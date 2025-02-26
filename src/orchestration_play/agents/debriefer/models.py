from typing import Dict, List
from autogen import AssistantAgent
from pydantic import BaseModel, Field

class ComedyPotential(BaseModel):
    """Identified comedy elements in an article"""
    absurdity_score: int  # 1-10 how absurd is this
    tech_buzzwords: List[str]  # Overused tech terms that could be mocked
    exaggerations: List[str]  # Claims that seem overblown
    contrasts: List[str]  # Ironic or contradictory elements
    numbers_to_mock: List[Dict[str, str]]  # Funding amounts, metrics etc worth joking about
    pop_culture_hooks: List[str]  # References that could be used (Black Mirror etc)
    callback_hooks: List[str]  # Elements that could be referenced later

class CoreStory(BaseModel):
    """Main story elements for comedy analysis"""
    simple_summary: str = Field(..., description="One sentence explanation of what happened")
    who: List[str] = Field(..., description="Key people/companies involved")
    what_they_claim: str = Field(..., description="Main thing they're saying/promising")
    reality_check: str = Field(..., description="Why this is ridiculous/ironic")

class JuicyDetails(BaseModel):
    """Detailed elements for comedy writing"""
    best_quotes: List[str] = Field(..., description="2-3 most outrageous quotes")
    big_numbers: List[str] = Field(..., description="Any laughably large/small numbers with context")
    tech_buzzwords: List[str] = Field(..., description="Pretentious/overused terms they used")
    grandiose_claims: List[str] = Field(..., description="Their most overblown statements")

class ComedyAngles(BaseModel):
    """Comedy approaches for the article"""
    main_irony: str = Field(..., description="Core contradictory/hypocritical element")
    industry_parallel: str = Field(..., description="Similar thing other tech companies do")
    pop_culture_ref: str = Field(..., description="What movie/show plot this resembles")
    recurring_themes: List[str] = Field(..., description="Tech industry patterns this fits into")

class ArticleBrief(BaseModel):
    """Detailed comedy analysis of an article"""
    core_story: CoreStory
    juicy_details: JuicyDetails
    comedy_angles: ComedyAngles
