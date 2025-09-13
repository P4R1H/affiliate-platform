"""
Main platform integration service.
This replaces services/platform_fetch.py entirely.
"""
from typing import Dict, Any, Optional, List
from datetime import datetime

from .reddit import RedditIntegration
from .instagram import InstagramIntegration
from .tiktok import TiktokIntegration
from .youtube import YoutubeIntegration
from .x import XIntegration
from app.models.schemas.platform import PlatformAPIResponse
from app.utils import get_logger

logger = get_logger(__name__)

class PlatformIntegrationService:
    """Main service for managing all platform integrations."""
    
    def __init__(self):
        self.integrations = {
            "reddit": RedditIntegration(),
            "instagram": InstagramIntegration(),
            "tiktok": TiktokIntegration(),
            "youtube": YoutubeIntegration(),
            "x": XIntegration(),
            "twitter": XIntegration(),  # Alias
        }
        self.logger = get_logger("platform_integration_service")
    
    async def fetch_post_metrics(
        self,
        platform_name: str,
        post_url: str,
        platform_config: Optional[Dict[str, Any]] = None
    ) -> Optional[PlatformAPIResponse]:
        """Fetch metrics from platform integration."""
        platform_name_lower = platform_name.lower()
        
        if platform_name_lower not in self.integrations:
            self.logger.error(
                "Unsupported platform",
                platform_name=platform_name,
                supported_platforms=list(self.integrations.keys())
            )
            return None
        
        integration = self.integrations[platform_name_lower]
        
        try:
            metrics = await integration.fetch_post_metrics(post_url, platform_config)
            
            if metrics:
                self.logger.info(
                    "Platform metrics fetch successful",
                    platform=platform_name,
                    views=metrics.views,
                    clicks=metrics.clicks
                )
            
            return metrics
            
        except Exception as e:
            self.logger.error(
                "Platform metrics fetch failed",
                platform=platform_name,
                error=str(e),
                exc_info=True
            )
            return None