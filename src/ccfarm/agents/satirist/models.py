from typing import List, Optional
from pydantic import BaseModel, Field


class SpeechSegment(BaseModel):
    text: str = Field(
        description="The speech text content with optional SSML tags for controlling delivery. "
        "Use <emphasis>, <prosody>, and <break> tags to enhance performance."
    )

    keywords: List[str] = Field(
        description="Keywords that describe the emotional content and visual elements of this segment. "
        "These will be used to fetch matching GIFs. Examples: 'shocked', 'facepalm', "
        "'eye-roll', 'sarcastic', etc. Choose 3-5 descriptive terms per segment."
    )


class ComedyScript(BaseModel):
    title: str = Field(
        description="A catchy, satirical title for the comedy piece - should be humorous "
        "and capture the essence of the original news with an ironic twist."
    )

    description: str = Field(
        description="A brief description of the satirical take on the news article. "
        "Should explain the comedic angle in 1-2 sentences."
    )

    topic_tags: List[str] = Field(
        description="List of relevant topics covered in the content (e.g., 'Politics', 'Technology', 'AI'). "
        "These help with content categorization and searchability."
    )

    segments: List[SpeechSegment] = Field(
        description="A series of 2-4 speech segments that form the satirical comedy piece. "
        "Each segment should be short, punchy, and include appropriate SSML tags."
    )
