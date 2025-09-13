# Platform Integrations Guide

Complete guide for implementing and extending platform integrations in the Affiliate Reconciliation Platform.

## Overview

The platform uses a modular adapter pattern to support multiple advertising platforms. Each platform integration implements a standardized interface while handling platform-specific authentication, API calls, and data transformation.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                 Platform Integration Service                │
├─────────────────────────────────────────────────────────────┤
│  Reddit  │ Instagram │ TikTok │ YouTube │ X/Twitter │ ...   │
│ Adapter  │  Adapter  │ Adapter│ Adapter │  Adapter  │       │
└─────────────────────────────────────────────────────────────┘
           │           │         │         │           │
           ▼           ▼         ▼         ▼           ▼
    ┌───────────┬─────────────┬─────────┬───────────┬─────────┐
    │ Reddit    │ Instagram   │ TikTok  │ YouTube   │ X       │
    │ API       │ Graph API   │ API     │ Data API  │ API v2  │
    └───────────┴─────────────┴─────────┴───────────┴─────────┘
```

## Current Implementations

### Supported Platforms

| Platform | Status | Metrics Supported | Authentication |
|----------|--------|-------------------|----------------|
| Reddit | Mock (ready for real API) | views, clicks, conversions | Client credentials |
| Instagram | Mock (ready for real API) | impressions, clicks, conversions | Access token |
| TikTok | Mock (ready for real API) | plays, clicks, conversions | Business API |
| YouTube | Mock (ready for real API) | views, clicks, subscribers | API key |
| X/Twitter | Mock (ready for real API) | impressions, clicks, bookmarks | Bearer token |

### Why Mock Implementations?

All current implementations are mock-based for the following reasons:

1. **Cost Efficiency**: Real platform APIs often require premium access or significant costs
2. **Rate Limiting**: Production APIs have strict rate limits that would impact development
3. **Deterministic Testing**: Mocks allow consistent testing without external dependencies
4. **Rapid Development**: Focus on core reconciliation logic without API integration complexity

Each mock implementation includes:
- Realistic metric generation with platform-specific patterns
- Simulated API latency and failure rates
- Proper error handling and retry logic
- Complete data transformation to unified format

## Integration Interface

All platform integrations must implement the following interface:

```python
class PlatformIntegration:
    """Base interface for platform integrations."""
    
    async def fetch_post_metrics(
        self, 
        post_url: str, 
        config: Optional[Dict[str, Any]] = None
    ) -> Optional[PlatformAPIResponse]:
        """
        Fetch metrics for a specific post.
        
        Args:
            post_url: The URL of the post to fetch metrics for
            config: Platform-specific configuration (API keys, etc.)
            
        Returns:
            PlatformAPIResponse with unified metrics or None if failed
        """
        pass
```

## Unified Response Format

All platform integrations must return data in the standardized `PlatformAPIResponse` format:

```python
class PlatformAPIResponse(BaseModel):
    """Unified platform API response format."""
    
    post_url: str
    platform_name: str
    
    # Core metrics (standardized across platforms)
    views: Optional[int] = None
    clicks: Optional[int] = None  
    conversions: Optional[int] = None
    spend: Optional[float] = None
    
    # Engagement metrics (platform-specific)
    likes: Optional[int] = None
    comments: Optional[int] = None
    shares: Optional[int] = None
    
    # Metadata
    raw_response: Dict[str, Any]  # Original platform response
    api_version: Optional[str] = None
    rate_limit_remaining: Optional[int] = None
    cache_hit: bool = False
    fetched_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
```

## Platform-Specific Implementations

### Reddit Integration

**File**: `app/integrations/reddit.py`

**Metrics Mapping**:
- `views` → Post upvotes (Reddit doesn't provide view counts)
- `clicks` → Comment count (proxy for engagement)
- `conversions` → Award count

**Mock Implementation**:
```python
async def fetch_post_metrics(self, post_url: str, config: Optional[Dict[str, Any]] = None) -> Optional[PlatformAPIResponse]:
    # Simulate realistic Reddit engagement patterns
    base_upvotes = random.randint(50, 10000)
    
    raw_reddit_data = RedditAPIResponse(
        ups=base_upvotes,
        downs=int(base_upvotes * random.uniform(0.05, 0.3)),
        num_comments=int(base_upvotes * random.uniform(0.1, 0.8)),
        total_awards_received=int(base_upvotes * random.uniform(0.001, 0.05))
    )
    
    return PlatformAPIResponse(
        post_url=post_url,
        platform_name="reddit",
        raw_response=raw_reddit_data.dict(),
        views=raw_reddit_data.ups,
        clicks=raw_reddit_data.num_comments,
        conversions=raw_reddit_data.total_awards_received
    )
