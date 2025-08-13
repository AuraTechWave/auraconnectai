from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime


class MenuItemRecommendation(BaseModel):
    menu_item_id: int
    name: str
    description: Optional[str] = None
    price: float
    score: int

    class Config:
        orm_mode = True


class RecommendationResponse(BaseModel):
    recommendations: List[MenuItemRecommendation]
    generated_at: datetime