"""
Pydantic schemas for campaign management.
"""
from datetime import date, datetime
from typing import Optional, List
from decimal import Decimal
from pydantic import BaseModel, Field, ConfigDict
from ..db.enums import CampaignStatus

class CampaignCreate(BaseModel):
    name: str = Field(min_length=1, max_length=300)
    advertiser_name: str = Field(min_length=1, max_length=200)
    start_date: date
    end_date: Optional[date] = None
    impression_cap: Optional[int] = Field(None, gt=0)
    cpm: Optional[Decimal] = Field(None, gt=0)
    platform_ids: List[int] = Field(min_length=1, description="List of platform IDs for this campaign")
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "name": "Gamer Graveyard",
            "advertiser_name": "Opera GX",
            "start_date": "2025-06-01",
            "end_date": "2025-08-31",
            "impression_cap": 1000000,
            "cpm": 2.50,
            "platform_ids": [1, 2, 3]
        }
    })

class CampaignRead(BaseModel):
    id: int
    name: str
    advertiser_name: str
    start_date: date
    end_date: Optional[date]
    impression_cap: Optional[int]
    cpm: Optional[Decimal]
    status: CampaignStatus
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

class CampaignUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=300)
    end_date: Optional[date] = None
    impression_cap: Optional[int] = Field(None, gt=0)
    cpm: Optional[Decimal] = Field(None, gt=0)
    status: Optional[CampaignStatus] = None

