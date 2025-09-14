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

| Platform | Status | Metrics Supported | Authentication | Link Processing |
|----------|--------|-------------------|----------------|----------------|
| Reddit | Mock (with real link normalization) | views, clicks, conversions, likes, comments, shares | Client credentials | Real API normalization |
| Instagram | Mock (ready for real API) | impressions, clicks, conversions, likes, comments, shares | Access token | Basic URL cleaning |
| TikTok | Mock (ready for real API) | plays, clicks, conversions, likes, comments, shares | Business API | Basic URL cleaning |
| YouTube | Mock (ready for real API) | views, clicks, conversions, likes, comments | API key | Basic URL cleaning |
| X/Twitter | Mock (ready for real API) | impressions, clicks, conversions, likes, comments, shares | Bearer token | Basic URL cleaning |

### Why Mock Implementations?

All current implementations are mock-based for the following reasons:

1. **Cost Efficiency**: Real platform APIs often require premium access or significant costs
2. **Rate Limiting**: Production APIs have strict rate limits that would impact development
3. **Deterministic Testing**: Mocks allow consistent testing without external dependencies
4. **Rapid Development**: Focus on core reconciliation logic without API integration complexity

Each mock implementation includes:
- Realistic metric generation with platform-specific patterns
- Simulated API latency and failure rates (5% failure rate)
- Proper error handling and retry logic
- **Reddit**: Real API link normalization for share links
- **Instagram**: Proper impressions ≥ reach relationship
- **TikTok**: Viral content simulation with age-based decay
- **YouTube**: Subscriber conversion rates based on content type
- **X/Twitter**: Tweet impression patterns based on follower count
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
    views: int = Field(ge=0, description="Views/impressions/plays")
    clicks: int = Field(ge=0, description="Clicks/taps on post or links") 
    conversions: int = Field(ge=0, description="Actions taken (follows, saves, etc.)")
    spend: Optional[float] = Field(None, ge=0, description="Ad spend if applicable")
    
    # Engagement metrics (platform-specific)
    likes: Optional[int] = Field(None, ge=0, description="Likes/reactions")
    comments: Optional[int] = Field(None, ge=0, description="Comments/replies")
    shares: Optional[int] = Field(None, ge=0, description="Shares/retweets")
    
    # Metadata
    fetched_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    api_version: Optional[str] = Field(None, description="API version used")
    rate_limit_remaining: Optional[int] = Field(None, description="API rate limit remaining")
    cache_hit: bool = Field(False, description="Whether data came from cache")
    raw_response: Dict[str, Any]  # Original platform response
    
    def to_unified_metrics(self) -> UnifiedMetrics:
        """Convert to unified metrics format for reconciliation."""
        return UnifiedMetrics(
            views=self.views,
            clicks=self.clicks,
            conversions=self.conversions,
            post_url=self.post_url,
            platform_name=self.platform_name,
            timestamp=self.fetched_at,
            source="platform_api"
        )
```

**Note**: `UnifiedMetrics` is imported from `app.models.schemas.base`.

## Error Handling & Platform Errors

All integrations include comprehensive error handling with structured error reporting:

```python
class PlatformError(BaseModel):
    """Schema for platform integration errors."""
    platform_name: str
    error_type: str = Field(description="API_ERROR, RATE_LIMITED, NOT_FOUND, etc.")
    error_message: str
    post_url: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    retry_after: Optional[int] = Field(None, description="Seconds to wait before retry")
```

**Error Types**:
- `API_ERROR`: General API failures
- `RATE_LIMITED`: Rate limit exceeded
- `NOT_FOUND`: Post/content not found
- `AUTH_FAILED`: Authentication/authorization issues
- `TIMEOUT`: Request timeout
- `INVALID_RESPONSE`: Malformed API response

**Error Handling Patterns**:
```python
try:
    # Platform API call
    response = await session.get(api_url)
    
    if response.status == 429:
        raise PlatformError(
            platform_name="reddit",
            error_type="RATE_LIMITED",
            error_message="Rate limit exceeded",
            post_url=post_url,
            retry_after=60
        )
        
except asyncio.TimeoutError:
    raise PlatformError(
        platform_name="reddit", 
        error_type="TIMEOUT",
        error_message="Request timed out",
        post_url=post_url
        )
```

## Unified Metrics Conversion

All `PlatformAPIResponse` objects can be converted to the internal `UnifiedMetrics` format for reconciliation processing:

```python
# Automatic conversion
platform_response = await integration.fetch_post_metrics(post_url, config)
unified_metrics = platform_response.to_unified_metrics()

# UnifiedMetrics schema
class UnifiedMetrics(BaseModel):
    """Internal metrics format for reconciliation engine."""
    
    views: int
    clicks: int
    conversions: int
    post_url: str
    platform_name: str
    timestamp: datetime
    source: str = "platform_api"  # or "user_submission"
```

**Conversion Benefits**:
- Standardized format for all downstream processing
- Consistent timestamp handling
- Source attribution for debugging
- Easy integration with reconciliation engine

## Link Processing & NormalizationThe platform includes sophisticated URL processing capabilities to handle various link formats and normalize them for consistent processing.

### Reddit Link Normalization

**File**: `app/integrations/reddit.py`

Reddit has a unique challenge with share links that need to be resolved to canonical post URLs. The integration includes real Reddit API calls for link normalization:

```python
async def normalize_reddit_link(url: str) -> str:
    """
    Normalize Reddit share links to canonical post URLs using real Reddit API.
    
    Examples:
        https://reddit.com/r/test/s/abc123 -> https://reddit.com/r/test/comments/real_id/title
        https://reddit.com/r/test/comments/123/title -> https://reddit.com/r/test/comments/123/title (unchanged)
    """
