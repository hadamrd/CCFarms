import os
import json
from typing import List, Dict, Optional
from prefect import get_run_logger
from orchestration_play.agents.schema_agent import SchemaAgent
from orchestration_play.clients.news_client import NewsAPIClient


class Debriefer(SchemaAgent):
    """
    AI agent that performs detailed analysis on news articles.
    Uses the SchemaAgent base class for structured prompting and response validation.
    """
    
    def __init__(
        self,
        anthropic_api_key: str,
        news_client: Optional[NewsAPIClient] = None,
        model: str = "claude-3-5-sonnet-20241022",
        schema_file: Optional[str] = None
    ):
        """
        Initialize the Debriefer agent with required dependencies.
        
        Args:
            anthropic_api_key: API key for Anthropic
            news_client: Optional NewsAPI client (can be injected later)
            model: Anthropic model to use
            schema_file: Path to JSON schema file (optional)
        """
        # Set up the directory for this agent
        self.agent_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Load schema from file or use default
        schema_path = schema_file or os.path.join(
            self.agent_dir,
            "debriefer_schema.json"
        )
        
        # Load schema from file
        if os.path.exists(schema_path):
            with open(schema_path, 'r') as f:
                response_schema = json.load(f)
        else:
            raise ValueError("Schema file not found: " + schema_path)
        
        # Initialize base agent with JSON schema
        super().__init__(
            name="NewsDebriefer",
            response_schema=response_schema,
            anthropic_api_key=anthropic_api_key,
            model=model,
            template_dir=self.agent_dir,
            response_tag="brief_json",
            temperature=0.3
        )
        
        self.logger = get_run_logger()
        self.news_client = news_client
    
    def set_news_client(self, news_client: NewsAPIClient):
        """Set the NewsAPI client after initialization"""
        self.news_client = news_client
    
    def process_articles(self, raw_articles: List[Dict]) -> List[Dict]:
        """
        Process a batch of articles by fetching full content and analyzing them.
        
        Args:
            raw_articles: List of article dictionaries from NewsAPI
            
        Returns:
            List of validated article analysis results as dictionaries
        """
        if not self.news_client:
            self.logger.error("NewsAPI client not set - call set_news_client() first")
            raise ValueError("NewsAPI client not initialized")
            
        processed = []
        
        for article in raw_articles:
            try:
                # First get the full content
                url = article.get('url')
                if not url:
                    self.logger.warning(f"Skipping article with no URL: {article.get('title')}")
                    continue

                content = self.news_client.fetch_article_content(url)
                if not content:
                    self.logger.warning(f"Could not fetch content for: {url}")
                    continue

                # Add full content to article
                article['content'] = content

                # Now analyze with full content
                try:
                    analysis_result = self.analyze_article(article)
                    # Add the URL to the result
                    analysis_result['url'] = url
                    processed.append(analysis_result)
                    self.logger.info(f"Successfully analyzed article: {article.get('title')}")
                except Exception as e:
                    self.logger.error(f"Analysis failed for {article.get('title')}: {str(e)}")
                
            except Exception as e:
                self.logger.error(f"Processing failed for {article.get('title', 'Unknown')}: {str(e)}")
                
        return processed
    
    def analyze_article(self, article: Dict) -> Dict:
        """
        Analyze a single article using SchemaAgent processing.
        
        Args:
            article: Article dictionary with title and content
            
        Returns:
            Dictionary with analysis results conforming to schema
        """
        try:
            self.logger.info(f"Analyzing article: {article.get('title')}")
            
            # Use the base agent's process method with the analyze_prompt.j2 template
            return self.process(
                prompt_template="analyze_prompt.j2",
                article=article
            )
            
        except Exception as e:
            self.logger.error(f"Error analyzing article: {article.get('title', 'Unknown')}: {e}")
            raise  # Allow for retry logic to be handled by caller
    
    def analyze_single_url(self, url: str) -> Dict:
        """
        Fetch and analyze a single article by URL.
        
        Args:
            url: URL of the article to analyze
            
        Returns:
            Dictionary with analysis results conforming to schema
        """
        if not self.news_client:
            self.logger.error("NewsAPI client not set - call set_news_client() first")
            raise ValueError("NewsAPI client not initialized")
            
        try:
            # Fetch content
            content = self.news_client.fetch_article_content(url)
            if not content:
                raise ValueError(f"Could not fetch content for URL: {url}")
                
            # Create a minimal article object
            article = {
                'url': url,
                'title': self._extract_title_from_content(content),
                'content': content
            }
            
            # Analyze it
            analysis_result = self.analyze_article(article)
            # Add URL to result
            analysis_result['url'] = url
            return analysis_result
            
        except Exception as e:
            self.logger.error(f"Error analyzing URL {url}: {str(e)}")
            raise
    
    def _extract_title_from_content(self, content: str) -> str:
        """
        Extract title from HTML content if possible.
        This is a simple fallback when title isn't provided.
        
        Args:
            content: HTML content of the article
            
        Returns:
            Extracted title or placeholder
        """
        import re
        title_match = re.search(r'<title>(.*?)</title>', content, re.IGNORECASE)
        if title_match:
            return title_match.group(1)
        return "Unknown Title"