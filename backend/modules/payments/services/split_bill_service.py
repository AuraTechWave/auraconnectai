# backend/modules/payments/services/split_bill_service.py

import logging
from typing import Dict, Any, Optional, List, Tuple
from decimal import Decimal
from datetime import datetime, timedelta
import secrets
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func
from sqlalchemy.orm import selectinload

from core.database import get_db
from core.cache import cache_service
from ..models.split_bill_models import (
    BillSplit, SplitParticipant, PaymentAllocation, TipDistribution,
    SplitMethod, SplitStatus, ParticipantStatus, TipMethod
)
from ..models.payment_models import Payment, PaymentStatus
from ...orders.models.order_models import Order, OrderItem
from ...customers.models.customer_models import Customer
from ...notifications.services.notification_service import notification_service

logger = logging.getLogger(__name__)


class SplitBillService:
    """
    Service for managing bill splits and participant shares
    """
    
    async def create_split(
        self,
        db: AsyncSession,
        order_id: int,
        split_method: SplitMethod,
        participants: List[Dict[str, Any]],
        organizer_info: Optional[Dict[str, Any]] = None,
        tip_method: Optional[TipMethod] = None,
        tip_value: Optional[Decimal] = None,
        split_config: Optional[Dict[str, Any]] = None,
        settings: Optional[Dict[str, Any]] = None
    ) -> BillSplit:
        """
        Create a new bill split
        
        Args:
            db: Database session
            order_id: Order to split
            split_method: How to split the bill
            participants: List of participant info dicts
            organizer_info: Organizer details
            tip_method: How to calculate tip
            tip_value: Tip percentage or amount
            split_config: Configuration for split method
            settings: Additional settings
            
        Returns:
            Created BillSplit instance
        """
        try:
            # Get order with items
            order = await db.get(Order, order_id)
            if not order:
                raise ValueError(f"Order {order_id} not found")
            
            # Calculate amounts
            subtotal = order.subtotal_amount or order.total_amount
            tax_amount = order.tax_amount or Decimal('0')
            service_charge = order.service_charge or Decimal('0')
            
            # Calculate tip
            tip_amount = self._calculate_tip_amount(
                subtotal, tip_method, tip_value
            )
            
            total_amount = subtotal + tax_amount + service_charge + tip_amount
            
            # Create split record
            bill_split = BillSplit(
                order_id=order_id,
                split_method=split_method,
                status=SplitStatus.PENDING,
                subtotal=subtotal,
                tax_amount=tax_amount,
                service_charge=service_charge,
                tip_method=tip_method,
                tip_value=tip_value,
                tip_amount=tip_amount,
                total_amount=total_amount,
                split_config=split_config or {}
            )
            
            # Set organizer info
            if organizer_info:
                bill_split.organizer_id = organizer_info.get('customer_id')
                bill_split.organizer_name = organizer_info.get('name')
                bill_split.organizer_email = organizer_info.get('email')
                bill_split.organizer_phone = organizer_info.get('phone')
            
            # Apply settings
            if settings:
                bill_split.allow_partial_payments = settings.get('allow_partial_payments', True)
                bill_split.require_all_acceptance = settings.get('require_all_acceptance', False)
                bill_split.auto_close_on_completion = settings.get('auto_close_on_completion', True)
                bill_split.send_reminders = settings.get('send_reminders', True)
                
                # Set expiration
                if 'expires_in_hours' in settings:
                    bill_split.expires_at = datetime.utcnow() + timedelta(
                        hours=settings['expires_in_hours']
                    )
            
            db.add(bill_split)
            await db.flush()
            
            # Create participants
            await self._create_participants(
                db, bill_split, participants, split_method, split_config
            )
            
            # Activate split if no acceptance required
            if not bill_split.require_all_acceptance:
                bill_split.status = SplitStatus.ACTIVE
            
            await db.commit()
            
            # Send invitations
            await self._send_participant_invitations(db, bill_split)
            
            # Clear order cache
            await cache_service.delete(f"order:{order_id}")
            
            return bill_split
            
        except Exception as e:
            await db.rollback()
            logger.error(f"Failed to create bill split: {e}")
            raise
    
    async def _create_participants(
        self,
        db: AsyncSession,
        bill_split: BillSplit,
        participants: List[Dict[str, Any]],
        split_method: SplitMethod,
        split_config: Optional[Dict[str, Any]]
    ):
        """Create participant records based on split method"""
        
        # Validate split configuration
        self._validate_split_config(
            split_method, participants, split_config, bill_split.total_amount
        )
        
        for participant_data in participants:
            # Calculate participant's share
            if split_method == SplitMethod.EQUAL:
                share_amount = bill_split.subtotal / len(participants)
                tip_share = bill_split.tip_amount / len(participants)
                
            elif split_method == SplitMethod.PERCENTAGE:
                percentage = split_config['percentages'].get(
                    str(participant_data.get('id', participant_data.get('email'))), 0
                )
                share_amount = bill_split.subtotal * Decimal(str(percentage)) / 100
                tip_share = bill_split.tip_amount * Decimal(str(percentage)) / 100
                
            elif split_method == SplitMethod.AMOUNT:
                amount = split_config['amounts'].get(
                    str(participant_data.get('id', participant_data.get('email'))), 0
                )
                share_amount = Decimal(str(amount))
                # For fixed amounts, tip is proportional to share
                if bill_split.subtotal > 0:
                    tip_share = bill_split.tip_amount * (share_amount / bill_split.subtotal)
                else:
                    tip_share = Decimal('0')
                    
            elif split_method == SplitMethod.ITEM:
                # Calculate based on items
                share_amount, tip_share = await self._calculate_item_based_share(
                    db, bill_split, participant_data, split_config
                )
            else:
                # Custom method - use provided amounts
                share_amount = Decimal(str(participant_data.get('share_amount', 0)))
                tip_share = Decimal(str(participant_data.get('tip_amount', 0)))
            
            # Add proportional tax and service charge
            if bill_split.subtotal > 0:
                proportion = share_amount / bill_split.subtotal
                tax_share = bill_split.tax_amount * proportion
                service_share = bill_split.service_charge * proportion
            else:
                tax_share = Decimal('0')
                service_share = Decimal('0')
            
            total_share = share_amount + tax_share + service_share + tip_share
            
            # Create participant
            participant = SplitParticipant(
                split_id=bill_split.id,
                customer_id=participant_data.get('customer_id'),
                name=participant_data['name'],
                email=participant_data.get('email'),
                phone=participant_data.get('phone'),
                share_amount=share_amount + tax_share + service_share,
                tip_amount=tip_share,
                total_amount=total_share,
                access_token=secrets.token_urlsafe(32),
                notify_via_email=participant_data.get('notify_via_email', True),
                notify_via_sms=participant_data.get('notify_via_sms', False)
            )
            
            db.add(participant)
    
    async def _calculate_item_based_share(
        self,
        db: AsyncSession,
        bill_split: BillSplit,
        participant_data: Dict[str, Any],
        split_config: Dict[str, Any]
    ) -> Tuple[Decimal, Decimal]:
        """Calculate share for item-based splitting"""
        
        participant_id = participant_data.get('id', participant_data.get('email'))
        items = split_config.get('items', [])
        
        share_amount = Decimal('0')
        
        for item_config in items:
            if participant_id in item_config.get('participant_ids', []):
                item_price = Decimal(str(item_config.get('price', 0)))
                quantity = item_config.get('quantity', 1)
                participants_count = len(item_config.get('participant_ids', []))
                
                if participants_count > 0:
                    # Split item cost among assigned participants
                    share_amount += (item_price * quantity) / participants_count
        
        # Calculate proportional tip
        if bill_split.subtotal > 0:
            tip_share = bill_split.tip_amount * (share_amount / bill_split.subtotal)
        else:
            tip_share = Decimal('0')
        
        return share_amount, tip_share
    
    def _calculate_tip_amount(
        self,
        subtotal: Decimal,
        tip_method: Optional[TipMethod],
        tip_value: Optional[Decimal]
    ) -> Decimal:
        """Calculate tip amount based on method"""
        
        if not tip_method or tip_value is None:
            return Decimal('0')
        
        if tip_method == TipMethod.PERCENTAGE:
            return subtotal * tip_value / 100
        
        elif tip_method == TipMethod.AMOUNT:
            return tip_value
        
        elif tip_method == TipMethod.ROUND_UP:
            # Round up to nearest dollar amount specified
            total_with_tax = subtotal  # Add tax if needed
            remainder = total_with_tax % tip_value
            if remainder > 0:
                return tip_value - remainder
            return Decimal('0')
        
        return Decimal('0')
    
    def _validate_split_config(
        self,
        split_method: SplitMethod,
        participants: List[Dict[str, Any]],
        split_config: Optional[Dict[str, Any]],
        total_amount: Decimal
    ):
        """Validate split configuration"""
        
        if split_method == SplitMethod.PERCENTAGE:
            if not split_config or 'percentages' not in split_config:
                raise ValueError("Percentage split requires 'percentages' in split_config")
            
            total_percentage = sum(
                Decimal(str(v)) for v in split_config['percentages'].values()
            )
            if abs(total_percentage - 100) > Decimal('0.01'):
                raise ValueError(f"Percentages must sum to 100%, got {total_percentage}%")
        
        elif split_method == SplitMethod.AMOUNT:
            if not split_config or 'amounts' not in split_config:
                raise ValueError("Amount split requires 'amounts' in split_config")
            
            total_amounts = sum(
                Decimal(str(v)) for v in split_config['amounts'].values()
            )
            if abs(total_amounts - total_amount) > Decimal('0.01'):
                raise ValueError(f"Amounts must sum to total {total_amount}, got {total_amounts}")
        
        elif split_method == SplitMethod.ITEM:
            if not split_config or 'items' not in split_config:
                raise ValueError("Item split requires 'items' in split_config")
    
    async def get_split(
        self,
        db: AsyncSession,
        split_id: int,
        include_participants: bool = True
    ) -> Optional[BillSplit]:
        """Get a bill split by ID"""
        
        query = select(BillSplit).where(BillSplit.id == split_id)
        
        if include_participants:
            query = query.options(selectinload(BillSplit.participants))
        
        result = await db.execute(query)
        return result.scalar_one_or_none()
    
    async def get_split_by_token(
        self,
        db: AsyncSession,
        access_token: str
    ) -> Optional[Tuple[BillSplit, SplitParticipant]]:
        """Get split and participant by access token"""
        
        result = await db.execute(
            select(SplitParticipant)
            .where(SplitParticipant.access_token == access_token)
            .options(selectinload(SplitParticipant.bill_split))
        )
        
        participant = result.scalar_one_or_none()
        if participant:
            return participant.bill_split, participant
        
        return None, None
    
    async def update_participant_status(
        self,
        db: AsyncSession,
        participant_id: int,
        status: ParticipantStatus,
        decline_reason: Optional[str] = None
    ) -> SplitParticipant:
        """Update participant status (accept/decline)"""
        
        try:
            participant = await db.get(SplitParticipant, participant_id)
            if not participant:
                raise ValueError(f"Participant {participant_id} not found")
            
            # Update status
            old_status = participant.status
            participant.status = status
            
            if status == ParticipantStatus.ACCEPTED:
                participant.accepted_at = datetime.utcnow()
            elif status == ParticipantStatus.DECLINED:
                participant.declined_at = datetime.utcnow()
                participant.decline_reason = decline_reason
            
            # Check if all required participants have responded
            await self._check_split_activation(db, participant.split_id)
            
            await db.commit()
            
            # Notify organizer
            if old_status != status:
                await self._notify_status_change(db, participant)
            
            return participant
            
        except Exception as e:
            await db.rollback()
            logger.error(f"Failed to update participant status: {e}")
            raise
    
    async def _check_split_activation(self, db: AsyncSession, split_id: int):
        """Check if split should be activated"""
        
        split = await db.get(BillSplit, split_id)
        if not split or split.status != SplitStatus.PENDING:
            return
        
        # Get all participants
        result = await db.execute(
            select(SplitParticipant).where(SplitParticipant.split_id == split_id)
        )
        participants = result.scalars().all()
        
        # Check if all have responded
        pending_count = sum(
            1 for p in participants 
            if p.status == ParticipantStatus.PENDING
        )
        
        if split.require_all_acceptance:
            # All must accept
            accepted_count = sum(
                1 for p in participants 
                if p.status == ParticipantStatus.ACCEPTED
            )
            
            if accepted_count == len(participants):
                split.status = SplitStatus.ACTIVE
        else:
            # Activate if all have responded
            if pending_count == 0:
                split.status = SplitStatus.ACTIVE
    
    async def record_participant_payment(
        self,
        db: AsyncSession,
        participant_id: int,
        payment: Payment,
        amount: Decimal
    ) -> PaymentAllocation:
        """Record a payment from a participant"""
        
        try:
            participant = await db.get(SplitParticipant, participant_id)
            if not participant:
                raise ValueError(f"Participant {participant_id} not found")
            
            split = await db.get(BillSplit, participant.split_id)
            if not split:
                raise ValueError("Split not found")
            
            # Update participant payment info
            participant.payment_id = payment.id
            participant.paid_amount += amount
            participant.paid_at = datetime.utcnow()
            
            if participant.paid_amount >= participant.total_amount:
                participant.status = ParticipantStatus.PAID
            
            # Create allocation record
            allocation = PaymentAllocation(
                payment_id=payment.id,
                split_id=split.id,
                participant_id=participant_id,
                allocated_amount=amount,
                covers_share=True,
                covers_tip=True
            )
            
            db.add(allocation)
            
            # Update split status
            await self._update_split_status(db, split)
            
            await db.commit()
            
            # Notify organizer
            await self._notify_payment_received(db, participant, amount)
            
            return allocation
            
        except Exception as e:
            await db.rollback()
            logger.error(f"Failed to record participant payment: {e}")
            raise
    
    async def _update_split_status(self, db: AsyncSession, split: BillSplit):
        """Update split status based on payments"""
        
        # Get all participants
        result = await db.execute(
            select(SplitParticipant).where(SplitParticipant.split_id == split.id)
        )
        participants = result.scalars().all()
        
        # Count payment statuses
        paid_count = sum(1 for p in participants if p.status == ParticipantStatus.PAID)
        declined_count = sum(1 for p in participants if p.status == ParticipantStatus.DECLINED)
        active_participants = len(participants) - declined_count
        
        if paid_count == active_participants and active_participants > 0:
            split.status = SplitStatus.COMPLETED
            
            # Process tip distribution if configured
            if split.tip_amount > 0:
                await self._create_tip_distribution(db, split)
                
        elif paid_count > 0:
            split.status = SplitStatus.PARTIALLY_PAID
    
    async def _create_tip_distribution(
        self,
        db: AsyncSession,
        split: BillSplit
    ):
        """Create tip distribution record when split is completed"""
        
        distribution = TipDistribution(
            order_id=split.order_id,
            split_id=split.id,
            tip_amount=split.tip_amount,
            distribution_method="pool"  # Default method
        )
        
        db.add(distribution)
    
    async def cancel_split(
        self,
        db: AsyncSession,
        split_id: int,
        reason: Optional[str] = None
    ) -> BillSplit:
        """Cancel a bill split"""
        
        try:
            split = await db.get(BillSplit, split_id)
            if not split:
                raise ValueError(f"Split {split_id} not found")
            
            if split.status == SplitStatus.COMPLETED:
                raise ValueError("Cannot cancel completed split")
            
            # Update status
            split.status = SplitStatus.CANCELLED
            if reason:
                split.metadata['cancellation_reason'] = reason
            
            # Cancel all pending participants
            result = await db.execute(
                select(SplitParticipant).where(
                    and_(
                        SplitParticipant.split_id == split_id,
                        SplitParticipant.status == ParticipantStatus.PENDING
                    )
                )
            )
            participants = result.scalars().all()
            
            for participant in participants:
                participant.status = ParticipantStatus.DECLINED
                participant.decline_reason = "Split cancelled"
            
            await db.commit()
            
            # Notify participants
            await self._notify_split_cancelled(db, split)
            
            return split
            
        except Exception as e:
            await db.rollback()
            logger.error(f"Failed to cancel split: {e}")
            raise
    
    async def send_reminders(
        self,
        db: AsyncSession,
        split_id: int
    ):
        """Send payment reminders to pending participants"""
        
        split = await db.get(BillSplit, split_id)
        if not split or not split.send_reminders:
            return
        
        # Get pending participants
        result = await db.execute(
            select(SplitParticipant).where(
                and_(
                    SplitParticipant.split_id == split_id,
                    SplitParticipant.status.in_([
                        ParticipantStatus.PENDING,
                        ParticipantStatus.ACCEPTED
                    ]),
                    SplitParticipant.paid_amount < SplitParticipant.total_amount
                )
            )
        )
        participants = result.scalars().all()
        
        for participant in participants:
            await self._send_payment_reminder(participant)
        
        split.reminder_sent_at = datetime.utcnow()
        await db.commit()
    
    # Notification methods
    
    async def _send_participant_invitations(self, db: AsyncSession, split: BillSplit):
        """Send invitations to all participants"""
        
        for participant in split.participants:
            if participant.notify_via_email and participant.email:
                await notification_service.send_email(
                    to_email=participant.email,
                    subject=f"You've been invited to split a bill",
                    template="split_bill_invitation",
                    context={
                        'participant_name': participant.name,
                        'organizer_name': split.organizer_name,
                        'total_amount': str(participant.total_amount),
                        'share_amount': str(participant.share_amount),
                        'tip_amount': str(participant.tip_amount),
                        'access_link': f"/split/{participant.access_token}"
                    }
                )
            
            participant.invite_sent_at = datetime.utcnow()
    
    async def _notify_status_change(self, db: AsyncSession, participant: SplitParticipant):
        """Notify organizer of participant status change"""
        
        split = await db.get(BillSplit, participant.split_id)
        if not split or not split.organizer_email:
            return
        
        status_text = "accepted" if participant.status == ParticipantStatus.ACCEPTED else "declined"
        
        await notification_service.send_email(
            to_email=split.organizer_email,
            subject=f"{participant.name} has {status_text} the bill split",
            template="split_status_update",
            context={
                'organizer_name': split.organizer_name,
                'participant_name': participant.name,
                'status': status_text,
                'reason': participant.decline_reason
            }
        )
    
    async def _notify_payment_received(
        self,
        db: AsyncSession,
        participant: SplitParticipant,
        amount: Decimal
    ):
        """Notify organizer of payment received"""
        
        split = await db.get(BillSplit, participant.split_id)
        if not split or not split.organizer_email:
            return
        
        await notification_service.send_email(
            to_email=split.organizer_email,
            subject=f"Payment received from {participant.name}",
            template="split_payment_received",
            context={
                'organizer_name': split.organizer_name,
                'participant_name': participant.name,
                'amount': str(amount),
                'remaining': str(participant.remaining_amount)
            }
        )
    
    async def _notify_split_cancelled(self, db: AsyncSession, split: BillSplit):
        """Notify all participants of cancellation"""
        
        for participant in split.participants:
            if participant.notify_via_email and participant.email:
                await notification_service.send_email(
                    to_email=participant.email,
                    subject="Bill split has been cancelled",
                    template="split_cancelled",
                    context={
                        'participant_name': participant.name,
                        'organizer_name': split.organizer_name
                    }
                )
    
    async def _send_payment_reminder(self, participant: SplitParticipant):
        """Send payment reminder to participant"""
        
        if participant.notify_via_email and participant.email:
            await notification_service.send_email(
                to_email=participant.email,
                subject="Reminder: Payment pending for bill split",
                template="split_payment_reminder",
                context={
                    'participant_name': participant.name,
                    'amount_due': str(participant.remaining_amount),
                    'access_link': f"/split/{participant.access_token}"
                }
            )


# Global service instance
split_bill_service = SplitBillService()