```

**Real Implementation Template**:
```python
import praw

async def fetch_reddit_metrics_real(post_url: str, config: Dict[str, Any]) -> Optional[PlatformAPIResponse]:
    reddit = praw.Reddit(
        client_id=config['client_id'],
        client_secret=config['client_secret'],
        user_agent=config['user_agent']
    )
    
    post_id = extract_reddit_post_id(post_url)
    submission = reddit.submission(id=post_id)
    
    return PlatformAPIResponse(
        post_url=post_url,
        platform_name="reddit",
        raw_response=submission.__dict__,
        views=submission.ups,
        clicks=submission.num_comments,
        conversions=submission.total_awards_received
    )
```

### Instagram Integration

**File**: `app/integrations/instagram.py`

**Metrics Mapping**:
- `views` → Impressions
- `clicks` → Website clicks + profile visits
- `conversions` → Saves + profile visits

**Mock Implementation Features**:
- Realistic engagement rates based on follower count
- Proper impression/reach relationship (impressions ≥ reach)
- Story vs post metric variations

**Real Implementation Template**:
```python
import aiohttp

async def fetch_instagram_metrics_real(post_url: str, config: Dict[str, Any]) -> Optional[PlatformAPIResponse]:
    access_token = config['access_token']
    post_id = extract_instagram_post_id(post_url)
    
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

### TikTok Integration

**File**: `app/integrations/tiktok.py`

**Metrics Mapping**:
- `views` → Play count
- `clicks` → Profile views
- `conversions` → Share count

**Mock Implementation Features**:
- Viral content simulation (some videos get massive play counts)
- Age-based engagement decay
- Regional variation in performance

**Real Implementation Template**:
```python
import aiohttp

async def fetch_tiktok_metrics_real(post_url: str, config: Dict[str, Any]) -> Optional[PlatformAPIResponse]:
    access_token = config['access_token']
    video_id = extract_tiktok_video_id(post_url)
    
    api_url = "https://business-api.tiktok.com/open_api/v1.3/video/data/"
    headers = {'Access-Token': access_token}
    data = {'video_ids': [video_id]}
    
    async with aiohttp.ClientSession() as session:
        async with session.post(api_url, headers=headers, json=data) as response:
            result = await response.json()
            # Process TikTok video data...
```

### YouTube Integration

**File**: `app/integrations/youtube.py`

**Metrics Mapping**:
- `views` → View count
- `clicks` → View count × CTR
- `conversions` → Subscriber gains

**Mock Implementation Features**:
- Video age affects growth patterns
- Subscriber conversion rates based on content type
- Realistic like/dislike ratios

**Real Implementation Template**:
```python
from googleapiclient.discovery import build

async def fetch_youtube_metrics_real(post_url: str, config: Dict[str, Any]) -> Optional[PlatformAPIResponse]:
    api_key = config['api_key']
    video_id = extract_youtube_video_id(post_url)
    
    youtube = build('youtube', 'v3', developerKey=api_key)
    
    request = youtube.videos().list(
        part='statistics,snippet',
        id=video_id
    )
    response = request.execute()
    
    if response['items']:
        stats = response['items'][0]['statistics']
        # Process YouTube video statistics...
```

### X/Twitter Integration  

**File**: `app/integrations/x.py`

**Metrics Mapping**:
- `views` → Impression count
- `clicks` → URL clicks + profile clicks
- `conversions` → Bookmarks

**Mock Implementation Features**:
- Tweet impression patterns based on follower count
- Realistic engagement rates for different content types
- Thread vs single tweet variations

