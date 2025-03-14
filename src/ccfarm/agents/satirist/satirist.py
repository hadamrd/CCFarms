import os
from typing import cast
from ccfarm.agents.satirist.models import VideoScript
from common.utils import get_flow_aware_logger
from ccfarm.agents.base_agent import BaseAgent
from ccfarm.clients.news_client import NewsAPIClient
from datetime import datetime

class Satirist(BaseAgent):
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
                    "model": "claude-3-7-sonnet-20250219",
                    "api_key": anthropic_api_key,
                    "api_base": "https://api.anthropic.com/v1/messages",
                    "api_type": "anthropic",
                }
            ],
            "temperature": 0.7,
        }
        
        super().__init__(
            name="NewsDebriefer",
            llm_config=llm_config,
            template_dir=self.agent_dir
        )
        
        self.logger = get_flow_aware_logger("Satirist")
        self.news_client = news_client

    def process_articles(self, raw_articles: list[dict]) -> VideoScript|None:
        if not self.news_client:
            raise ValueError("NewsAPI client not initialized")
        
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
                
            except Exception as e:
                self.logger.error(f"Processing failed for {article.get('title', 'Unknown')}: {str(e)}")
        
        try:
            return self.produce_article_audio_script(raw_articles)
        except Exception as e:
            self.logger.error(f"Satirist youtube script generation failed!")
            return None

    def produce_article_audio_script(self, articles: list[dict]) -> VideoScript:
        try:
            self.logger.info(f"Generating multi-article script for {len(articles)} articles")
            
            script = cast(VideoScript, self.generate_reply(
                prompt_template="multi_article_prompt.j2",
                response_tag="response",
                response_model=VideoScript,
                articles=articles,
                date=datetime.now().strftime("%d/%m/%Y, %H:%M:%S")
            ))
            
            self.logger.info(f"Successfully generated script: {script.title}")
            return script
        
        except Exception as e:
            self.logger.error(f"Error generating multi-article script: {e}")
            raise
