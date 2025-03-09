from __future__ import annotations

import json
import os
import re
import inspect
from typing import Dict, Optional, Any, Type

from autogen import AssistantAgent
from jinja2 import Environment, FileSystemLoader, select_autoescape
from pydantic import BaseModel
from prefect import get_run_logger
from tenacity import retry, stop_after_attempt, wait_random_exponential


class ResponseParsingError(Exception):
    pass


class ValidationError(Exception):
    pass


class LLMInteractionError(Exception):
    pass


class BaseAgent:
    def __init__(
        self,
        name: str,
        llm_config: dict,
        template_dir: Optional[str] = None,
        system_message_kwargs: Optional[Dict[str, Any]] = None,
        max_retries: int = 3,
    ):
        self.logger = get_run_logger()
        self.name = name
        self.max_retries = max_retries

        if template_dir is None:
            template_dir = os.path.dirname(inspect.getfile(self.__class__))

        self._setup_template_environment(template_dir)
        system_message = self._generate_system_message(system_message_kwargs or {})

        self.agent = AssistantAgent(name=name, llm_config=llm_config, system_message=system_message)

    def _setup_template_environment(self, template_dir: str) -> None:
        self.logger.info(f"Setting up template environment in '{template_dir}'")

        if not os.path.isdir(template_dir):
            raise FileNotFoundError(f"Template directory not found: {template_dir}")

        self.template_env = Environment(
            loader=FileSystemLoader(template_dir),
            autoescape=select_autoescape(["html", "xml"]),
            trim_blocks=True,
            lstrip_blocks=True,
        )

        template_path = os.path.join(template_dir, "system_message.j2")
        if not os.path.exists(template_path):
            raise FileNotFoundError(
                f"Required template 'system_message.j2' not found at {template_path}"
            )

    def _generate_system_message(self, kwargs: Dict[str, Any]) -> str:
        self.logger.info("Generating system message")
        return self._render_template("system_message.j2", **kwargs)

    def _render_template(self, template_name: str, **kwargs) -> str:
        try:
            template = self.template_env.get_template(template_name)
            return template.render(**kwargs)
        except Exception as e:
            self.logger.error(f"Error rendering template '{template_name}': {str(e)}")
            raise RuntimeError(f"Template rendering failed: {str(e)}") from e

    def _extract_tagged_json(self, content: str, tag_name: str) -> Dict[str, Any]:
        pattern = f"<{tag_name}>(.*?)</{tag_name}>"
        match = re.search(pattern, content, re.DOTALL)

        if not match:
            error_msg = f"Response does not contain <{tag_name}> tags"
            self.logger.error(error_msg)
            truncated_content = content[:500] + "..." if len(content) > 500 else content
            raise ResponseParsingError(f"{error_msg}. Content: {truncated_content}")

        json_str = match.group(1).strip()

        try:
            result = json.loads(json_str)
            if not isinstance(result, dict):
                raise ResponseParsingError(f"Parsed JSON is not a dictionary: {type(result)}")
            return result
        except json.JSONDecodeError as e:
            truncated_json = json_str[:300] + "..." if len(json_str) > 300 else json_str
            error_msg = f"Invalid JSON in <{tag_name}> tags: {str(e)}\nContent: {truncated_json}"
            self.logger.error(error_msg)
            raise ResponseParsingError(error_msg) from e

    def _format_schema_instructions(self, model: Type[BaseModel], tag: str) -> str:
        schema = model.schema()
        return f"""
Return your response in <{tag}> format with valid JSON that conforms to this schema:
```json
{json.dumps(schema, indent=2)}
```

Make sure all required fields are included and properly formatted. 
The response must be valid JSON enclosed in <{tag}> tags.
"""

    @retry(stop=stop_after_attempt(3), wait=wait_random_exponential(multiplier=1, max=60))
    def _call_llm_with_retry(self, prompt: str) -> Dict[str, Any]:
        self.logger.info("Making LLM call")
        response = self.agent.generate_reply([{"content": prompt, "role": "user"}])

        if response is None:
            raise LLMInteractionError("LLM returned None response")

        if not isinstance(response, dict):
            raise LLMInteractionError(f"Expected dict response, got {type(response)}")

        content = response.get("content")
        if content is None or not isinstance(content, str):
            raise LLMInteractionError("Response is missing content or content is not a string")

        return response

    def generate_reply(
        self,
        prompt_template: str,
        response_tag: str,
        response_model: Type[BaseModel],
        auto_append_instructions: bool = True,
        **kwargs,
    ) -> BaseModel:
        prompt = self._render_template(prompt_template, **kwargs)
        self.logger.info(prompt)

        return self.generate_reply_with_raw_prompt(
            prompt=prompt,
            response_tag=response_tag,
            response_model=response_model,
            auto_append_instructions=auto_append_instructions,
        )

    def generate_reply_with_raw_prompt(
        self,
        prompt: str,
        response_tag: str,
        response_model: Type[BaseModel],
        auto_append_instructions: bool = True,
    ) -> BaseModel:
        if auto_append_instructions:
            schema_instructions = self._format_schema_instructions(response_model, response_tag)
            prompt = f"{prompt.rstrip()}\n\n{schema_instructions}"

        try:
            response = self._call_llm_with_retry(prompt)
            content = response["content"]
            json_data = self._extract_tagged_json(content, response_tag)
            return response_model.parse_obj(json_data)
        except (ResponseParsingError, ValidationError, LLMInteractionError) as e:
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error in generate_reply: {str(e)}")
            raise RuntimeError(f"Failed to generate reply: {str(e)}") from e
