"""
TikTok platform integration with mock responses.
"""
import asyncio
import random
from datetime import datetime
from typing import Dict, Any, Optional

from app.models.schemas.platform import PlatformAPIResponse, TikTokAPIResponse
from app.utils import get_logger

logger = get_logger(__name__)

class TiktokIntegration:
    """TikTok platform integration class."""
    
    def __init__(self):
        self.platform_name = "tiktok"
        self.logger = get_logger(f"integration.{self.platform_name}")
    
    async def fetch_post_metrics(
        self, 
        post_url: str, 
        config: Optional[Dict[str, Any]] = None
    ) -> Optional[PlatformAPIResponse]:
        """
        Fetch TikTok post metrics (MOCK IMPLEMENTATION).
        
        Real implementation would use TikTok Business API:
        ```python
        # Real TikTok API implementation
        import aiohttp
        
        access_token = config.get('access_token')
        video_id = self._extract_video_id(post_url)
        
        api_url = f"https://business-api.tiktok.com/open_api/v1.3/video/data/"
        headers = {'Access-Token': access_token}
        data = {'video_ids': [video_id]}
        
        async with aiohttp.ClientSession() as session:
            async with session.post(api_url, headers=headers, json=data) as response:
                result = await response.json()
                # Process TikTok video data...
        ```
        
        We use mock because: TikTok is banned in India where this is developed,
        and TikTok Business API only shows metrics for your own content.
        """
        self.logger.info(
            "Fetching TikTok metrics (mock)",
            post_url=post_url
        )
        
        try:
            # Simulate API latency
            await asyncio.sleep(random.uniform(0.6, 2.0))
            
            # Simulate occasional failures (5% failure rate)
            if random.random() < 0.05:
                self.logger.warning(
                    "Simulated TikTok API failure",
                    post_url=post_url
                )
                return None
            
            base_plays = random.randint(5000, 100000)
            
            raw_tiktok_data = TikTokAPIResponse(
                play_count=base_plays,
                like_count=int(base_plays * random.uniform(0.03, 0.15)),
                comment_count=int(base_plays * random.uniform(0.002, 0.01)),
                share_count=int(base_plays * random.uniform(0.005, 0.03)),
                view_count=int(base_plays * 0.95),  # Slightly less than plays
                profile_views=int(base_plays * random.uniform(0.001, 0.008))
            )
            
            response = PlatformAPIResponse(
                post_url=post_url,
                platform_name="tiktok",
                raw_response=raw_tiktok_data.dict(),
                views=raw_tiktok_data.play_count,
                clicks=raw_tiktok_data.profile_views or 0,  # Handle None case
                conversions=raw_tiktok_data.share_count,
                spend=None,
                likes=raw_tiktok_data.like_count,
                comments=raw_tiktok_data.comment_count,
                shares=raw_tiktok_data.share_count,
                api_version="v1.3",
                rate_limit_remaining=random.randint(90, 100),
                cache_hit=False
            )
            
            self.logger.info(
                "TikTok metrics fetched successfully",
                post_url=post_url,
                views=response.views,
                clicks=response.clicks
            )
            
            return response
            
        except Exception as e:
            self.logger.error(
                "TikTok metrics fetch failed",
                post_url=post_url,
                error=str(e),
                exc_info=True
            )
            return None