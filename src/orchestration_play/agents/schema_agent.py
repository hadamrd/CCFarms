# src/orchestration_play/agents/schema_agent.py
from autogen import AssistantAgent
from jinja2 import Environment, FileSystemLoader, select_autoescape
import json
import os
import re
from typing import Dict, List, Optional, Any, Union
import jsonschema
from prefect import get_run_logger
from tenacity import retry, stop_after_attempt, wait_random_exponential
import inspect

class SchemaAgent:
    """
    Base agent class that combines autogen's AssistantAgent with JSON Schema validation
    and templating capabilities.
    """
    
    def __init__(
        self,
        name: str,
        response_schema: Dict[str, Any],
        anthropic_api_key: str,
        model: str = "claude-3-5-sonnet-20241022",
        template_dir: Optional[str] = None,
        system_message_template: str = "system_message.j2",
        temperature: float = 0.3,
        response_tag: str = "response_json",
        max_retries: int = 3,
    ):
        """
        Initialize the schema-based agent.
        
        Args:
            name: Name of the agent
            response_schema: JSON Schema that defines the expected response format
            anthropic_api_key: API key for Anthropic
            model: Model name to use
            template_dir: Directory containing templates (defaults to agent's directory)
            system_message_template: Filename of the system message template
            temperature: Model temperature
            response_tag: Tag to wrap the JSON response in
            max_retries: Maximum number of retries for API calls
        """
        self.logger = get_run_logger()
        self.response_schema = response_schema
        self.response_tag = response_tag
        self.max_retries = max_retries
        
        # Set up template environment
        if template_dir is None:
            # Default to the directory where the child class is defined
            template_dir = os.path.dirname(inspect.getfile(self.__class__))
        
        self.template_env = Environment(
            loader=FileSystemLoader(template_dir),
            autoescape=select_autoescape(["html", "xml"]),
            trim_blocks=True,
            lstrip_blocks=True
        )
        
        # Generate system message from template
        system_message = self._render_template(
            system_message_template,
            response_tag=response_tag,
            response_schema=json.dumps(response_schema, indent=2)
        )
        
        # Initialize the underlying AssistantAgent
        self.agent = AssistantAgent(
            name=name,
            llm_config={
                "config_list": [{
                    "model": model,
                    "api_key": anthropic_api_key,
                    "api_base": "https://api.anthropic.com/v1/messages",
                    "api_type": "anthropic",
                }],
                "temperature": temperature,
                "timeout": 30,
            },
            system_message=system_message
        )
    
    def _render_template(self, template_name: str, **kwargs) -> str:
        """
        Render a template with the given arguments.
        
        Args:
            template_name: Name of the template file
            **kwargs: Arguments to pass to the template
            
        Returns:
            Rendered template string
        """
        try:
            template = self.template_env.get_template(template_name)
            return template.render(**kwargs)
        except Exception as e:
            self.logger.error(f"Error rendering template {template_name}: {str(e)}")
            raise
    
    def _extract_tagged_json(self, content: str) -> Dict:
        """
        Extract JSON from between response tags in the LLM response.
        
        Args:
            content: Raw response from LLM
            
        Returns:
            Parsed JSON dictionary
        """
        pattern = f'<{self.response_tag}>(.*?)</{self.response_tag}>'
        match = re.search(pattern, content, re.DOTALL)
        
        if not match:
            self.logger.error(f"No {self.response_tag} tags found in response")
            error_msg = f"Response does not contain proper {self.response_tag} tags. Full response: {content[:500]}..."
            raise ValueError(error_msg)
            
        json_str = match.group(1).strip()
        
        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            self.logger.error(f"Invalid JSON in response: {json_str[:500]}...")
            raise ValueError(f"Invalid JSON in response: {str(e)}")
    
    def _validate_against_schema(self, data: Dict) -> None:
        """
        Validate data against the JSON schema.
        
        Args:
            data: Data to validate
            
        Raises:
            jsonschema.exceptions.ValidationError: If validation fails
        """
        try:
            jsonschema.validate(instance=data, schema=self.response_schema)
        except jsonschema.exceptions.ValidationError as e:
            self.logger.error(f"Schema validation failed: {str(e)}")
            raise
    
    # @retry(
    #     stop=stop_after_attempt(3),
    #     wait=wait_random_exponential(
    #         multiplier=1,
    #         max=60
    #     )
    # )
    def process(self, prompt_template: str, **kwargs) -> Dict:
        """
        Process a prompt and return the validated response.
        
        Args:
            prompt_template: Name of the prompt template file
            **kwargs: Arguments to pass to the prompt template
            
        Returns:
            Validated dictionary response
        """
        # Add schema to kwargs
        kwargs['response_schema'] = json.dumps(self.response_schema, indent=2)
        kwargs['response_tag'] = self.response_tag
            
        # Render prompt
        prompt = self._render_template(prompt_template, **kwargs)
        
        try:
            self.logger.info(f"Sending prompt to LLM")
            response = self.agent.generate_reply([{"content": prompt, "role": "user"}])
            
            if not response or "content" not in response:
                raise ValueError("Empty or invalid response from LLM")
                
            # Parse response
            json_data = self._extract_tagged_json(response["content"])
            
            # Validate against schema
            self._validate_against_schema(json_data)
            
            return json_data
            
        except Exception as e:
            self.logger.error(f"Error in process method: {str(e)}")
            raise
    
    def load_schema_from_file(self, schema_file: str) -> Dict:
        """
        Load a JSON schema from a file.
        
        Args:
            schema_file: Path to the schema file
            
        Returns:
            Loaded schema dictionary
        """
        try:
            with open(schema_file, 'r') as f:
                schema = json.load(f)
            return schema
        except Exception as e:
            self.logger.error(f"Error loading schema from {schema_file}: {str(e)}")
            raise