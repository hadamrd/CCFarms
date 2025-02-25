from typing import Dict, Any
from prefect.blocks.core import Block
from pydantic import SecretStr
import requests

class TeamsWebhook(Block):
    """Block for Microsoft Teams webhook notifications"""
    _block_type_name = "Teams Webhook"
    _block_type_slug = "teams-webhook"
    _logo_url = "https://cdn-icons-png.flaticon.com/512/732/732227.png"
    
    url: SecretStr

    def notify(self, message: str) -> requests.Response:
        teams_payload: Dict[str, Any] = {
            "@type": "MessageCard",
            "@context": "http://schema.org/extensions",
            "themeColor": "0076D7",
            "summary": "Prefect Notification",
            "sections": [{
                "activityTitle": "Weather Report Flow",
                "text": message
            }]
        }
        
        response: requests.Response = requests.post(
            self.url.get_secret_value(),
            json=teams_payload
        )
        response.raise_for_status()
        return response
