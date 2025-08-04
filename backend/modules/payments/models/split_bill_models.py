# backend/modules/payments/models/split_bill_models.py

from sqlalchemy import Column, Integer, String, ForeignKey, Numeric, Boolean, Text, DateTime, Enum as SQLEnum, Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from decimal import Decimal
from typing import Dict, Any, Optional, List
import enum

from core.database import Base, TimestampMixin


class SplitMethod(str, enum.Enum):
    """Methods for splitting bills"""
    EQUAL = "equal"  # Split equally among all participants
    PERCENTAGE = "percentage"  # Split by percentage
    AMOUNT = "amount"  # Split by specific amounts
    ITEM = "item"  # Split by individual items
    CUSTOM = "custom"  # Custom split logic


class SplitStatus(str, enum.Enum):
    """Status of a split bill"""
    PENDING = "pending"  # Initial state
    ACTIVE = "active"  # Ready for payment
    PARTIALLY_PAID = "partially_paid"  # Some participants have paid
    COMPLETED = "completed"  # All participants have paid
    CANCELLED = "cancelled"  # Split was cancelled


class ParticipantStatus(str, enum.Enum):
    """Status of a participant in a split"""
    PENDING = "pending"  # Waiting to accept/pay
    ACCEPTED = "accepted"  # Accepted their portion
    DECLINED = "declined"  # Declined to participate
    PAID = "paid"  # Payment completed
    REFUNDED = "refunded"  # Payment was refunded


class TipMethod(str, enum.Enum):
    """Methods for calculating tips"""
    PERCENTAGE = "percentage"  # Percentage of subtotal
    AMOUNT = "amount"  # Fixed amount
    ROUND_UP = "round_up"  # Round up to nearest dollar amount


