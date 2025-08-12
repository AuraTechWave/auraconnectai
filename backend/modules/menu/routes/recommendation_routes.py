from typing import Optional, List
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from core.database import get_db
from ..schemas.recommendation_schemas import (
    MenuItemRecommendation,
    RecommendationResponse,
)
from ..services.recommendation_service import MenuRecommendationService

router = APIRouter(
    prefix="/menu/recommendations",
    tags=["Menu Recommendations"],
)


@router.get("/", response_model=RecommendationResponse)
def get_menu_recommendations(
    customer_id: Optional[int] = Query(None, description="Filter recommendations for a specific customer"),
    max_results: int = Query(5, ge=1, le=50, description="Maximum number of recommendations to return"),
    db: Session = Depends(get_db),
):
    """Fetch menu item recommendations.

    Recommendations are generated based on order history. If ``customer_id`` is provided,
    the algorithm prioritises that customer's past orders before falling back to global
    popularity.
    """
    service = MenuRecommendationService(db)
    recs = service.get_recommendations(customer_id=customer_id, max_results=max_results)

    # Convert to schema objects
    recommendations: List[MenuItemRecommendation] = [
        MenuItemRecommendation(
            menu_item_id=item.id,
            name=item.name,
            description=item.description,
            price=item.price,
            score=score,
        )
        for item, score in recs
    ]

    return RecommendationResponse(recommendations=recommendations, generated_at=datetime.utcnow())