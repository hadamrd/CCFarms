import os
from typing import Dict, List, Any, Optional, cast
from prefect import get_run_logger
from ccfarm.agents.BaseAgent import BaseAgent
from ccfarm.clients.news_client import NewsAPIClient
from .models import NewsAnalysis


class Debriefer(BaseAgent):
    """
    AI agent that performs detailed analysis on news articles for comedy potential.
    Uses the BaseAgent class for structured prompting and response validation.
    """
    news_client: NewsAPIClient
    
    def __init__(
        self,
        anthropic_api_key: str,
        news_client: NewsAPIClient,
    ):
        """
        Initialize the Debriefer agent with required dependencies.
        
        Args:
            anthropic_api_key: API key for Anthropic
            news_client: NewsAPI client
        """
        # Set up the directory for this agent
        self.agent_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Configure LLM settings for AutoGen
        llm_config = {
            "config_list": [
                {
                    "model": "claude-3-5-sonnet-20241022",
                    "api_key": anthropic_api_key,
                    "api_base": "https://api.anthropic.com/v1/messages",
                    "api_type": "anthropic",
                }
            ],
            "temperature": 0.3,  # More factual assessments
        }
        
        # Initialize base agent
        super().__init__(
            name="NewsDebriefer",
            llm_config=llm_config,
            template_dir=self.agent_dir,
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
                    analysis_result_dict = analysis_result.dict()
                    analysis_result_dict['url'] = url
                    processed.append(analysis_result_dict)
                    self.logger.info(f"Successfully analyzed article: {article.get('title')}")
                except Exception as e:
                    self.logger.error(f"Analysis failed for {article.get('title')}: {str(e)}")
                
            except Exception as e:
                self.logger.error(f"Processing failed for {article.get('title', 'Unknown')}: {str(e)}")
                
        return processed
    
    def analyze_article(self, article: Dict) -> NewsAnalysis:
        """
        Analyze a single article using BaseAgent processing.
        
        Args:
            article: Article dictionary with title and content
            
        Returns:
            NewsAnalysis with comedic evaluation results conforming to schema
        """
        try:
            self.logger.info(f"Analyzing article: {article.get('title')}")
            
            # Use the base agent's process method with the analyze_prompt.j2 template
            analysis = cast(NewsAnalysis, self.generate_reply(
                prompt_template="analyze_prompt.j2",
                response_tag="brief_json",
                response_model=NewsAnalysis,
                article=article
            ))
            
            return analysis
            
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
                
            # Create an article object with the URL and content
            article = {
                'url': url,
                'content': content
            }
            
            # Analyze it
            analysis_result = self.analyze_article(article)
            
            # Convert to dict and add URL
            result_dict = analysis_result.dict()
            result_dict['url'] = url
            return result_dict
            
        except Exception as e:
            self.logger.error(f"Error analyzing URL {url}: {str(e)}")
            raise
