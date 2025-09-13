"""
Link processing utilities for cleaning and normalizing social media URLs.
Handles basic URL sanitization and platform detection only.
"""
import urllib.parse
import re
from typing import Optional
from app.utils import get_logger

logger = get_logger(__name__)

def clean_link(url: str) -> str:
    """
    Clean URL by removing tracking parameters, fragments, and extra whitespace.
    
    Args:
        url: Raw URL from user input
        
    Returns:
        Cleaned URL without query parameters and fragments
        
    Example:
        clean_link("https://reddit.com/r/test/comments/123?utm_source=share#comment")
        -> "https://reddit.com/r/test/comments/123"
    """
    if not url or not url.strip():
        raise ValueError("URL cannot be empty")
    
    url = url.strip()
    
    try:
        parsed = urllib.parse.urlparse(url)
        
        # Remove query parameters and fragments
        clean = parsed._replace(query='', fragment='')
        clean_url = urllib.parse.urlunparse(clean)
        
        # Remove trailing slashes for consistency
        if clean_url.endswith('/') and clean_url != 'https://' and clean_url != 'http://':
            clean_url = clean_url.rstrip('/')
        
        logger.debug(
            "URL cleaned successfully",
            original_url=url,
            clean_url=clean_url
        )
        
        return clean_url
        
    except Exception as e:
        logger.error(
            "URL cleaning failed",
            url=url,
            error=str(e)
        )
        raise ValueError(f"Invalid URL format: {str(e)}")

def detect_platform(url: str) -> Optional[str]:
    """
    Detect platform from URL patterns.
    
    Args:
        url: Clean URL
        
    Returns:
        Platform name (lowercase) or None if not recognized
        
    Supported platforms: reddit, instagram, meta, tiktok, youtube, x
    """
    if not url:
        return None
    
    url_lower = url.lower()
    
    # Reddit patterns
    if ('reddit.com' in url_lower or 
        'redd.it' in url_lower or 
        'old.reddit.com' in url_lower):
        return 'reddit'
    
    # Instagram patterns
    elif 'instagram.com' in url_lower or 'instagr.am' in url_lower:
        return 'instagram'
    
    # Meta/Facebook patterns
    elif ('facebook.com' in url_lower or 
          'fb.com' in url_lower or 
          'm.facebook.com' in url_lower):
        return 'meta'
    
    # TikTok patterns
    elif 'tiktok.com' in url_lower or 'vm.tiktok.com' in url_lower:
        return 'tiktok'
    
    # YouTube patterns
    elif ('youtube.com' in url_lower or 
          'youtu.be' in url_lower or 
          'm.youtube.com' in url_lower):
        return 'youtube'
    
    # X/Twitter patterns
    elif ('twitter.com' in url_lower or 
          'x.com' in url_lower or 
          't.co' in url_lower):
        return 'x'
    
    else:
        logger.warning(
            "Unknown platform detected",
            url=url
        )
        return None

def validate_url_format(url: str) -> bool:
    """
    Validate that URL has proper format.
    
    Args:
        url: URL to validate
        
    Returns:
        True if URL format is valid, False otherwise
    """
    try:
        result = urllib.parse.urlparse(url)
        return all([result.scheme, result.netloc])
    except Exception:
        return False

async def process_post_url(url: str, expected_platform: str) -> tuple[str, str]:
    """
    Complete URL processing pipeline: clean, detect, validate, normalize.
    
    Args:
        url: Raw URL from user input
        expected_platform: Platform name from database
        
    Returns:
        Tuple of (processed_url, detected_platform)
        
    Raises:
        ValueError: If URL is invalid, platform mismatch, or processing fails
    """
    logger.info(
        "Starting URL processing pipeline",
        raw_url=url,
        expected_platform=expected_platform
    )
    
    # Step 1: Clean URL
    try:
        clean_url = clean_link(url)
    except ValueError as e:
        logger.error(
            "URL cleaning failed in pipeline",
            raw_url=url,
            error=str(e)
        )
        raise ValueError(f"URL cleaning failed: {str(e)}")
    
    # Step 2: Validate format
    if not validate_url_format(clean_url):
        logger.error(
            "URL format validation failed",
            clean_url=clean_url
        )
        raise ValueError("URL format is invalid")
    
    # Step 3: Detect platform
    detected_platform = detect_platform(clean_url)
    if not detected_platform:
        logger.error(
            "Platform detection failed",
            clean_url=clean_url
        )
        raise ValueError("Could not detect platform from URL")
    
    # Step 4: Validate platform match
    if detected_platform.lower() != expected_platform.lower():
        logger.error(
            "Platform mismatch detected",
            detected_platform=detected_platform,
            expected_platform=expected_platform,
            clean_url=clean_url
        )
        raise ValueError(
            f"URL belongs to {detected_platform} but expected {expected_platform}"
        )
    
    # Step 5: Platform-specific normalization (only Reddit needs this)
    processed_url = clean_url
    if detected_platform.lower() == 'reddit':
        # Import here to avoid circular imports
        from app.integrations.reddit import normalize_reddit_link
        try:
            processed_url = await normalize_reddit_link(clean_url)
        except ValueError as e:
            logger.error(
                "Reddit link normalization failed in pipeline",
                clean_url=clean_url,
                error=str(e)
            )
            raise ValueError(f"Reddit link normalization failed: {str(e)}")
    
    logger.info(
        "URL processing pipeline completed successfully",
        raw_url=url,
        processed_url=processed_url,
        detected_platform=detected_platform
    )
    
    return processed_url, detected_platform