from .base import UnifiedMetrics, ResponseBase
from .users import (
    UserCreate, UserRead, UserUpdate, UserPostSubmission,
    UserCreateAffiliate, UserCreateClient,
    # Legacy aliases
    AffiliateCreate, AffiliateRead, AffiliateUpdate, AffiliatePostSubmission
)
from .clients import ClientCreate, ClientRead, ClientUpdate, ClientWithUsers, ClientWithRelations
from .campaigns import CampaignCreate, CampaignRead, CampaignUpdate, CampaignReadWithRelations
from .posts import PostCreate, PostRead
from .reconciliation import (
    ReconciliationResult,
    ReconciliationTrigger,
    DiscrepancyDetail,
    TrustScoreChange,
    AlertPayload,
    ReconciliationJobPayload,
)
from .alerts import AlertRead, AlertResolve
from .platform import PlatformAPIResponse

__all__ = [
    # Base
    "UnifiedMetrics",
    "ResponseBase",
    
    # Users (including legacy affiliate aliases)
    "UserCreate",
    "UserRead", 
    "UserUpdate",
    "UserPostSubmission",
    "UserCreateAffiliate",
    "UserCreateClient",
    "AffiliateCreate",
    "AffiliateRead", 
    "AffiliateUpdate",
    "AffiliatePostSubmission",
    
    # Clients
    "ClientCreate",
    "ClientRead",
    "ClientUpdate", 
    "ClientWithUsers",
    "ClientWithRelations",
    
    # Campaigns
    "CampaignCreate",
    "CampaignRead",
    "CampaignUpdate",
    "CampaignReadWithRelations",
    
    # Posts
    "PostCreate",
    "PostRead",
    
    # Reconciliation
    "ReconciliationResult",
    "ReconciliationTrigger",
    "DiscrepancyDetail",
    "TrustScoreChange",
    "AlertPayload",
    "ReconciliationJobPayload",
    # Alerts
    "AlertRead",
    "AlertResolve",
    
    # Platform
    "PlatformAPIResponse"
]