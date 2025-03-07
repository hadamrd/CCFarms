import os
import json
from typing import List, Dict, Optional
from datetime import datetime
from prefect import get_run_logger
from orchestration_play.agents.schema_agent import SchemaAgent


class Satirist(SchemaAgent):
    """
    AI agent that generates comedy scripts from analyzed news briefs.
    Uses the SchemaAgent base class for structured prompting and response validation.
    """
    
    def __init__(
        self,
        anthropic_api_key: str,
        model: str = "claude-3-5-sonnet-20241022",
        schema_file: Optional[str] = None,
        temperature: float = 0.7  # Higher creativity for comedy
    ):
        """
        Initialize the Satirist agent for generating comedy scripts.
        
        Args:
            anthropic_api_key: API key for Anthropic's Claude
            model: The LLM model to use
            schema_file: Path to JSON schema file (optional)
            temperature: Model temperature (higher for more creative comedy)
        """
        # Set up the directory for this agent
        self.agent_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Load schema from file or use default
        schema_path = schema_file or os.path.join(
            self.agent_dir,
            "satirist_schema.json"
        )
        
        # Load schema from file
        if os.path.exists(schema_path):
            with open(schema_path, 'r') as f:
                response_schema = json.load(f)
        else:
            raise ValueError("Schema file not found: " + schema_path)
        
        # Initialize base agent with JSON schema
        super().__init__(
            name="NewsComedian",
            response_schema=response_schema,
            anthropic_api_key=anthropic_api_key,
            model=model,
            template_dir=self.agent_dir,
            system_message_template="system_message.j2",
            response_tag="comedy_script",
            temperature=temperature
        )
        
        self.logger = get_run_logger()
    
    def generate_comedy_script(self, analyzed_articles: List[Dict]) -> Dict:
        """
        Generate a comedy script based on the analyzed articles.
        
        Args:
            analyzed_articles: List of analyzed article briefs
            
        Returns:
            Dictionary containing the comedy script and metadata
        """
        try:
            self.logger.info(f"Generating comedy script for {len(analyzed_articles)} articles")
            
            # Convert datetime to string to avoid serialization issues
            current_date = datetime.now().strftime("%A, %B %d, %Y")
            
            # Use the base SchemaAgent's process method with the prompt.j2 template
            script_data = self.process(
                prompt_template="prompt.j2",
                briefs=analyzed_articles,
                date=current_date
            )
            
            # Add metadata to the result
            result = {
                "script_data": script_data,
                "source_articles": [article.get("article_id", article.get("url", "unknown")) for article in analyzed_articles],
                "generated_at": datetime.now().isoformat(),
                "article_count": len(analyzed_articles)
            }
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error in generate_comedy_script: {str(e)}")
            raise  # Re-raise for retry logic to be handled by caller