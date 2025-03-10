from typing import List, Optional
from pydantic import BaseModel, Field

class SpeechSegment(BaseModel):
    """Simple speech segment with minimal voice parameters"""
    text: str = Field(
        ...,
        description="Clean speech text without stage directions or formatting"
    )
    
    tone: str = Field(
        "neutral",
        description="Basic emotional tone (neutral, excited, serious, funny, etc.)"
    )
    
    speed: float = Field(
        1.0,
        description="Speech rate multiplier (default: 1.0)"
    )
    
    pause_after: float = Field(
        0.0,
        description="Seconds to pause after this segment"
    )

class ComedyScript(BaseModel):
    """Simplified model for a voice-ready comedy script"""
    title: str = Field(
        ..., 
        description="Title for the comedy segment"
    )
    
    description: str = Field(
        ..., 
        description="Brief description of the comedy segment"
    )
    
    segments: List[SpeechSegment] = Field(
        ...,
        description="List of speech segments with minimal voice parameters"
    )