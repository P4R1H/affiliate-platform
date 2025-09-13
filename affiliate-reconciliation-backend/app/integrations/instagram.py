"""
Instagram platform integration with mock responses.
"""
import asyncio
import random
from typing import Dict, Any, Optional

from app.models.schemas.platform import PlatformAPIResponse, InstagramAPIResponse
from app.utils import get_logger

logger = get_logger(__name__)

class InstagramIntegration:
    """Instagram platform integration class."""
    
    def __init__(self):
        self.platform_name = "instagram"
        self.logger = get_logger(f"integration.{self.platform_name}")
    
    async def fetch_post_metrics(
        self, 
        post_url: str, 
        config: Optional[Dict[str, Any]] = None
    ) -> Optional[PlatformAPIResponse]:
        """
        Fetch Instagram post metrics (MOCK IMPLEMENTATION).
        
        Real implementation would use Instagram Basic Display API:
        ```python
        # Real Instagram API implementation
        import aiohttp
        
        access_token = config.get('access_token')
        post_id = self._extract_post_id(post_url)
        
        api_url = f"https://graph.instagram.com/{post_id}/insights"
        params = {
            'metric': 'impressions,reach,profile_visits,website_clicks',
            'access_token': access_token
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url, params=params) as response:
                data = await response.json()
                # Process Instagram insights data...
        ```
        
        We use mock because: Instagram API only provides metrics for posts you own,
        not for external posts you want to track.
        """
        self.logger.info(
            "Fetching Instagram metrics (mock)",
            post_url=post_url
        )
        
        try:
            # Simulate API latency
            # Local latency simulation range (seconds)
            await asyncio.sleep(random.uniform(0.4, 1.2))
            
            # Simulate occasional failures (5% failure rate)
            if random.random() < 0.05:  # 5% simulated failure rate
                self.logger.warning(
                    "Simulated Instagram API failure",
                    post_url=post_url
                )
                return None
            
            # Generate realistic Instagram engagement (reach <= impressions by definition)
            base_reach = random.randint(1000, 20000)
            impressions = int(base_reach * random.uniform(1.05, 1.6))  # impressions >= reach

            raw_instagram_data = InstagramAPIResponse(
                like_count=int(base_reach * random.uniform(0.03, 0.12)),
                comment_count=int(base_reach * random.uniform(0.005, 0.03)),
                impressions=impressions,
                reach=base_reach,
                play_count=int(base_reach * random.uniform(1.2, 2.0)) if random.choice([True, False]) else None,
                saved=int(base_reach * random.uniform(0.01, 0.04)),
                profile_visits=int(base_reach * random.uniform(0.002, 0.015)),
                website_clicks=int(base_reach * random.uniform(0.001, 0.008))
            )
            
            # Build unified response (impressions now always present)
            response = PlatformAPIResponse(
                post_url=post_url,
                platform_name="instagram",
                raw_response=raw_instagram_data.dict(),
                views=raw_instagram_data.impressions,
                clicks=raw_instagram_data.website_clicks or 0,
                conversions=(raw_instagram_data.saved or 0) + (raw_instagram_data.profile_visits or 0),
                spend=None,  # Organic posts don't have ad spend
                likes=raw_instagram_data.like_count,
                comments=raw_instagram_data.comment_count,
                shares=int(raw_instagram_data.like_count * 0.15),
                api_version="v18.0",
                rate_limit_remaining=random.randint(180, 200),
                cache_hit=False
            )
            
            self.logger.info(
                "Instagram metrics fetched successfully",
                post_url=post_url,
                views=response.views,
                clicks=response.clicks,
                conversions=response.conversions
            )
            
            return response
            
        except Exception as e:
            self.logger.error(
                "Instagram metrics fetch failed",
                post_url=post_url,
                error=str(e),
                exc_info=True
            )
            return None