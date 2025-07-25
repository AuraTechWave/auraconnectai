from sqlalchemy.orm import Session
from typing import List, Optional
from ..services.fraud_service import (
    perform_fraud_check, get_fraud_alerts, resolve_fraud_alert
)
from ..schemas.order_schemas import (
    FraudCheckRequest, FraudCheckResponse
)
from ..enums.order_enums import FraudRiskLevel


async def check_order_fraud(
    fraud_request: FraudCheckRequest,
    db: Session
) -> FraudCheckResponse:
    return await perform_fraud_check(
        db,
        fraud_request.order_id,
        fraud_request.checkpoint_types,
        fraud_request.force_recheck
    )


async def list_fraud_alerts(
    db: Session,
    resolved: Optional[bool] = None,
    severity: Optional[FraudRiskLevel] = None,
    limit: int = 100,
    offset: int = 0
) -> List[dict]:
    return await get_fraud_alerts(db, resolved, severity, limit, offset)


async def resolve_alert(db: Session, alert_id: int) -> dict:
    return await resolve_fraud_alert(db, alert_id)
