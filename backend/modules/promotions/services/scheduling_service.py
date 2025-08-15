# backend/modules/promotions/services/scheduling_service.py

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, timedelta
import logging
import asyncio
from croniter import croniter

from ..models.promotion_models import Promotion, PromotionStatus, PromotionRule
from ..schemas.promotion_schemas import PromotionCreate, PromotionUpdate
from ..services.promotion_service import PromotionService

logger = logging.getLogger(__name__)


class PromotionSchedulingService:
    """Service for scheduling and automating promotion lifecycle"""

    def __init__(self, db: Session):
        self.db = db
        self.promotion_service = PromotionService(db)

    def schedule_promotion(
        self, promotion_data: PromotionCreate, schedule_options: Dict[str, Any]
    ) -> Promotion:
        """
        Schedule a promotion with advanced scheduling options

        Args:
            promotion_data: Promotion creation data
            schedule_options: Scheduling configuration
                - recurrence_pattern: daily, weekly, monthly, custom
                - recurrence_interval: Interval for recurrence
                - recurrence_days: Days of week/month for recurrence
                - max_occurrences: Maximum number of occurrences
                - auto_activate: Automatically activate when start time is reached
                - auto_deactivate: Automatically deactivate at end time

        Returns:
            Created promotion with scheduling metadata
        """
        try:
            # Create the promotion with scheduled status
            promotion = self.promotion_service.create_promotion(promotion_data)

            # Set initial status based on scheduling
            now = datetime.utcnow()
            if promotion_data.start_date > now:
                promotion.status = PromotionStatus.SCHEDULED
            elif schedule_options.get("auto_activate", True):
                promotion.status = PromotionStatus.ACTIVE
            else:
                promotion.status = PromotionStatus.DRAFT

            # Store scheduling metadata
            if not promotion.metadata:
                promotion.metadata = {}

            promotion.metadata["scheduling"] = {
                "created_at": now.isoformat(),
                "schedule_options": schedule_options,
                "next_occurrence": self._calculate_next_occurrence(
                    promotion_data.start_date, schedule_options
                ),
                "occurrences_count": 0,
                "last_processed": None,
            }

            self.db.commit()
            self.db.refresh(promotion)

            logger.info(f"Scheduled promotion: {promotion.name} (ID: {promotion.id})")
            return promotion

        except Exception as e:
            self.db.rollback()
            logger.error(f"Error scheduling promotion: {str(e)}")
            raise

    def _calculate_next_occurrence(
        self, start_date: datetime, schedule_options: Dict[str, Any]
    ) -> Optional[str]:
        """Calculate next occurrence based on recurrence pattern"""

        pattern = schedule_options.get("recurrence_pattern")
        if not pattern or pattern == "none":
            return None

        now = datetime.utcnow()
        base_date = max(start_date, now)

        if pattern == "daily":
            interval = schedule_options.get("recurrence_interval", 1)
            next_date = base_date + timedelta(days=interval)

        elif pattern == "weekly":
            interval = schedule_options.get("recurrence_interval", 1)
            days_of_week = schedule_options.get("recurrence_days", [])

            if days_of_week:
                # Find next occurrence on specified days
                next_date = self._find_next_weekday(base_date, days_of_week, interval)
            else:
                next_date = base_date + timedelta(weeks=interval)

        elif pattern == "monthly":
            interval = schedule_options.get("recurrence_interval", 1)
            days_of_month = schedule_options.get("recurrence_days", [])

            if days_of_month:
                next_date = self._find_next_monthday(base_date, days_of_month, interval)
            else:
                # Same day next month
                next_date = self._add_months(base_date, interval)

        elif pattern == "custom":
            # Use cron expression
            cron_expr = schedule_options.get("cron_expression")
            if cron_expr:
                cron = croniter(cron_expr, base_date)
                next_date = cron.get_next(datetime)
            else:
                return None
        else:
            return None

        return next_date.isoformat() if next_date else None

    def _find_next_weekday(
        self, start_date: datetime, days_of_week: List[int], week_interval: int
    ) -> datetime:
        """Find next occurrence on specified weekdays"""
        current = start_date
        weeks_added = 0

        while True:
            if current.weekday() in days_of_week and current > start_date:
                if weeks_added % week_interval == 0:
                    return current

            current += timedelta(days=1)
            if current.weekday() == 0:  # Monday
                weeks_added += 1

    def _find_next_monthday(
        self, start_date: datetime, days_of_month: List[int], month_interval: int
    ) -> datetime:
        """Find next occurrence on specified days of month"""
        current = start_date
        months_added = 0

        while True:
            if current.day in days_of_month and current > start_date:
                if months_added % month_interval == 0:
                    return current

            current += timedelta(days=1)
            if current.day == 1:
                months_added += 1

    def _add_months(self, date: datetime, months: int) -> datetime:
        """Add months to a date, handling edge cases"""
        month = date.month - 1 + months
        year = date.year + month // 12
        month = month % 12 + 1
        day = min(
            date.day,
            [
                31,
                29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28,
                31,
                30,
                31,
                30,
                31,
                31,
                30,
                31,
                30,
                31,
            ][month - 1],
        )

        return date.replace(year=year, month=month, day=day)

    async def process_scheduled_promotions(self) -> Dict[str, Any]:
        """Process all scheduled promotions and update their status"""

        try:
            now = datetime.utcnow()
            results = {
                "activated": [],
                "deactivated": [],
                "scheduled": [],
                "errors": [],
            }

            # Find promotions to activate
            promotions_to_activate = (
                self.db.query(Promotion)
                .filter(
                    Promotion.status == PromotionStatus.SCHEDULED,
                    Promotion.start_date <= now,
                    Promotion.end_date > now,
                )
                .all()
            )

            for promotion in promotions_to_activate:
                try:
                    metadata = promotion.metadata or {}
                    scheduling = metadata.get("scheduling", {})

                    if scheduling.get("schedule_options", {}).get(
                        "auto_activate", True
                    ):
                        promotion.status = PromotionStatus.ACTIVE
                        results["activated"].append(
                            {"id": promotion.id, "name": promotion.name}
                        )

                        logger.info(f"Activated scheduled promotion: {promotion.name}")
                except Exception as e:
                    logger.error(f"Error activating promotion {promotion.id}: {str(e)}")
                    results["errors"].append(
                        {"promotion_id": promotion.id, "error": str(e)}
                    )

            # Find promotions to deactivate
            promotions_to_deactivate = (
                self.db.query(Promotion)
                .filter(
                    Promotion.status == PromotionStatus.ACTIVE,
                    Promotion.end_date <= now,
                )
                .all()
            )

            for promotion in promotions_to_deactivate:
                try:
                    metadata = promotion.metadata or {}
                    scheduling = metadata.get("scheduling", {})

                    if scheduling.get("schedule_options", {}).get(
                        "auto_deactivate", True
                    ):
                        promotion.status = PromotionStatus.ENDED
                        results["deactivated"].append(
                            {"id": promotion.id, "name": promotion.name}
                        )

                        # Check for recurrence
                        if await self._handle_recurrence(promotion):
                            results["scheduled"].append(
                                {
                                    "id": promotion.id,
                                    "name": promotion.name,
                                    "next_occurrence": promotion.metadata["scheduling"][
                                        "next_occurrence"
                                    ],
                                }
                            )

                        logger.info(f"Deactivated expired promotion: {promotion.name}")
                except Exception as e:
                    logger.error(
                        f"Error deactivating promotion {promotion.id}: {str(e)}"
                    )
                    results["errors"].append(
                        {"promotion_id": promotion.id, "error": str(e)}
                    )

            self.db.commit()

            logger.info(
                f"Processed scheduled promotions: {len(results['activated'])} activated, "
                f"{len(results['deactivated'])} deactivated"
            )

            return results

        except Exception as e:
            self.db.rollback()
            logger.error(f"Error processing scheduled promotions: {str(e)}")
            raise

    async def _handle_recurrence(self, promotion: Promotion) -> bool:
        """Handle recurring promotion scheduling"""

        metadata = promotion.metadata or {}
        scheduling = metadata.get("scheduling", {})
        schedule_options = scheduling.get("schedule_options", {})

        if (
            not schedule_options.get("recurrence_pattern")
            or schedule_options["recurrence_pattern"] == "none"
        ):
            return False

        # Check max occurrences
        occurrences_count = scheduling.get("occurrences_count", 0) + 1
        max_occurrences = schedule_options.get("max_occurrences")

        if max_occurrences and occurrences_count >= max_occurrences:
            logger.info(
                f"Promotion {promotion.id} reached max occurrences ({max_occurrences})"
            )
            return False

        # Calculate next occurrence
        next_occurrence = self._calculate_next_occurrence(
            datetime.utcnow(), schedule_options
        )

        if not next_occurrence:
            return False

        # Create new occurrence
        next_start = datetime.fromisoformat(next_occurrence)
        duration = promotion.end_date - promotion.start_date
        next_end = next_start + duration

        # Update promotion for next occurrence
        promotion.start_date = next_start
        promotion.end_date = next_end
        promotion.status = PromotionStatus.SCHEDULED

        # Update metadata
        scheduling["occurrences_count"] = occurrences_count
        scheduling["last_processed"] = datetime.utcnow().isoformat()
        scheduling["next_occurrence"] = next_occurrence

        promotion.metadata["scheduling"] = scheduling

        return True

    def create_time_based_promotion(
        self, promotion_data: PromotionCreate, time_rules: List[Dict[str, Any]]
    ) -> Promotion:
        """
        Create a promotion with time-based activation rules

        Args:
            promotion_data: Base promotion data
            time_rules: List of time-based rules
                - type: 'hour_of_day', 'day_of_week', 'date_range', 'special_event'
                - conditions: Specific conditions for each rule type

        Returns:
            Created promotion with time rules
        """
        try:
            # Create the promotion
            promotion = self.promotion_service.create_promotion(promotion_data)

            # Add time-based rules
            for rule_data in time_rules:
                rule = PromotionRule(
                    promotion_id=promotion.id,
                    rule_type="time_based",
                    condition_type=rule_data["type"],
                    condition_value=rule_data["conditions"],
                    action_type="activate",
                    action_value={"status": "active"},
                    is_active=True,
                )
                self.db.add(rule)

            self.db.commit()
            self.db.refresh(promotion)

            logger.info(
                f"Created time-based promotion: {promotion.name} with {len(time_rules)} rules"
            )
            return promotion

        except Exception as e:
            self.db.rollback()
            logger.error(f"Error creating time-based promotion: {str(e)}")
            raise

    def evaluate_time_based_rules(self, promotion_id: int) -> Tuple[bool, str]:
        """
        Evaluate time-based rules for a promotion

        Args:
            promotion_id: Promotion to evaluate

        Returns:
            Tuple of (should_be_active, reason)
        """
        try:
            rules = (
                self.db.query(PromotionRule)
                .filter(
                    PromotionRule.promotion_id == promotion_id,
                    PromotionRule.rule_type == "time_based",
                    PromotionRule.is_active == True,
                )
                .all()
            )

            if not rules:
                return True, "No time-based rules"

            now = datetime.utcnow()

            for rule in rules:
                condition_type = rule.condition_type
                conditions = rule.condition_value or {}

                if condition_type == "hour_of_day":
                    start_hour = conditions.get("start_hour", 0)
                    end_hour = conditions.get("end_hour", 24)
                    current_hour = now.hour

                    if not (start_hour <= current_hour < end_hour):
                        return (
                            False,
                            f"Outside active hours ({start_hour}:00 - {end_hour}:00)",
                        )

                elif condition_type == "day_of_week":
                    active_days = conditions.get("days", [])
                    current_day = now.weekday()

                    if current_day not in active_days:
                        return False, f"Not active on {now.strftime('%A')}"

                elif condition_type == "date_range":
                    start_date = datetime.fromisoformat(conditions.get("start_date"))
                    end_date = datetime.fromisoformat(conditions.get("end_date"))

                    if not (start_date <= now <= end_date):
                        return False, f"Outside date range"

                elif condition_type == "special_event":
                    event_dates = conditions.get("event_dates", [])
                    today = now.date().isoformat()

                    if today not in event_dates:
                        return False, f"Not a special event day"

            return True, "All time-based rules satisfied"

        except Exception as e:
            logger.error(f"Error evaluating time-based rules: {str(e)}")
            return True, f"Error evaluating rules: {str(e)}"

    async def process_time_based_promotions(self) -> Dict[str, Any]:
        """Process all promotions with time-based rules"""

        try:
            results = {"evaluated": 0, "activated": [], "deactivated": [], "errors": []}

            # Get all promotions with time-based rules
            promotions_with_rules = (
                self.db.query(Promotion)
                .join(PromotionRule)
                .filter(
                    PromotionRule.rule_type == "time_based",
                    PromotionRule.is_active == True,
                )
                .distinct()
                .all()
            )

            for promotion in promotions_with_rules:
                try:
                    results["evaluated"] += 1

                    should_be_active, reason = self.evaluate_time_based_rules(
                        promotion.id
                    )

                    if should_be_active and promotion.status != PromotionStatus.ACTIVE:
                        promotion.status = PromotionStatus.ACTIVE
                        results["activated"].append(
                            {
                                "id": promotion.id,
                                "name": promotion.name,
                                "reason": reason,
                            }
                        )

                    elif (
                        not should_be_active
                        and promotion.status == PromotionStatus.ACTIVE
                    ):
                        promotion.status = PromotionStatus.PAUSED
                        results["deactivated"].append(
                            {
                                "id": promotion.id,
                                "name": promotion.name,
                                "reason": reason,
                            }
                        )

                except Exception as e:
                    logger.error(f"Error processing promotion {promotion.id}: {str(e)}")
                    results["errors"].append(
                        {"promotion_id": promotion.id, "error": str(e)}
                    )

            self.db.commit()

            return results

        except Exception as e:
            self.db.rollback()
            logger.error(f"Error processing time-based promotions: {str(e)}")
            raise

    def create_automated_promotion_sequence(
        self,
        sequence_name: str,
        promotions: List[Dict[str, Any]],
        trigger_conditions: Dict[str, Any],
    ) -> List[Promotion]:
        """
        Create a sequence of automated promotions

        Args:
            sequence_name: Name for the promotion sequence
            promotions: List of promotion configurations with timing
            trigger_conditions: Conditions to trigger the sequence

        Returns:
            List of created promotions
        """
        try:
            created_promotions = []
            sequence_id = f"seq_{datetime.utcnow().timestamp()}"

            for idx, promo_config in enumerate(promotions):
                promotion_data = PromotionCreate(**promo_config["data"])

                # Add sequence metadata
                if not promotion_data.metadata:
                    promotion_data.metadata = {}

                promotion_data.metadata["sequence"] = {
                    "sequence_id": sequence_id,
                    "sequence_name": sequence_name,
                    "position": idx,
                    "trigger_conditions": trigger_conditions,
                    "delay_after_previous": promo_config.get("delay_after_previous", 0),
                    "depends_on": promo_config.get("depends_on", []),
                }

                promotion = self.promotion_service.create_promotion(promotion_data)
                created_promotions.append(promotion)

            logger.info(
                f"Created promotion sequence '{sequence_name}' with {len(created_promotions)} promotions"
            )
            return created_promotions

        except Exception as e:
            self.db.rollback()
            logger.error(f"Error creating promotion sequence: {str(e)}")
            raise

    def get_scheduled_promotions(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        include_recurring: bool = True,
    ) -> List[Dict[str, Any]]:
        """Get all scheduled promotions within a date range"""

        try:
            query = self.db.query(Promotion).filter(
                Promotion.status.in_([PromotionStatus.SCHEDULED, PromotionStatus.DRAFT])
            )

            if start_date:
                query = query.filter(Promotion.start_date >= start_date)
            if end_date:
                query = query.filter(Promotion.start_date <= end_date)

            promotions = query.all()

            scheduled_list = []
            for promotion in promotions:
                metadata = promotion.metadata or {}
                scheduling = metadata.get("scheduling", {})

                scheduled_info = {
                    "id": promotion.id,
                    "name": promotion.name,
                    "start_date": promotion.start_date.isoformat(),
                    "end_date": promotion.end_date.isoformat(),
                    "status": promotion.status,
                    "is_recurring": bool(
                        scheduling.get("schedule_options", {}).get("recurrence_pattern")
                    ),
                    "next_occurrence": scheduling.get("next_occurrence"),
                    "occurrences_count": scheduling.get("occurrences_count", 0),
                }

                if include_recurring or not scheduled_info["is_recurring"]:
                    scheduled_list.append(scheduled_info)

            return sorted(scheduled_list, key=lambda x: x["start_date"])

        except Exception as e:
            logger.error(f"Error getting scheduled promotions: {str(e)}")
            raise

    def cancel_scheduled_promotion(
        self, promotion_id: int, cancel_future_occurrences: bool = True
    ) -> bool:
        """Cancel a scheduled promotion"""

        try:
            promotion = (
                self.db.query(Promotion).filter(Promotion.id == promotion_id).first()
            )

            if not promotion:
                return False

            if promotion.status not in [
                PromotionStatus.SCHEDULED,
                PromotionStatus.DRAFT,
            ]:
                raise ValueError(
                    f"Cannot cancel promotion with status {promotion.status}"
                )

            promotion.status = PromotionStatus.CANCELLED

            if cancel_future_occurrences and promotion.metadata:
                scheduling = promotion.metadata.get("scheduling", {})
                if scheduling:
                    scheduling["cancelled_at"] = datetime.utcnow().isoformat()
                    scheduling["cancel_future_occurrences"] = True
                    promotion.metadata["scheduling"] = scheduling

            self.db.commit()

            logger.info(f"Cancelled scheduled promotion: {promotion.id}")
            return True

        except Exception as e:
            self.db.rollback()
            logger.error(f"Error cancelling scheduled promotion: {str(e)}")
            raise
