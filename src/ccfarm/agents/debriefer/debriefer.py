import os
from typing import Dict, List, Any, Optional, cast
from prefect import get_run_logger
from ccfarm.agents.base_agent import BaseAgent
from ccfarm.clients.news_client import NewsAPIClient
from .models import ArticleAnalysis


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
        
        super().__init__(
            name="NewsDebriefer",
            llm_config=llm_config,
            template_dir=self.agent_dir,
        )
        
        self.logger = get_run_logger()
        self.news_client = news_client
    
    def process_articles(self, raw_articles: List[Dict]) -> List[ArticleAnalysis]:
        if not self.news_client:
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
                    processed.append(analysis_result)
                    self.logger.info(f"Successfully analyzed article: {article.get('title')}")
                except Exception as e:
                    self.logger.error(f"Analysis failed for {article.get('title')}: {str(e)}")
                
            except Exception as e:
                self.logger.error(f"Processing failed for {article.get('title', 'Unknown')}: {str(e)}")
                
        return processed
    
    def analyze_article(self, article: Dict) -> ArticleAnalysis:
        try:
            self.logger.info(f"Analyzing article: {article.get('title')}")
            
            analysis = cast(ArticleAnalysis, self.generate_reply(
                prompt_template="analyze_prompt.j2",
                response_tag="response",
                response_model=ArticleAnalysis,
                article=article
            ))
            
            return analysis
            
        except Exception as e:
            self.logger.error(f"Error analyzing article: {article.get('title', 'Unknown')}: {e}")
            raise  # Allow for retry logic to be handled by caller

