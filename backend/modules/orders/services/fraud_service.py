from sqlalchemy.orm import Session
from fastapi import HTTPException
from typing import List, Optional, Dict
from datetime import datetime, timedelta
from decimal import Decimal
import json

from ..models.order_models import Order
from ..schemas.order_schemas import FraudCheckResponse
from ..enums.order_enums import (FraudCheckStatus, FraudRiskLevel,
                                 CheckpointType)
from backend.core.compliance import ComplianceEngine


async def perform_fraud_check(
    db: Session,
    order_id: int,
    checkpoint_types: Optional[List[CheckpointType]] = None,
    force_recheck: bool = False
) -> FraudCheckResponse:
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    if not force_recheck and order.fraud_last_check:
        time_since_check = datetime.utcnow() - order.fraud_last_check
        if time_since_check < timedelta(hours=1):
            return FraudCheckResponse(
                order_id=order_id,
                risk_score=float(order.fraud_risk_score or 0.0),
                risk_level=FraudRiskLevel(order.fraud_status or "pending"),
                status=FraudCheckStatus(order.fraud_status or "pending"),
                flags=json.loads(order.fraud_flags) if order.fraud_flags
                else [],
                checked_at=order.fraud_last_check
            )

    if not checkpoint_types:
        checkpoint_types = [
            CheckpointType.VOLUME_CHECK,
            CheckpointType.PRICE_CHECK,
            CheckpointType.TIMING_CHECK,
            CheckpointType.PATTERN_CHECK
        ]

    risk_score = 0.0
    flags = []

    for checkpoint in checkpoint_types:
        check_result = await _perform_individual_check(db, order, checkpoint)
        risk_score += check_result["score"]
        if check_result["flags"]:
            flags.extend(check_result["flags"])

    risk_level = _calculate_risk_level(risk_score)
    status = _determine_status(risk_level)

    order.fraud_risk_score = Decimal(str(risk_score))
    order.fraud_status = status.value
    order.fraud_last_check = datetime.utcnow()
    order.fraud_flags = json.dumps(flags) if flags else None

    compliance_engine = ComplianceEngine(db)
    compliance_engine.validate_fraud_check(
        {"id": order_id, "status": order.status},
        risk_score
    )

    db.commit()

    return FraudCheckResponse(
        order_id=order_id,
        risk_score=risk_score,
        risk_level=risk_level,
        status=status,
        flags=flags,
        checked_at=order.fraud_last_check
    )


async def _perform_individual_check(
    db: Session,
    order: Order,
    checkpoint: CheckpointType
) -> Dict:
    if checkpoint == CheckpointType.VOLUME_CHECK:
        return await _check_volume_patterns(db, order)
    elif checkpoint == CheckpointType.PRICE_CHECK:
        return await _check_price_patterns(db, order)
    elif checkpoint == CheckpointType.TIMING_CHECK:
        return await _check_timing_patterns(db, order)
    elif checkpoint == CheckpointType.PATTERN_CHECK:
        return await _check_suspicious_patterns(db, order)

    return {"score": 0.0, "flags": []}


async def _check_volume_patterns(db: Session, order: Order) -> Dict:
    flags = []
    score = 0.0

    total_items = sum(item.quantity for item in order.order_items)
    if total_items > 20:
        flags.append("High volume order (>20 items)")
        score += 15.0
    elif total_items > 10:
        flags.append("Medium volume order (>10 items)")
        score += 5.0

    for item in order.order_items:
        if item.quantity > 10:
            flags.append(f"High quantity single item: {item.quantity}")
            score += 10.0

    return {"score": score, "flags": flags}


async def _check_price_patterns(db: Session, order: Order) -> Dict:
    flags = []
    score = 0.0

    total_value = sum(float(item.price) * item.quantity
                      for item in order.order_items)

    if total_value > 1000:
        flags.append(f"High value order: ${total_value:.2f}")
        score += 20.0
    elif total_value > 500:
        flags.append(f"Medium value order: ${total_value:.2f}")
        score += 10.0

    for item in order.order_items:
        if float(item.price) < 1.0:
            flags.append(f"Unusually low price: ${item.price}")
            score += 15.0

    return {"score": score, "flags": flags}


async def _check_timing_patterns(db: Session, order: Order) -> Dict:
    flags = []
    score = 0.0

    order_hour = order.created_at.hour
    if order_hour < 6 or order_hour > 23:
        flags.append(f"Order placed at unusual hour: {order_hour}:00")
        score += 5.0

    recent_orders = db.query(Order).filter(
        Order.staff_id == order.staff_id,
        Order.created_at > order.created_at - timedelta(minutes=10),
        Order.id != order.id
    ).count()

    if recent_orders > 3:
        flags.append(f"Multiple orders from same staff in 10 minutes: "
                     f"{recent_orders}")
        score += 10.0

    return {"score": score, "flags": flags}


async def _check_suspicious_patterns(db: Session, order: Order) -> Dict:
    flags = []
    score = 0.0

    if order.table_no is None:
        flags.append("No table number specified")
        score += 3.0

    excessive_notes = sum(1 for item in order.order_items
                          if item.notes and len(item.notes) > 100)
    if excessive_notes > 0:
        flags.append(f"Items with excessive notes: {excessive_notes}")
        score += 5.0

    return {"score": score, "flags": flags}


def _calculate_risk_level(risk_score: float) -> FraudRiskLevel:
    if risk_score >= 50:
        return FraudRiskLevel.CRITICAL
    elif risk_score >= 30:
        return FraudRiskLevel.HIGH
    elif risk_score >= 15:
        return FraudRiskLevel.MEDIUM
    else:
        return FraudRiskLevel.LOW


def _determine_status(risk_level: FraudRiskLevel) -> FraudCheckStatus:
    if risk_level == FraudRiskLevel.CRITICAL:
        return FraudCheckStatus.FAILED
    elif risk_level == FraudRiskLevel.HIGH:
        return FraudCheckStatus.MANUAL_REVIEW
    else:
        return FraudCheckStatus.PASSED


async def get_fraud_alerts(
    db: Session,
    resolved: Optional[bool] = None,
    severity: Optional[FraudRiskLevel] = None,
    limit: int = 100,
    offset: int = 0
) -> List[Dict]:
    return []


async def resolve_fraud_alert(db: Session, alert_id: int) -> Dict:
    return {"message": "Alert resolved", "alert_id": alert_id}
