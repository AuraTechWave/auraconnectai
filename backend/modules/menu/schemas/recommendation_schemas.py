from pydantic import BaseModel, ConfigDict
from typing import List, Optional
from datetime import datetime


class MenuItemRecommendation(BaseModel):
    menu_item_id: int
    name: str
    description: Optional[str] = None
    price: float
    score: int
    model_config = ConfigDict(from_attributes=True)

    # Custom JSON encoders need to be handled differently in v2
    # Consider using model_serializer if needed


class RecommendationResponse(BaseModel):
    recommendations: List[MenuItemRecommendation]
    generated_at: datetime
