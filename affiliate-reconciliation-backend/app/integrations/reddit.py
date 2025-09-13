"""
Reddit platform integration with link normalization and mock metrics.
Contains both real Reddit API for link resolution and mock data for metrics.
"""
import asyncio
import random
import re
from typing import Dict, Any, Optional
import aiohttp

from app.models.schemas.platform import PlatformAPIResponse, RedditAPIResponse
from app.utils import get_logger

logger = get_logger(__name__)

class RedditIntegration:
    """Reddit platform integration class."""
    
    def __init__(self):
        self.platform_name = "reddit"
        self.logger = get_logger(f"integration.{self.platform_name}")
    
    async def fetch_post_metrics(
        self, 
        post_url: str, 
        config: Optional[Dict[str, Any]] = None
    ) -> Optional[PlatformAPIResponse]:
        """Fetch metrics for a Reddit post."""
        return await fetch_reddit_metrics(post_url, config)

async def normalize_reddit_link(url: str) -> str:
    """
    Normalize Reddit share links to canonical post URLs using real Reddit API.
    
    Args:
        url: Clean Reddit URL (may be share link)
        
    Returns:
        Canonical Reddit post URL
        
    Raises:
        ValueError: If Reddit API call fails or URL is invalid
        
    Examples:
        https://reddit.com/r/test/s/abc123 -> https://reddit.com/r/test/comments/real_id/title
        https://reddit.com/r/test/comments/123/title -> https://reddit.com/r/test/comments/123/title (unchanged)
    """
    logger.info(
        "Starting Reddit link normalization",
        url=url
    )
    
    # Check if it's already a canonical URL
    canonical_pattern = r'reddit\.com/r/[^/]+/comments/[a-zA-Z0-9]+'
    if re.search(canonical_pattern, url):
        logger.debug(
            "URL is already canonical",
            url=url
        )
        return url
    
    # Extract share ID from share links
    share_patterns = [
        r'reddit\.com/r/[^/]+/s/([a-zA-Z0-9]+)',
        r'redd\.it/([a-zA-Z0-9]+)'
    ]
    
    share_id = None
    for pattern in share_patterns:
        match = re.search(pattern, url)
        if match:
            share_id = match.group(1)
            break
    
    if not share_id:
        logger.warning(
            "Could not extract share ID from Reddit URL",
            url=url
        )
        # Return original URL if we can't extract share ID
        return url
    
    try:
        # Real Reddit API call to resolve share link
        # Using Reddit's public JSON API (no auth required)
        api_url = f"https://www.reddit.com/api/info.json?id=t3_{share_id}"
        timeout = aiohttp.ClientTimeout(total=10)  # 10s timeout for link resolution

        async with aiohttp.ClientSession(timeout=timeout) as session:
            headers = {
                'User-Agent': 'Affiliate-Reconciliation-Bot/1.0 (contact: your-email@domain.com)'
            }
            
            logger.debug(
                "Making Reddit API request",
                api_url=api_url,
                share_id=share_id
            )
            
            async with session.get(api_url, headers=headers) as response:
                if response.status != 200:
                    logger.error(
                        "Reddit API request failed",
                        status_code=response.status,
                        url=url,
                        api_url=api_url
                    )
                    raise ValueError(f"Reddit API returned status {response.status}")
                
                data = await response.json()
                
                # Extract canonical URL from response
                if (data and 
                    'data' in data and 
                    'children' in data['data'] and 
                    len(data['data']['children']) > 0):
                    
                    post_data = data['data']['children'][0]['data']
                    canonical_url = f"https://reddit.com{post_data.get('permalink', '')}"
                    
                    # Remove trailing slash for consistency
                    canonical_url = canonical_url.rstrip('/')
                    
                    logger.info(
                        "Reddit link normalization successful",
                        original_url=url,
                        canonical_url=canonical_url,
                        share_id=share_id
                    )
                    
                    return canonical_url
                else:
                    logger.error(
                        "Invalid Reddit API response format",
                        response_data=data,
                        url=url
                    )
                    raise ValueError("Reddit API returned invalid response format")
    
    except asyncio.TimeoutError:
        logger.error(
            "Reddit API request timed out",
            url=url,
            share_id=share_id
        )
        raise ValueError("Reddit API request timed out")
    
    except aiohttp.ClientError as e:
        logger.error(
            "Reddit API client error",
            url=url,
            error=str(e)
        )
        raise ValueError(f"Reddit API client error: {str(e)}")
    
    except Exception as e:
        logger.error(
            "Reddit link normalization failed",
            url=url,
            error=str(e),
            exc_info=True
        )
        raise ValueError(f"Failed to normalize Reddit link: {str(e)}")

