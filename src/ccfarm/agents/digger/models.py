from pydantic import BaseModel, Field

class ArticleScore(BaseModel):
    """Pydantic model for article scoring results"""
    score: int = Field(..., ge=0, le=10, description="Comedy potential score from 0-10")
    reason: str = Field(..., description="One line explanation for the score")
