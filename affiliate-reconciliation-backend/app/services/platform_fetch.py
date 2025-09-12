from app.integrations import RedditIntegration, InstagramIntegration, TiktokIntegration, YoutubeIntegration

PLATFORM_MAP = {
    'reddit': RedditIntegration(),
    'instagram': InstagramIntegration(),
    'tiktok': TiktokIntegration(),
    'youtube' : YoutubeIntegration()
}

def fetch_from_platform(platform_name: str, campaign_id: str):
    integration = PLATFORM_MAP.get(platform_name)
    if not integration:
        raise ValueError("Unsupported platform")
    return integration.fetch_data(campaign_id)