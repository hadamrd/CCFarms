import os
from typing import List, Optional, cast
import base64
from datetime import datetime
from ccfarm.agents.illustrator.models import PromptCollection
import openai
from common.utils import get_flow_aware_logger
from ccfarm.agents.base_agent import BaseAgent

class ComicIllustrator(BaseAgent):
    """
    AI agent that generates DALL-E 3 prompts for satirical images and creates those images.
    Uses Claude for prompt generation and OpenAI for image creation.
    """
    
    def __init__(
        self,
        anthropic_api_key: str,
        openai_api_key: str,
    ):
        # Set up the directory for this agent
        self.agent_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Configure LLM settings for AutoGen with Claude
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
            name="ComicIllustrator",
            llm_config=llm_config,
            template_dir=self.agent_dir
        )
        
        self.logger = get_flow_aware_logger("ComicIllustrator")
        self.openai_api_key = openai_api_key
        
        # Initialize OpenAI client
        self.openai_client = openai.OpenAI(api_key=self.openai_api_key)
    
    def generate_dalle_prompts(self, segment_text: str) -> PromptCollection:
        """
        Generate a collection of DALL-E 3 prompts for a specific speech segment.
        
        Args:
            segment_text: The speech segment text to illustrate
            
        Returns:
            A PromptCollection with multiple DALL-E prompts
        """
        try:
            self.logger.info(f"Generating DALL-E prompts for segment")
            
            prompt_collection = cast(PromptCollection, self.generate_reply(
                prompt_template="dalle_prompt_generator.j2",
                response_tag="response",
                response_model=PromptCollection,
                segment_text=segment_text,
                date=datetime.now().strftime("%d/%m/%Y, %H:%M:%S")
            ))
            
            self.logger.info(f"Successfully generated {len(prompt_collection.prompts)} DALL-E prompts")
            return prompt_collection
            
        except Exception as e:
            self.logger.error(f"Error generating DALL-E prompts: {e}")
            raise
    
    def create_dalle_image(self, prompt: str, output_dir: str) -> Optional[str]:
        """
        Generate an image using DALL-E 3 based on the provided prompt.
        
        Args:
            prompt: The text to send to DALL-E
            output_dir: Directory to save the generated image
            
        Returns:
            Path to the saved image file, or None if generation failed
        """
        try:
            self.logger.info(f"Generating DALL-E image for segment")
            
            # Make sure output directory exists
            os.makedirs(output_dir, exist_ok=True)
            
            # Call DALL-E API
            response = self.openai_client.images.generate(
                model="dall-e-3",
                prompt=prompt,
                size="1024x1024",
                quality="standard",
                n=1,
                response_format="b64_json"
            )
            
            # Extract and save the image
            image_data = base64.b64decode(response.data[0].b64_json) # type: ignore
            
            # Create a filename with timestamp to avoid collisions
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            image_filename = f"dalle3_image_{timestamp}.png"
            image_path = os.path.join(output_dir, image_filename)
            
            # Save the image
            with open(image_path, "wb") as img_file:
                img_file.write(image_data)
            
            self.logger.info(f"Successfully saved DALL-E image to {image_path}")
            return image_path
            
        except Exception as e:
            self.logger.error(f"Error generating DALL-E image: {e}")
            return None
    
    def generate_images(self, text: str, output_dir: str) -> List[str]:
        """
        Complete workflow to generate multiple images for a speech segment.
        
        Args:
            segment_text: The speech segment text to illustrate
            segment_index: The index of the segment in the overall script
            output_dir: Directory to save the generated images
            
        Returns:
            List of paths to generated image files
        """
        # Generate prompts
        prompt_collection = self.generate_dalle_prompts(text)
        
        # Generate images for each prompt
        image_paths = []
        for prompt in prompt_collection.prompts:
            image_path = self.create_dalle_image(prompt, output_dir)
            if image_path:
                image_paths.append(image_path)
        
        self.logger.info(f"Generated {len(image_paths)} images for segment")
        return image_paths