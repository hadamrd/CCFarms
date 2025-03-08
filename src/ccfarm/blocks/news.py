from prefect.blocks.core import Block
from pydantic import SecretStr, Field

class NewsAPIBlock(Block):
    """Secure storage and configuration for NewsAPI integration"""
    _block_type_name = "NewsAPI Configuration"
    _block_type_slug = "newsapi-config"
    _logo_url = "https://newsapi.org/images/n-logo-border.png"  # Official NewsAPI logo
    _description = "Stores credentials and configuration for NewsAPI integration"

    api_key: SecretStr = Field(
        ...,
        description="Your NewsAPI secret key (get from newsapi.org)",
        example="abcdef1234567890abcdef1234567890"
    )
    rate_limit: int = Field(
        default=100,
        description="Maximum API calls per hour",
        ge=50,
        le=500
    )
    skip_domains: list[str] = Field(
        default_factory=list,
        description="Domains to exclude from results",
        example=["medium.com", "nytimes.com"]
    )
    
    def get_client(self):
        """Initialize a configured NewsAPI client"""
        from ccfarm.clients.news_client import NewsAPIClient
        
        return NewsAPIClient(
            api_key=self.api_key.get_secret_value(),
            rate_limit=self.rate_limit,
            skip_domains=self.skip_domains
        )
