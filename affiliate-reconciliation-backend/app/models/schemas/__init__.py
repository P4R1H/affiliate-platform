from .base import UnifiedMetrics, ResponseBase
from .affiliates import AffiliateCreate, AffiliateRead, AffiliateUpdate, AffiliatePostSubmission
from .campaigns import CampaignCreate, CampaignRead, CampaignUpdate
from .posts import PostCreate, PostRead
from .reconciliation import ReconciliationResult, ReconciliationTrigger
from .alerts import AlertRead, AlertResolve
from .platform import PlatformAPIResponse

__all__ = [
    # Base
    "UnifiedMetrics",
    "ResponseBase",
    
    # Affiliates
    "AffiliateCreate",
    "AffiliateRead", 
    "AffiliateUpdate",
    "AffiliatePostSubmission",
    
    # Campaigns
    "CampaignCreate",
    "CampaignRead",
    "CampaignUpdate",
    
    # Posts
    "PostCreate",
    "PostRead",
    
    # Reconciliation
    "ReconciliationResult",
    "ReconciliationTrigger",    
    # Alerts
    "AlertRead",
    "AlertResolve",
    
    # Platform
    "PlatformAPIResponse"
]

# ====================
# app/models/schemas/base.py
# ====================
# ====================
# app/models/schemas/affiliates.py
# ====================

# ====================
# app/models/schemas/campaigns.py
# ====================
# ====================
# app/models/schemas/posts.py
# ====================
# ====================
# app/models/schemas/reconciliation.py
# ====================

# ====================
# app/models/schemas/dashboard.py
# ====================
# ====================
# app/models/schemas/alerts.py
# ====================
# ====================
# app/models/schemas/platform.py
# ====================
