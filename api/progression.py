from api.client import APIClient
from typing import Optional, Dict, List
from datetime import datetime, timezone

class ProgressionSync:
    def __init__(self, api_client: APIClient, device_id: str):
        self.api = api_client
        self.device_id = device_id
        
    async def get_progression(self, endpoint: str) -> Optional[Dict]:
        try:
            resp = await self.api.get(endpoint)
            if resp.status_code == 200:
                return resp.json()
            return None
        except Exception as e:
            print(f"Error fetching progression: {e}")
            return None
            
    async def update_progression(self, endpoint: str, fraction: float, title: str = None, href: str = None, position: int = None, content_type: str = None):
        """
        Sync progression based on the Readium Locator object specification 
        (used by Codex and LibrarySimplified).
        """
        try:
            data = {
                "modified": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "device": {
                    "id": f"urn:uuid:{self.device_id}",
                    "name": "ComicCatcher PyQt6"
                },
                "locator": {
                    "locations": {
                        "progression": fraction,
                        "total_progression": fraction
                    }
                }
            }
            
            if position is not None:
                data["locator"]["locations"]["position"] = position
            if title:
                data["locator"]["title"] = title
            if href:
                data["locator"]["href"] = href
            if content_type:
                data["locator"]["type"] = content_type
                
            await self.api.put(endpoint, json=data)
        except Exception as e:
            print(f"Failed to sync progression: {e}")
