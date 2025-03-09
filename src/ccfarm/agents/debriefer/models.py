from typing import List, Optional
from pydantic import BaseModel, Field

class ComedyAngle(BaseModel):
    """Pydantic model for a specific comedy approach with a sample line"""
    approach: str = Field(..., description="A specific comedic approach or angle to take with the news story")
    sample_line: str = Field(..., description="An example joke or line using this comedic approach")

class ArticleAnalysis(BaseModel):
    """Pydantic model for the complete news analysis with comedy potential evaluation"""
    title: str = Field(..., description="Original title of the news article")
    
    satirical_headlines: Optional[List[str]] = Field(
        default=None, 
        max_items=3,
        description="Up to 3 alternative satirical headlines for the news story"
    )
    
    summary: str = Field(..., description="Brief, objective summary of the news article's content")
    
    core_absurdity: str = Field(
        ..., 
        description="The central absurd, ironic, or contradictory element that makes this news story comedically interesting"
    )
    
    key_points: Optional[List[str]] = Field(
        default=None, 
        max_items=5,
        description="Up to 5 key factual points from the article that could be used in comedy"
    )
    
    comedy_potential: int = Field(
        ..., 
        ge=1,
        le=10,
        description="Rating from 1-10 of how much comedy potential this news story has"
    )
    
    comedy_angles: List[ComedyAngle] = Field(
        ..., 
        max_items=3,
        description="Up to 3 different comedic approaches to take with this news story"
    )
    
    target_audience: Optional[str] = Field(
        default=None, 
        description="The ideal audience demographic or type for comedy based on this story"
    )
    
    sensitive_elements: Optional[str] = Field(
        default=None, 
        description="Any potentially sensitive or controversial elements to be aware of when using this story"
    )
    
    news_category: str = Field(
        ..., 
        description="The general category of news this story belongs to (politics, tech, sports, etc.)"
    )