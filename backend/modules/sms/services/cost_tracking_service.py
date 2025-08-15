# backend/modules/sms/services/cost_tracking_service.py

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, func

from modules.sms.models.sms_models import (
    SMSMessage, SMSCost, SMSProvider, SMSTemplateCategory, SMSDirection
)
from modules.sms.schemas.sms_schemas import SMSCostCreate, SMSCostSummary

logger = logging.getLogger(__name__)


class CostTrackingService:
    """Service for tracking SMS costs and billing"""
    
    # Default cost per segment (in USD)
    DEFAULT_COSTS = {
        SMSProvider.TWILIO: {
            'outbound': 0.0075,
            'inbound': 0.0075,
            'phone_number': 1.00  # Monthly cost
        },
        SMSProvider.AWS_SNS: {
            'outbound': 0.00645,
            'inbound': 0.00,
            'phone_number': 0.00
        }
    }
    
    def __init__(self, db: Session):
        self.db = db
    
    async def track_message_cost(self, message: SMSMessage) -> None:
        """
        Track cost for a single message
        
        Args:
            message: SMS message with cost information
        """
        if not message.cost_amount:
            # Estimate cost if not provided
            provider_costs = self.DEFAULT_COSTS.get(message.provider, self.DEFAULT_COSTS[SMSProvider.TWILIO])
            
            if message.direction == SMSDirection.OUTBOUND:
                message.cost_amount = provider_costs['outbound'] * message.segments_count
            else:
                message.cost_amount = provider_costs['inbound'] * message.segments_count
            
            message.cost_currency = 'USD'
            self.db.commit()
        
        logger.debug(f"Tracked cost for message {message.id}: ${message.cost_amount:.4f}")
    
    def calculate_period_costs(
        self,
        start_date: datetime,
        end_date: datetime,
        provider: Optional[SMSProvider] = None
    ) -> SMSCost:
        """
        Calculate costs for a billing period
        
        Args:
            start_date: Start of billing period
            end_date: End of billing period
            provider: Specific provider (None for all)
        
        Returns:
            SMSCost record with calculated costs
        """
        # Query messages for the period
        query = self.db.query(SMSMessage).filter(
            and_(
                SMSMessage.created_at >= start_date,
                SMSMessage.created_at <= end_date
            )
        )
        
        if provider:
            query = query.filter(SMSMessage.provider == provider)
        
        messages = query.all()
        
        # Calculate totals
        total_messages = len(messages)
        total_segments = sum(m.segments_count for m in messages)
        
        outbound_messages = [m for m in messages if m.direction == SMSDirection.OUTBOUND]
        inbound_messages = [m for m in messages if m.direction == SMSDirection.INBOUND]
        
        outbound_cost = sum(m.cost_amount or 0 for m in outbound_messages)
        inbound_cost = sum(m.cost_amount or 0 for m in inbound_messages)
        
        # Calculate cost by category
        cost_by_category = {}
        for message in messages:
            if message.template and message.template.category:
                category = message.template.category.value
                if category not in cost_by_category:
                    cost_by_category[category] = {'count': 0, 'cost': 0}
                cost_by_category[category]['count'] += 1
                cost_by_category[category]['cost'] += message.cost_amount or 0
        
        # Calculate phone number costs (estimated monthly cost prorated)
        days_in_period = (end_date - start_date).days
        phone_number_cost = 0
        
        if provider:
            provider_costs = self.DEFAULT_COSTS.get(provider, self.DEFAULT_COSTS[SMSProvider.TWILIO])
            phone_number_cost = (provider_costs['phone_number'] / 30) * days_in_period
        
        total_cost = outbound_cost + inbound_cost + phone_number_cost
        
        # Check if cost record exists for this period
        existing_cost = self.db.query(SMSCost).filter(
            and_(
                SMSCost.billing_period_start == start_date,
                SMSCost.billing_period_end == end_date,
                SMSCost.provider == provider if provider else True
            )
        ).first()
        
        if existing_cost:
            # Update existing record
            existing_cost.total_messages = total_messages
            existing_cost.total_segments = total_segments
            existing_cost.outbound_cost = outbound_cost
            existing_cost.inbound_cost = inbound_cost
            existing_cost.phone_number_cost = phone_number_cost
            existing_cost.total_cost = total_cost
            existing_cost.cost_by_category = cost_by_category
            self.db.commit()
            self.db.refresh(existing_cost)
            return existing_cost
        
        # Create new cost record
        cost_record = SMSCost(
            billing_period_start=start_date,
            billing_period_end=end_date,
            provider=provider or SMSProvider.TWILIO,
            total_messages=total_messages,
            total_segments=total_segments,
            outbound_cost=outbound_cost,
            inbound_cost=inbound_cost,
            phone_number_cost=phone_number_cost,
            total_cost=total_cost,
            currency='USD',
            cost_by_category=cost_by_category
        )
        
        self.db.add(cost_record)
        self.db.commit()
        self.db.refresh(cost_record)
        
        logger.info(f"Calculated costs for period {start_date} to {end_date}: ${total_cost:.2f}")
        return cost_record
    
    def get_cost_summary(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> SMSCostSummary:
        """
        Get cost summary for a period
        
        Args:
            start_date: Start of period
            end_date: End of period
        
        Returns:
            Cost summary with totals and breakdown
        """
        # Get or calculate cost records
        cost_records = self.db.query(SMSCost).filter(
            and_(
                SMSCost.billing_period_start >= start_date,
                SMSCost.billing_period_end <= end_date
            )
        ).all()
        
        if not cost_records:
            # Calculate costs if not already done
            cost_record = self.calculate_period_costs(start_date, end_date)
            cost_records = [cost_record]
        
        # Aggregate totals
        total_messages = sum(r.total_messages for r in cost_records)
        total_segments = sum(r.total_segments for r in cost_records)
        total_cost = sum(r.total_cost for r in cost_records)
        
        # Cost by provider
        cost_by_provider = {}
        for record in cost_records:
            provider = record.provider.value
            if provider not in cost_by_provider:
                cost_by_provider[provider] = 0
            cost_by_provider[provider] += record.total_cost
        
        # Aggregate cost by category
        cost_by_category = {}
        for record in cost_records:
            if record.cost_by_category:
                for category, data in record.cost_by_category.items():
                    if category not in cost_by_category:
                        cost_by_category[category] = {'count': 0, 'cost': 0}
                    cost_by_category[category]['count'] += data['count']
                    cost_by_category[category]['cost'] += data['cost']
        
        # Calculate comparison to previous period
        period_length = (end_date - start_date).days
        previous_start = start_date - timedelta(days=period_length)
        previous_end = start_date
        
        previous_records = self.db.query(SMSCost).filter(
            and_(
                SMSCost.billing_period_start >= previous_start,
                SMSCost.billing_period_end <= previous_end
            )
        ).all()
        
        comparison = None
        if previous_records:
            previous_total = sum(r.total_cost for r in previous_records)
            previous_messages = sum(r.total_messages for r in previous_records)
            
            comparison = {
                'cost_change': total_cost - previous_total,
                'cost_change_percent': ((total_cost - previous_total) / previous_total * 100) if previous_total > 0 else 0,
                'message_change': total_messages - previous_messages,
                'message_change_percent': ((total_messages - previous_messages) / previous_messages * 100) if previous_messages > 0 else 0
            }
        
        return SMSCostSummary(
            period_start=start_date,
            period_end=end_date,
            total_messages=total_messages,
            total_segments=total_segments,
            total_cost=total_cost,
            currency='USD',
            cost_by_provider=cost_by_provider,
            cost_by_category=cost_by_category,
            average_cost_per_message=total_cost / total_messages if total_messages > 0 else 0,
            comparison_to_previous=comparison
        )
    
    def mark_as_paid(
        self,
        cost_id: int,
        payment_reference: str,
        paid_at: Optional[datetime] = None
    ) -> SMSCost:
        """
        Mark a cost record as paid
        
        Args:
            cost_id: ID of the cost record
            payment_reference: Payment reference number
            paid_at: Payment timestamp (default: now)
        
        Returns:
            Updated cost record
        """
        cost_record = self.db.query(SMSCost).filter(
            SMSCost.id == cost_id
        ).first()
        
        if not cost_record:
            raise ValueError(f"Cost record {cost_id} not found")
        
        cost_record.is_paid = True
        cost_record.paid_at = paid_at or datetime.utcnow()
        cost_record.payment_reference = payment_reference
        
        self.db.commit()
        self.db.refresh(cost_record)
        
        logger.info(f"Marked cost record {cost_id} as paid: {payment_reference}")
        return cost_record
    
    def get_unpaid_costs(self) -> List[SMSCost]:
        """Get all unpaid cost records"""
        return self.db.query(SMSCost).filter(
            SMSCost.is_paid == False
        ).order_by(SMSCost.billing_period_start).all()
    
    def generate_billing_report(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Any]:
        """
        Generate detailed billing report
        
        Args:
            start_date: Start of reporting period
            end_date: End of reporting period
        
        Returns:
            Detailed billing report
        """
        cost_summary = self.get_cost_summary(start_date, end_date)
        
        # Get message statistics
        messages = self.db.query(SMSMessage).filter(
            and_(
                SMSMessage.created_at >= start_date,
                SMSMessage.created_at <= end_date
            )
        ).all()
        
        # Calculate delivery statistics
        delivered = sum(1 for m in messages if m.status.value == 'delivered')
        failed = sum(1 for m in messages if m.status.value in ['failed', 'undelivered'])
        
        # Calculate average response time
        response_times = []
        for message in messages:
            if message.sent_at and message.delivered_at:
                response_time = (message.delivered_at - message.sent_at).total_seconds()
                response_times.append(response_time)
        
        avg_response_time = sum(response_times) / len(response_times) if response_times else 0
        
        # Top customers by usage
        customer_usage = {}
        for message in messages:
            if message.customer_id:
                if message.customer_id not in customer_usage:
                    customer_usage[message.customer_id] = {'count': 0, 'cost': 0}
                customer_usage[message.customer_id]['count'] += 1
                customer_usage[message.customer_id]['cost'] += message.cost_amount or 0
        
        top_customers = sorted(
            customer_usage.items(),
            key=lambda x: x[1]['cost'],
            reverse=True
        )[:10]
        
        return {
            'period': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat()
            },
            'summary': cost_summary.dict(),
            'statistics': {
                'total_messages': cost_summary.total_messages,
                'delivered': delivered,
                'failed': failed,
                'delivery_rate': (delivered / cost_summary.total_messages * 100) if cost_summary.total_messages > 0 else 0,
                'average_response_time': avg_response_time,
                'average_segments_per_message': cost_summary.total_segments / cost_summary.total_messages if cost_summary.total_messages > 0 else 1
            },
            'top_customers': [
                {
                    'customer_id': customer_id,
                    'message_count': data['count'],
                    'total_cost': data['cost']
                }
                for customer_id, data in top_customers
            ]
        }