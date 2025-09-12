from abc import ABC, abstractmethod
from typing import Dict, Any

class PlatformIntegration(ABC):
    @abstractmethod
    def fetch_data(self, campaign_id: str) -> Dict[str, Any]:
        """Fetch metrics like views, clicks, conversions for a campaign."""
        pass