**Real Implementation Template**:
```python
import tweepy

async def fetch_x_metrics_real(post_url: str, config: Dict[str, Any]) -> Optional[PlatformAPIResponse]:
    bearer_token = config['bearer_token']
    client = tweepy.Client(bearer_token=bearer_token)
    
    tweet_id = extract_tweet_id(post_url)
    
    tweet = client.get_tweet(
        tweet_id, 
        tweet_fields=['public_metrics', 'non_public_metrics'],
        user_auth=True
    )
    
    if tweet.data:
        metrics = tweet.data.public_metrics
        # Process X/Twitter metrics...
```

## Adding a New Platform Integration

### Step 1: Create the Integration File

Create a new file in `app/integrations/` following the naming pattern:

```python
# app/integrations/linkedin.py

from typing import Dict, Any, Optional
from app.models.schemas.platform import PlatformAPIResponse
from app.utils import get_logger

class LinkedInIntegration:
    """LinkedIn platform integration class."""
    
    def __init__(self):
        self.platform_name = "linkedin"
        self.logger = get_logger(f"integration.{self.platform_name}")
    
    async def fetch_post_metrics(
        self, 
        post_url: str, 
        config: Optional[Dict[str, Any]] = None
    ) -> Optional[PlatformAPIResponse]:
        """Fetch LinkedIn post metrics."""
        
        # Mock implementation
        try:
            # Simulate API call
            await asyncio.sleep(random.uniform(0.5, 1.5))
            
            # Generate realistic LinkedIn metrics
            base_impressions = random.randint(500, 50000)
            
            return PlatformAPIResponse(
                post_url=post_url,
                platform_name="linkedin",
                raw_response={
                    "impressions": base_impressions,
                    "clicks": int(base_impressions * 0.02),
                    "reactions": int(base_impressions * 0.01)
                },
                views=base_impressions,
                clicks=int(base_impressions * 0.02),
                conversions=int(base_impressions * 0.005)
            )
            
        except Exception as e:
            self.logger.error("LinkedIn metrics fetch failed", error=str(e))
            return None
```

### Step 2: Register in Platform Service

Add the new integration to `app/integrations/platforms.py`:

```python
from .linkedin import LinkedInIntegration

class PlatformIntegrationService:
    def __init__(self):
        self.integrations = {
            "reddit": RedditIntegration(),
            "instagram": InstagramIntegration(),
            "tiktok": TiktokIntegration(),
            "youtube": YoutubeIntegration(),
            "x": XIntegration(),
            "linkedin": LinkedInIntegration(),  # Add new integration
        }
```

### Step 3: Add Platform Schema

Add platform-specific response schema to `app/models/schemas/platform.py`:

```python
class LinkedInAPIResponse(BaseModel):
    """Raw LinkedIn API response schema."""
    impressions: int
    clicks: int
    reactions: int
    shares: Optional[int] = None
    comments: Optional[int] = None
```

### Step 4: Create Database Entry

Add the platform to your database:

```sql
INSERT INTO platforms (name, api_base_url, is_active) 
VALUES ('linkedin', 'https://api.linkedin.com/v2/', true);
```

### Step 5: Add URL Processing (if needed)

If the platform has specific URL patterns, add processing logic to `app/utils/link_processing.py`:

```python
def process_linkedin_url(url: str) -> str:
    """Normalize LinkedIn post URLs."""
    # Add LinkedIn-specific URL normalization logic
    return normalized_url
```

## Configuration Management

Platform configurations are managed through the database and can be updated via API:

```python
# Example platform configuration
{
    "api_key": "your_api_key",
    "client_id": "your_client_id", 
    "client_secret": "your_client_secret",
    "rate_limit": 1000,
    "timeout": 30,
    "retry_attempts": 3
}
```

### Environment Variables

For development, platform credentials can be set via environment variables:

```bash
# Reddit
REDDIT_CLIENT_ID=your_reddit_client_id
REDDIT_CLIENT_SECRET=your_reddit_client_secret
REDDIT_USER_AGENT=your_app_name

# Instagram
INSTAGRAM_ACCESS_TOKEN=your_instagram_access_token

# TikTok
TIKTOK_ACCESS_TOKEN=your_tiktok_access_token

# YouTube
YOUTUBE_API_KEY=your_youtube_api_key

# X/Twitter
TWITTER_BEARER_TOKEN=your_twitter_bearer_token
```

## Error Handling

All integrations should implement consistent error handling:

