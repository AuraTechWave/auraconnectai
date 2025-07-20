from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from backend.core.database import get_db
from ..controllers.order_controller import get_order_by_id
from ..schemas.order_schemas import OrderOut

router = APIRouter(prefix="/orders", tags=["Orders"])


@router.get("/{id}", response_model=OrderOut)
def get_order(id: int, db: Session = Depends(get_db)):
    return get_order_by_id(db, id)
