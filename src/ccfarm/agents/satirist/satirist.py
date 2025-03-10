import os
from typing import Dict, List, cast
from datetime import datetime
from prefect import get_run_logger
from ccfarm.agents.base_agent import BaseAgent
from .models import ComedyScript


class Satirist(BaseAgent):
    """
    AI agent that generates comedy scripts from analyzed news briefs.
    Uses the BaseAgent class for structured prompting and response validation.
    """
    
    def __init__(
        self,
        anthropic_api_key: str,
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
            "temperature": 0.7,  # Higher temperature for more creative comedy
        }
        
        super().__init__(
            name="NewsComedian",
            llm_config=llm_config,
            template_dir=self.agent_dir,
        )
        
        self.logger = get_run_logger()
    
    def generate_comedy_script(self, analyzed_articles: List[Dict]) -> Dict:
        try:
            self.logger.info(f"Generating comedy script for {len(analyzed_articles)} articles")
            
            # Generate the script using the prompt template
            script = cast(ComedyScript, self.generate_reply(
                prompt_template="prompt.j2",
                response_tag="response",
                response_model=ComedyScript,
                briefs=analyzed_articles,
                date=datetime.now().strftime("%A, %B %d, %Y")
            ))

            script_dict = script.dict()
            
            result = {
                "script_data": script_dict,
                "source_articles": [
                    article.get("title", "unknown") 
                    for article in analyzed_articles
                ],
                "generated_at": datetime.now().isoformat(),
                "article_count": len(analyzed_articles)
            }
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error generating comedy script: {str(e)}")
            raise  # Re-raise for retry logic to be handled by caller
