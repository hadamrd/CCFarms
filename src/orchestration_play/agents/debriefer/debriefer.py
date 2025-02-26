import json
import os
from autogen import AssistantAgent
from orchestration_play.agents.debriefer.models import ArticleBrief
from orchestration_play.clients.news_client import NewsAPIClient
from prefect import get_run_logger
import requests
from typing import List, Dict
from tenacity import retry, stop_after_attempt, wait_random_exponential
import re
from jinja2 import Environment, FileSystemLoader, select_autoescape

CURRDIR = os.path.dirname(os.path.abspath(__file__))

template_env = env = Environment(
    loader=FileSystemLoader(CURRDIR),
    autoescape=select_autoescape(["html", "xml"]),
    trim_blocks=True,
    lstrip_blocks=True
)

class Debriefer(AssistantAgent):
    def __init__(self, anthropic_api_key: str, news_client: NewsAPIClient=None, model: str = "claude-3-5-sonnet-20241022"):
        super().__init__(
            name="NewsScout",
            llm_config={
                    "config_list": [{
                        "model": model,
                        "api_key": anthropic_api_key,
                        "api_base": "https://api.anthropic.com/v1/messages",
                        "api_type": "anthropic",
                    }],
                    "temperature": 0.3,  # More factual
                    "timeout": 30,
            },
            system_message=template_env.get_template('system_message.j2')
        )
        self.logger = get_run_logger()
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': 'AINewsBot/1.0'})
        self.news_client = news_client

    def process_articles(self, raw_articles: List[Dict]) -> List[ArticleBrief]:
        """Sanitize and enrich articles with full content before analysis"""
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
                    brief = self.analyze_article(article)
                    processed.append(brief)
                    self.logger.info(f"Successfully analyzed article: {article.get('title')}")
                except Exception as e:
                    self.logger.error(f"Analysis failed for {article.get('title')}: {str(e)}")
                
            except Exception as e:
                self.logger.error(f"Analysis failed for {article.get('title')}: {str(e)}")
                
        return processed

    def _build_analysis_prompt(self, article: Dict) -> str:
        """Generate prompt using template with full content"""
        template = template_env.get_template('analyse_prompt.j2')
        return template.render(
            article=article.get('title', ''),
            content=article.get('content', ''),
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_random_exponential(
            multiplier=1,
            max=60
        )
    )
    def analyze_article(self, article: Dict) -> ArticleBrief:
        """Analyze a single article for comedy potential"""
        try:
            prompt = self._build_analysis_prompt(article)
            self.logger.info(f"Sending analysis request for: {article.get('title')}")
            
            response = self.generate_reply([{"content": prompt, "role": "user"}])
            
            if not response or "content" not in response:
                self.logger.error(f"Empty or invalid response for {article.get('title')}")
                raise ValueError("Empty or invalid response from LLM")
            
            self.logger.info(f"Received response: {response}")
            # Parse the tagged response into ArticleBrief
            brief_json = self._extract_tagged_json(response.get("content", ""))
            return ArticleBrief(**brief_json)
        except Exception as e:
            self.logger.error(f"Error in analyze_article: {str(e)}")
            raise  # Re-raise for retry
        
    def _extract_tagged_json(self, content: str) -> Dict:
        """Extract JSON from between brief_json tags"""
        pattern = r'<brief_json>(.*?)</brief_json>'
        match = re.search(pattern, content, re.DOTALL)
        if not match:
            raise ValueError("No brief_json tags found in response")
        json_str = match.group(1).strip()
        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            self.logger.error(f"Invalid JSON in response: {json_str[:500]}...")
            raise ValueError(f"Invalid JSON in response: {str(e)}")