```python
async def fetch_post_metrics(self, post_url: str, config: Optional[Dict[str, Any]] = None) -> Optional[PlatformAPIResponse]:
    try:
        # Platform API call logic
        pass
        
    except requests.exceptions.Timeout:
        self.logger.warning("Platform API timeout", post_url=post_url)
        return None
        
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 429:
            self.logger.warning("Rate limit exceeded", post_url=post_url)
        elif e.response.status_code == 401:
            self.logger.error("Authentication failed", post_url=post_url)
        else:
            self.logger.error("HTTP error", status_code=e.response.status_code)
        return None
        
    except Exception as e:
        self.logger.error("Unexpected error", error=str(e), exc_info=True)
        return None
```

## Testing Integration

### Unit Testing

Create tests for your integration in `tests/test_unit_integrations.py`:

```python
def test_linkedin_integration():
    integration = LinkedInIntegration()
    
    # Test successful fetch
    response = await integration.fetch_post_metrics(
        "https://linkedin.com/posts/example",
        config={"api_key": "test_key"}
    )
    
    assert response is not None
    assert response.platform_name == "linkedin"
    assert response.views > 0
```

### Integration Testing

Add integration tests that use the full reconciliation flow:

```python
def test_linkedin_reconciliation_flow(client, db_session):
    # Create test data
    platform = create_platform(name="linkedin")
    affiliate = create_affiliate()
    campaign = create_campaign()
    
    # Submit post
    response = client.post("/api/v1/submissions/", json={
        "campaign_id": campaign.id,
        "platform_id": platform.id,
        "url": "https://linkedin.com/posts/example",
        "claimed_views": 1000
    })
    
    # Verify reconciliation
    # ... test logic
```

## Migration from Mock to Real APIs

When ready to switch from mock to real APIs:

1. **Implement Real API Logic**: Replace mock implementation with actual API calls
2. **Add Authentication**: Implement proper credential management
3. **Handle Rate Limits**: Add rate limiting and backoff logic
4. **Update Configuration**: Set real API credentials
5. **Test Thoroughly**: Verify real API integration works correctly
6. **Monitor Performance**: Watch for API latency and error rates

### Example Migration

```python
class RedditIntegration:
    def __init__(self):
        self.use_mock = os.getenv("REDDIT_USE_MOCK", "true").lower() == "true"
        
    async def fetch_post_metrics(self, post_url: str, config: Optional[Dict[str, Any]] = None) -> Optional[PlatformAPIResponse]:
        if self.use_mock:
            return await self._fetch_mock_metrics(post_url)
        else:
            return await self._fetch_real_metrics(post_url, config)
```

## Monitoring & Observability

All integrations automatically include:

- **Structured Logging**: Request/response details, timing, errors
- **Performance Metrics**: API call duration, success/failure rates
- **Circuit Breaker**: Automatic failure detection and recovery
- **Rate Limit Tracking**: Monitor API quota usage

See [Operations & Observability](OPERATIONS_AND_OBSERVABILITY.md) for detailed monitoring setup.

## Best Practices

1. **Consistent Error Handling**: Always return None on failure, log appropriately
2. **Rate Limit Respect**: Implement backoff and retry logic
3. **Data Validation**: Validate API responses before processing
4. **Security**: Never log sensitive data (API keys, tokens)
5. **Performance**: Use async/await for all I/O operations
6. **Testing**: Maintain high test coverage for all integration paths
7. **Documentation**: Document API-specific quirks and limitations

## Troubleshooting

### Common Issues

**Integration Not Found**:
```
ERROR: Unsupported platform: linkedin
```
- Verify integration is registered in PlatformIntegrationService
- Check platform exists in database

**Authentication Failures**:
```
ERROR: Authentication failed
```
- Verify API credentials are correct
- Check token expiration dates
- Ensure proper scopes/permissions

**Rate Limiting**:
```
WARNING: Rate limit exceeded
```
- Implement proper backoff logic
- Consider caching responses
- Review API usage patterns

**Data Transformation Errors**:
```
ERROR: Failed to transform platform response
```
- Verify platform response schema
- Check for missing/null fields
- Validate data types

For more troubleshooting guidance, see [Operations & Observability](OPERATIONS_AND_OBSERVABILITY.md).