async def fetch_reddit_metrics(
    post_url: str, 
    config: Optional[Dict[str, Any]] = None
) -> Optional[PlatformAPIResponse]:
    """
    Fetch Reddit post metrics (MOCK IMPLEMENTATION).
    
    Real implementation would look like:
    ```python
    # Real Reddit API implementation
    import praw
    
    reddit = praw.Reddit(
        client_id=config.get('client_id'),
        client_secret=config.get('client_secret'),
        user_agent=config.get('user_agent')
    )
    
    # Extract post ID from URL
    post_id = extract_reddit_post_id(post_url)
    submission = reddit.submission(id=post_id)
    
    return PlatformAPIResponse(
        post_url=post_url,
        platform_name="reddit",
        raw_response=submission.__dict__,
        views=submission.ups,  # Reddit doesn't provide view counts
        clicks=submission.num_comments,
        conversions=submission.total_awards_received,
        likes=submission.ups,
        comments=submission.num_comments,
        shares=0,  # Reddit doesn't track shares
    )
    ```
    
    We use mock because: Reddit doesn't provide actual view counts, 
    only upvotes and engagement metrics.
    """
    logger.info(
        "Fetching Reddit metrics (mock)",
        post_url=post_url
    )
    
    try:
        # Simulate API latency
        await asyncio.sleep(random.uniform(0.3, 1.5))

        # Simulate occasional failures (configurable failure rate)
        if random.random() < 0.05:  # 5% simulated failure rate
            logger.warning(
                "Simulated Reddit API failure",
                post_url=post_url
            )
            return None

        # Generate realistic mock data
        base_engagement = random.randint(100, 5000)
        
        # Create raw Reddit API response
        raw_reddit_data = RedditAPIResponse(
            ups=base_engagement,
            downs=int(base_engagement * random.uniform(0.05, 0.15)),
            score=int(base_engagement * random.uniform(0.85, 0.95)),
            num_comments=int(base_engagement * random.uniform(0.02, 0.08)),
            upvote_ratio=random.uniform(0.75, 0.98),
            awards=random.randint(0, 10),
            gilded=random.randint(0, 3),
            total_awards_received=random.randint(0, 15),
            subreddit="technology",
            permalink="/r/technology/comments/123abc/title/"
        )
        
        # Map to unified response
        response = PlatformAPIResponse(
            post_url=post_url,
            platform_name="reddit",
            raw_response=raw_reddit_data.dict(),
            views=raw_reddit_data.ups,
            clicks=raw_reddit_data.num_comments,
            conversions=raw_reddit_data.total_awards_received or 0,
            spend=None,
            likes=raw_reddit_data.ups,
            comments=raw_reddit_data.num_comments,
            shares=int(raw_reddit_data.ups * 0.02),  # heuristic kept local (low impact)
            api_version="v1.0",
            rate_limit_remaining=random.randint(950, 1000),
            cache_hit=False
        )
        
        logger.info(
            "Reddit metrics fetched successfully",
            post_url=post_url,
            views=response.views,
            clicks=response.clicks,
            conversions=response.conversions
        )
        
        return response
        
    except Exception as e:
        logger.error(
            "Reddit metrics fetch failed",
            post_url=post_url,
            error=str(e),
            exc_info=True
        )
        return None

def extract_reddit_post_id(url: str) -> Optional[str]:
    """Extract Reddit post ID from canonical URL."""
    patterns = [
        r'reddit\.com/r/[^/]+/comments/([a-zA-Z0-9]+)',
        r'redd\.it/([a-zA-Z0-9]+)'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    
    return None