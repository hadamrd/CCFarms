import json
import os
from typing import List, Dict
from datetime import datetime
from autogen import AssistantAgent
from jinja2 import Environment, FileSystemLoader, select_autoescape
from prefect import get_run_logger
from tenacity import retry, stop_after_attempt, wait_random_exponential
import re

CURRDIR = os.path.dirname(os.path.abspath(__file__))

template_env = Environment(
    loader=FileSystemLoader(CURRDIR),
    autoescape=select_autoescape(["html", "xml"]),
    trim_blocks=True,
    lstrip_blocks=True
)

class Satirist(AssistantAgent):
    def __init__(self, anthropic_api_key: str, model: str = "claude-3-5-sonnet-20241022"):
        """
        Initialize the Satirist agent for generating comedy scripts from analyzed news briefs.
        
        Args:
            anthropic_api_key: API key for Anthropic's Claude
            model: The LLM model to use
        """
        system_message = template_env.get_template('system_message.j2').render()
        
        super().__init__(
            name="NewsComedian",
            llm_config={
                "config_list": [{
                    "model": model,
                    "api_key": anthropic_api_key,
                    "api_base": "https://api.anthropic.com/v1/messages",
                    "api_type": "anthropic",
                }],
                "temperature": 0.7,  # Higher creativity for comedy
                "timeout": 45,
            },
            system_message=system_message
        )
        self.logger = get_run_logger()

    def _build_script_prompt(self, analyzed_articles: List[Dict]) -> str:
        """
        Generate prompt for the satirist using the template with analyzed articles.
        
        Args:
            analyzed_articles: List of analyzed article briefs
            
        Returns:
            Formatted prompt string
        """
        template = template_env.get_template('prompt.j2')
        return template.render(
            briefs=analyzed_articles,
            date=datetime.now().strftime("%A, %B %d, %Y")
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_random_exponential(
            multiplier=1,
            max=60
        )
    )
    def generate_comedy_script(self, analyzed_articles: List[Dict]) -> Dict:
        """
        Generate a comedy script based on the analyzed articles.
        
        Args:
            analyzed_articles: List of analyzed article briefs
            
        Returns:
            Dictionary containing the comedy script and metadata
        """
        try:
            prompt = self._build_script_prompt(analyzed_articles)
            self.logger.info(f"Generating comedy script for {len(analyzed_articles)} articles")
            
            response = self.generate_reply([{"content": prompt, "role": "user"}])
            
            if not response or "content" not in response:
                self.logger.error("Empty or invalid response from LLM")
                raise ValueError("Empty or invalid response from LLM")
            
            # Parse the tagged response
            script_data = self._extract_tagged_json(response.get("content", ""))
            
            result = {
                "script": script_data,
                "source_articles": [article.get("article_id") for article in analyzed_articles],
                "generated_at": datetime.now().isoformat(),
                "article_count": len(analyzed_articles)
            }
            
            return result
        except Exception as e:
            self.logger.error(f"Error in generate_comedy_script: {str(e)}")
            raise  # Re-raise for retry
        
    def _extract_tagged_json(self, content: str) -> Dict:
        """
        Extract JSON from between comedy_script tags in the LLM response.
        
        Args:
            content: Raw LLM response
            
        Returns:
            Parsed JSON content
        """
        pattern = r'<comedy_script>(.*?)</comedy_script>'
        match = re.search(pattern, content, re.DOTALL)
        if not match:
            raise ValueError("No comedy_script tags found in response")
        json_str = match.group(1).strip()
        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            self.logger.error(f"Invalid JSON in response: {json_str[:500]}...")
            raise ValueError(f"Invalid JSON in response: {str(e)}")