```

**Features**:
- Resolves Reddit share links (`/s/` format) to canonical URLs
- Uses real Reddit JSON API (no authentication required)
- Handles both `reddit.com` and `redd.it` short links
- Includes proper error handling and timeout management

### General URL Processing

**File**: `app/utils/link_processing.py`

All URLs go through a standardized processing pipeline:

```python
async def process_post_url(url: str, expected_platform: str) -> tuple[str, str]:
    """
    Complete URL processing pipeline: clean, detect, validate, normalize.
    
    Steps:
    1. Clean URL (remove tracking parameters, fragments)
    2. Validate URL format
    3. Detect platform from URL patterns
    4. Validate platform match with expected platform
    5. Apply platform-specific normalization (Reddit only)
    """
```

**Supported Platforms for Detection**:
- Reddit (`reddit.com`, `redd.it`, `old.reddit.com`)
- Instagram (`instagram.com`, `instagr.am`)
- TikTok (`tiktok.com`, `vm.tiktok.com`)
- YouTube (`youtube.com`, `youtu.be`)
- X/Twitter (`twitter.com`, `x.com`, `t.co`)

## Platform-Specific Implementations

### Reddit Integration

**File**: `app/integrations/reddit.py`

**Features**:
- **Real Link Normalization**: Uses Reddit's public JSON API to resolve share links
- **Sophisticated Mock Metrics**: Realistic engagement patterns with failure simulation
- **Comprehensive Error Handling**: Timeout, rate limiting, and API error management

**Metrics Mapping**:
- `views` → Post upvotes (Reddit doesn't provide view counts)
- `clicks` → Comment count (proxy for engagement)
- `conversions` → Total awards received
- `likes` → Upvotes
- `comments` → Comment count
- `shares` → Estimated shares (upvotes × 0.02 heuristic)

**Mock Implementation Features**:
- Base engagement between 100-5000 upvotes
- Realistic upvote ratios (0.75-0.98)
- Comment ratios based on engagement (0.02-0.08)
- Award distribution (0-15 total awards)
- 5% simulated failure rate

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

**Features**:
- **Realistic Engagement Simulation**: Proper impressions ≥ reach relationship
- **Content Type Variations**: Different patterns for posts vs stories/reels
- **Geographic and Demographic Factors**: Regional engagement variations

**Metrics Mapping**:
- `views` → Impressions (always ≥ reach by definition)
- `clicks` → Website clicks
- `conversions` → Saves + profile visits (engagement actions)
- `likes` → Like count
- `comments` → Comment count
- `shares` → Estimated shares (likes × 0.15 heuristic)

**Mock Implementation Features**:
- Base reach between 1000-20000
- Impressions = reach × (1.05-1.6) to maintain realistic ratios
- Like ratios (0.03-0.12 of reach)
- Comment ratios (0.005-0.03 of reach)
- Optional play_count for video content
- 5% simulated failure rate

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

**Features**:
- **Viral Content Simulation**: Some videos get massive play counts
- **Age-Based Engagement Decay**: Older content gets less engagement
- **Regional Variations**: Different performance patterns by region

**Metrics Mapping**:
- `views` → Play count (primary metric)
- `clicks` → Profile views
- `conversions` → Share count
- `likes` → Like count
- `comments` → Comment count
- `shares` → Share count

**Mock Implementation Features**:
- Play counts from 1000-50000 (some viral content up to 500k+)
- Like ratios (0.02-0.08 of plays)
- Comment ratios (0.001-0.005 of plays)
- Share ratios (0.005-0.02 of plays)
- 5% simulated failure rate

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

**Features**:
- **Content Type Variations**: Different engagement patterns by video type
- **Subscriber Conversion Modeling**: Realistic subscriber gain rates
- **Age-Based Performance**: Video age affects growth patterns

**Metrics Mapping**:
- `views` → View count
- `clicks` → Estimated clicks (views × CTR)
- `conversions` → Subscriber gains
- `likes` → Like count
- `comments` → Comment count

**Mock Implementation Features**:
- View counts from 1000-50000
- Like ratios (0.01-0.05 of views)
- Comment ratios (0.001-0.01 of views)
- Subscriber conversion rates (0.001-0.005 of views)
- Realistic CTR ranges (0.02-0.12)
- 5% simulated failure rate

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

**Features**:
- **Follower-Based Engagement**: Impression patterns based on follower count
- **Content Type Variations**: Different engagement for text vs media tweets
- **Thread vs Single Tweet**: Different patterns for thread components

**Metrics Mapping**:
- `views` → Impression count
- `clicks` → URL clicks + profile clicks
- `conversions` → Bookmark count
- `likes` → Like count
- `comments` → Reply count
- `shares` → Retweet count

**Mock Implementation Features**:
- Impression counts from 1000-50000 based on follower simulation
- Like ratios (0.005-0.03 of impressions)
- Reply ratios (0.001-0.01 of impressions)
- Retweet ratios (0.01-0.05 of impressions)
- Bookmark ratios (0.002-0.01 of impressions)
- 5% simulated failure rate

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
    """Main service for managing all platform integrations."""
    
    def __init__(self):
        self.integrations = {
            "reddit": RedditIntegration(),
            "instagram": InstagramIntegration(),
            "tiktok": TiktokIntegration(),
            "youtube": YoutubeIntegration(),
            "x": XIntegration(),
            "twitter": XIntegration(),  # Alias for backward compatibility
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
X_BEARER_TOKEN=your_x_bearer_token  # Alternative naming
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

def test_twitter_alias():
    # Test that 'twitter' platform name works
    service = PlatformIntegrationService()
    response = await service.fetch_post_metrics(
        "twitter", 
        "https://twitter.com/user/status/123",
        config={"bearer_token": "test_token"}
    )
    assert response.platform_name == "x"  # Internal name
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