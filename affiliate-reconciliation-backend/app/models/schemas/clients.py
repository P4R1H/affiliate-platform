"""
Pydantic schemas for client-related operations.
"""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict

class ClientCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "name": "Opera GX"
        }
    })

class ClientRead(BaseModel):
    id: int
    name: str
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

class ClientUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)

class ClientWithUsers(ClientRead):
    """Client model with user relationships."""
    user_count: int = 0
    campaign_count: int = 0

class ClientWithRelations(ClientRead):
    """Client model with full relationship data."""
    users: List["UserRead"] = []
    campaigns: List["CampaignRead"] = []
    
    model_config = ConfigDict(from_attributes=True)

# Forward references will be resolved when UserRead and CampaignRead are imported
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .users import UserRead
    from .campaigns import CampaignRead