class BillSplit(Base, TimestampMixin):
    """
    Main split bill record that tracks how an order is split among multiple participants
    """
    __tablename__ = "bill_splits"
    
    id = Column(Integer, primary_key=True, index=True)
    split_id = Column(String(100), nullable=False, unique=True, index=True)
    
    # Order relationship
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False, index=True)
    
    # Split configuration
    split_method = Column(SQLEnum(SplitMethod), nullable=False, default=SplitMethod.EQUAL)
    status = Column(SQLEnum(SplitStatus), nullable=False, default=SplitStatus.PENDING, index=True)
    
    # Amounts
    subtotal = Column(Numeric(10, 2), nullable=False)  # Pre-tax, pre-tip amount
    tax_amount = Column(Numeric(10, 2), nullable=False, default=0)
    service_charge = Column(Numeric(10, 2), nullable=False, default=0)
    
    # Tip configuration
    tip_method = Column(SQLEnum(TipMethod), nullable=True)
    tip_value = Column(Numeric(10, 2), nullable=True)  # Percentage or amount based on tip_method
    tip_amount = Column(Numeric(10, 2), nullable=False, default=0)  # Calculated tip amount
    total_amount = Column(Numeric(10, 2), nullable=False)  # Total including tax and tip
    
    # Split configuration details
    split_config = Column(JSONB, nullable=True, default={})
    # For item-based splits: {"items": [{"item_id": 1, "participant_ids": [1, 2]}]}
    # For percentage splits: {"percentages": {"participant_1": 50, "participant_2": 50}}
    # For amount splits: {"amounts": {"participant_1": 25.00, "participant_2": 30.00}}
    
    # Organizer info
    organizer_id = Column(Integer, ForeignKey("customers.id"), nullable=True)
    organizer_name = Column(String(255), nullable=True)
    organizer_email = Column(String(255), nullable=True)
    organizer_phone = Column(String(50), nullable=True)
    
    # Settings
    allow_partial_payments = Column(Boolean, default=True)
    require_all_acceptance = Column(Boolean, default=False)
    auto_close_on_completion = Column(Boolean, default=True)
    expires_at = Column(DateTime, nullable=True)
    
    # Notification settings
    send_reminders = Column(Boolean, default=True)
    reminder_sent_at = Column(DateTime, nullable=True)
    
    # Metadata
    notes = Column(Text, nullable=True)
    metadata = Column(JSONB, nullable=True, default={})
    
    # Relationships
    order = relationship("Order", backref="bill_splits")
    participants = relationship("SplitParticipant", back_populates="bill_split", cascade="all, delete-orphan")
    allocations = relationship("PaymentAllocation", back_populates="bill_split")
    
    # Indexes
    __table_args__ = (
        Index('idx_bill_split_order_status', 'order_id', 'status'),
        Index('idx_bill_split_organizer', 'organizer_id'),
    )
    
    def calculate_participant_share(self, participant_id: int) -> Decimal:
        """Calculate a participant's share based on split method"""
        if self.split_method == SplitMethod.EQUAL:
            active_participants = [p for p in self.participants if p.status != ParticipantStatus.DECLINED]
            if not active_participants:
                return Decimal('0')
            return self.total_amount / len(active_participants)
        
        elif self.split_method == SplitMethod.PERCENTAGE:
            percentages = self.split_config.get('percentages', {})
            percentage = percentages.get(str(participant_id), 0)
            return self.total_amount * Decimal(str(percentage)) / 100
        
        elif self.split_method == SplitMethod.AMOUNT:
            amounts = self.split_config.get('amounts', {})
            return Decimal(str(amounts.get(str(participant_id), 0)))
        
        elif self.split_method == SplitMethod.ITEM:
            # Calculate based on items assigned to participant
            items = self.split_config.get('items', [])
            participant_total = Decimal('0')
            
            for item in items:
                if participant_id in item.get('participant_ids', []):
                    item_price = Decimal(str(item.get('price', 0)))
                    participants_count = len(item.get('participant_ids', []))
                    if participants_count > 0:
                        participant_total += item_price / participants_count
            
            # Add proportional tax and tip
            if self.subtotal > 0:
                proportion = participant_total / self.subtotal
                participant_total += (self.tax_amount + self.tip_amount) * proportion
            
            return participant_total
        
        return Decimal('0')
    
    @property
    def paid_amount(self) -> Decimal:
        """Calculate total amount paid so far"""
        return sum(p.paid_amount for p in self.participants)
    
    @property
    def remaining_amount(self) -> Decimal:
        """Calculate remaining amount to be paid"""
        return self.total_amount - self.paid_amount


class SplitParticipant(Base, TimestampMixin):
    """
    Individual participant in a bill split
    """
    __tablename__ = "split_participants"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Split relationship
    split_id = Column(Integer, ForeignKey("bill_splits.id"), nullable=False, index=True)
    
    # Participant info
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=True, index=True)
    name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=True)
    phone = Column(String(50), nullable=True)
    
    # Share details
    share_amount = Column(Numeric(10, 2), nullable=False)  # Their portion of the bill
    tip_amount = Column(Numeric(10, 2), nullable=False, default=0)  # Their tip contribution
    total_amount = Column(Numeric(10, 2), nullable=False)  # Total they need to pay
    
    # Custom tip override (if participant wants to tip differently)
    custom_tip_amount = Column(Numeric(10, 2), nullable=True)
    
    # Payment status
    status = Column(SQLEnum(ParticipantStatus), nullable=False, default=ParticipantStatus.PENDING, index=True)
    paid_amount = Column(Numeric(10, 2), nullable=False, default=0)
    payment_id = Column(Integer, ForeignKey("payments.id"), nullable=True)
    paid_at = Column(DateTime, nullable=True)
    
    # Acceptance tracking
    invite_sent_at = Column(DateTime, nullable=True)
    accepted_at = Column(DateTime, nullable=True)
    declined_at = Column(DateTime, nullable=True)
    decline_reason = Column(Text, nullable=True)
    
    # Access token for guest participants
    access_token = Column(String(255), nullable=True, unique=True, index=True)
    
    # Notification preferences
    notify_via_email = Column(Boolean, default=True)
    notify_via_sms = Column(Boolean, default=False)
    
    # Metadata
    notes = Column(Text, nullable=True)
    metadata = Column(JSONB, nullable=True, default={})
    
    # Relationships
    bill_split = relationship("BillSplit", back_populates="participants")
    payment = relationship("Payment", backref="split_participant")
    
    # Indexes
    __table_args__ = (
        Index('idx_participant_split_status', 'split_id', 'status'),
        Index('idx_participant_customer', 'customer_id'),
        UniqueConstraint('split_id', 'email', name='uq_split_participant_email'),
    )
    
    @property
    def is_fully_paid(self) -> bool:
        """Check if participant has paid their full share"""
        return self.paid_amount >= self.total_amount
    
    @property
    def remaining_amount(self) -> Decimal:
        """Calculate remaining amount for this participant"""
        return max(self.total_amount - self.paid_amount, Decimal('0'))


