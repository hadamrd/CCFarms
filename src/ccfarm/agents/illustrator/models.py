from pydantic import BaseModel, Field

class PromptCollection(BaseModel):
    """Collection of DALL-E prompts for a speech segment."""
    prompts: list[str] = Field(
        description="A list of 3-5 satirical, caricature-style DALL-E prompts that capture "
        "different aspects or moments of the speech segment."
    )