class PaymentAllocation(Base, TimestampMixin):
    """
    Tracks how payments are allocated to split bills
    Useful for reconciliation and refunds
    """
    __tablename__ = "payment_allocations"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Payment and split references
    payment_id = Column(Integer, ForeignKey("payments.id"), nullable=False, index=True)
    split_id = Column(Integer, ForeignKey("bill_splits.id"), nullable=False, index=True)
    participant_id = Column(Integer, ForeignKey("split_participants.id"), nullable=False, index=True)
    
    # Allocation details
    allocated_amount = Column(Numeric(10, 2), nullable=False)
    
    # What this allocation covers
    covers_share = Column(Boolean, default=True)  # Covers the participant's share
    covers_tip = Column(Boolean, default=True)  # Covers tip
    covers_fees = Column(Boolean, default=False)  # Covers any additional fees
    
    # Status
    is_active = Column(Boolean, default=True)
    
    # Metadata
    notes = Column(Text, nullable=True)
    
    # Relationships
    payment = relationship("Payment", backref="allocations")
    bill_split = relationship("BillSplit", back_populates="allocations")
    participant = relationship("SplitParticipant", backref="allocations")
    
    # Indexes
    __table_args__ = (
        Index('idx_allocation_payment', 'payment_id'),
        Index('idx_allocation_split', 'split_id'),
        Index('idx_allocation_participant', 'participant_id'),
        UniqueConstraint('payment_id', 'split_id', 'participant_id', name='uq_payment_split_participant'),
    )


class TipDistribution(Base, TimestampMixin):
    """
    Tracks how tips are distributed among staff
    """
    __tablename__ = "tip_distributions"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Source of tip
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=True, index=True)
    split_id = Column(Integer, ForeignKey("bill_splits.id"), nullable=True, index=True)
    payment_id = Column(Integer, ForeignKey("payments.id"), nullable=True, index=True)
    
    # Tip details
    tip_amount = Column(Numeric(10, 2), nullable=False)
    distribution_method = Column(String(50), nullable=False, default="pool")  # pool, direct, percentage
    
    # Distribution configuration
    distribution_config = Column(JSONB, nullable=True, default={})
    # {"rules": [{"staff_id": 1, "percentage": 50}, {"role": "server", "percentage": 30}]}
    
    # Status
    is_distributed = Column(Boolean, default=False)
    distributed_at = Column(DateTime, nullable=True)
    distributed_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    
    # Actual distributions
    distributions = Column(JSONB, nullable=True, default=[])
    # [{"staff_id": 1, "amount": 10.50, "paid": true, "paid_at": "2025-01-01"}]
    
    # Metadata
    notes = Column(Text, nullable=True)
    
    # Indexes
    __table_args__ = (
        Index('idx_tip_dist_order', 'order_id'),
        Index('idx_tip_dist_split', 'split_id'),
        Index('idx_tip_dist_status', 'is_distributed'),
    )