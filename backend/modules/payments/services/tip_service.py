# backend/modules/payments/services/tip_service.py

import logging
from typing import Dict, Any, Optional, List
from decimal import Decimal
from datetime import datetime, date
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func
from sqlalchemy.orm import selectinload

from core.database import get_db
from ..models.split_bill_models import TipDistribution, TipMethod
from ..models.payment_models import Payment, PaymentStatus
from ...orders.models.order_models import Order
from ...staff.models.staff_models import Staff, StaffRole
from ...payroll.models.payroll_models import TipRecord

logger = logging.getLogger(__name__)


class TipService:
    """
    Service for managing tip calculations and distributions
    """
    
    def calculate_tip(
        self,
        subtotal: Decimal,
        tip_method: TipMethod,
        tip_value: Decimal,
        **kwargs
    ) -> Decimal:
        """
        Calculate tip amount based on method
        
        Args:
            subtotal: Pre-tax amount
            tip_method: Method of tip calculation
            tip_value: Value used for calculation
            **kwargs: Additional parameters for specific methods
            
        Returns:
            Calculated tip amount
        """
        
        if tip_method == TipMethod.PERCENTAGE:
            return (subtotal * tip_value) / 100
            
        elif tip_method == TipMethod.AMOUNT:
            return tip_value
            
        elif tip_method == TipMethod.ROUND_UP:
            # Round up to nearest specified amount
            current_total = kwargs.get('current_total', subtotal)
            round_to = tip_value  # e.g., 5 for round to nearest $5
            
            remainder = current_total % round_to
            if remainder > 0:
                return round_to - remainder
            return Decimal('0')
            
        return Decimal('0')
    
    def suggest_tip_amounts(
        self,
        subtotal: Decimal,
        default_percentages: Optional[List[int]] = None
    ) -> List[Dict[str, Any]]:
        """
        Generate suggested tip amounts
        
        Args:
            subtotal: Pre-tax amount
            default_percentages: List of percentages to suggest
            
        Returns:
            List of suggested tip options
        """
        
        if default_percentages is None:
            default_percentages = [15, 18, 20, 25]
        
        suggestions = []
        
        for percentage in default_percentages:
            tip_amount = (subtotal * percentage) / 100
            total = subtotal + tip_amount
            
            suggestions.append({
                'percentage': percentage,
                'tip_amount': float(tip_amount),
                'total_amount': float(total),
                'display': f"{percentage}% (${tip_amount:.2f})"
            })
        
        # Add custom option
        suggestions.append({
            'percentage': None,
            'tip_amount': None,
            'total_amount': None,
            'display': 'Custom Amount'
        })
        
        return suggestions
    
    async def create_tip_distribution(
        self,
        db: AsyncSession,
        order_id: Optional[int] = None,
        payment_id: Optional[int] = None,
        split_id: Optional[int] = None,
        tip_amount: Decimal = Decimal('0'),
        distribution_method: str = "pool",
        distribution_config: Optional[Dict[str, Any]] = None
    ) -> TipDistribution:
        """
        Create a tip distribution record
        
        Args:
            db: Database session
            order_id: Associated order
            payment_id: Associated payment
            split_id: Associated split bill
            tip_amount: Total tip amount
            distribution_method: How to distribute (pool, direct, percentage, role)
            distribution_config: Configuration for distribution
            
        Returns:
            Created TipDistribution
        """
        
        try:
            distribution = TipDistribution(
                order_id=order_id,
                payment_id=payment_id,
                split_id=split_id,
                tip_amount=tip_amount,
                distribution_method=distribution_method,
                distribution_config=distribution_config or {}
            )
            
            db.add(distribution)
            await db.commit()
            
            return distribution
            
        except Exception as e:
            await db.rollback()
            logger.error(f"Failed to create tip distribution: {e}")
            raise
    
    async def process_tip_distribution(
        self,
        db: AsyncSession,
        distribution_id: int,
        processed_by: int
    ) -> TipDistribution:
        """
        Process a tip distribution and allocate to staff
        
        Args:
            db: Database session
            distribution_id: Distribution to process
            processed_by: User processing the distribution
            
        Returns:
            Updated distribution
        """
        
        try:
            distribution = await db.get(TipDistribution, distribution_id)
            if not distribution:
                raise ValueError(f"Distribution {distribution_id} not found")
            
            if distribution.is_distributed:
                raise ValueError("Distribution already processed")
            
            # Get eligible staff based on the shift
            eligible_staff = await self._get_eligible_staff(db, distribution)
            
            # Calculate individual distributions
            staff_distributions = await self._calculate_staff_distributions(
                db, distribution, eligible_staff
            )
            
            # Create tip records for payroll
            for staff_dist in staff_distributions:
                await self._create_tip_record(
                    db,
                    staff_id=staff_dist['staff_id'],
                    amount=staff_dist['amount'],
                    distribution_id=distribution.id,
                    date=date.today()
                )
            
            # Update distribution
            distribution.distributions = staff_distributions
            distribution.is_distributed = True
            distribution.distributed_at = datetime.utcnow()
            distribution.distributed_by = processed_by
            
            await db.commit()
            
            return distribution
            
        except Exception as e:
            await db.rollback()
            logger.error(f"Failed to process tip distribution: {e}")
            raise
    
    async def _get_eligible_staff(
        self,
        db: AsyncSession,
        distribution: TipDistribution
    ) -> List[Staff]:
        """Get staff eligible for tip distribution"""
        
        # For now, get all active tipped staff
        # In production, this would check shift schedules
        result = await db.execute(
            select(Staff).where(
                and_(
                    Staff.is_active == True,
                    Staff.receives_tips == True
                )
            )
        )
        
        return result.scalars().all()
    
    async def _calculate_staff_distributions(
        self,
        db: AsyncSession,
        distribution: TipDistribution,
        eligible_staff: List[Staff]
    ) -> List[Dict[str, Any]]:
        """Calculate how much each staff member receives"""
        
        distributions = []
        remaining_amount = distribution.tip_amount
        
        if distribution.distribution_method == "pool":
            # Equal distribution among all eligible staff
            if eligible_staff:
                per_person = distribution.tip_amount / len(eligible_staff)
                
                for staff in eligible_staff:
                    distributions.append({
                        'staff_id': staff.id,
                        'staff_name': staff.full_name,
                        'amount': float(per_person),
                        'method': 'pool',
                        'paid': False
                    })
                    
        elif distribution.distribution_method == "percentage":
            # Distribution based on configured percentages
            config = distribution.distribution_config or {}
            percentages = config.get('percentages', {})
            
            for staff in eligible_staff:
                percentage = percentages.get(str(staff.id), 0)
                if percentage > 0:
                    amount = distribution.tip_amount * Decimal(str(percentage)) / 100
                    distributions.append({
                        'staff_id': staff.id,
                        'staff_name': staff.full_name,
                        'amount': float(amount),
                        'percentage': percentage,
                        'method': 'percentage',
                        'paid': False
                    })
                    
        elif distribution.distribution_method == "role":
            # Distribution based on role percentages
            config = distribution.distribution_config or {}
            role_percentages = config.get('role_percentages', {
                'server': 40,
                'bartender': 30,
                'busser': 15,
                'host': 15
            })
            
            # Group staff by role
            role_counts = {}
            staff_by_role = {}
            
            for staff in eligible_staff:
                role = staff.role
                if role not in role_counts:
                    role_counts[role] = 0
                    staff_by_role[role] = []
                role_counts[role] += 1
                staff_by_role[role].append(staff)
            
            # Distribute based on role percentages
            for role, percentage in role_percentages.items():
                if role in staff_by_role and percentage > 0:
                    role_total = distribution.tip_amount * Decimal(str(percentage)) / 100
                    per_person = role_total / len(staff_by_role[role])
                    
                    for staff in staff_by_role[role]:
                        distributions.append({
                            'staff_id': staff.id,
                            'staff_name': staff.full_name,
                            'amount': float(per_person),
                            'role': role,
                            'role_percentage': percentage,
                            'method': 'role',
                            'paid': False
                        })
                        
        elif distribution.distribution_method == "direct":
            # Direct assignment to specific staff
            config = distribution.distribution_config or {}
            assignments = config.get('assignments', [])
            
            for assignment in assignments:
                staff_id = assignment.get('staff_id')
                amount = Decimal(str(assignment.get('amount', 0)))
                
                if staff_id and amount > 0:
                    staff = next((s for s in eligible_staff if s.id == staff_id), None)
                    if staff:
                        distributions.append({
                            'staff_id': staff.id,
                            'staff_name': staff.full_name,
                            'amount': float(amount),
                            'method': 'direct',
                            'paid': False
                        })
        
        return distributions
    
    async def _create_tip_record(
        self,
        db: AsyncSession,
        staff_id: int,
        amount: Decimal,
        distribution_id: int,
        date: date
    ):
        """Create a tip record for payroll processing"""
        
        # Check if TipRecord exists in payroll module
        try:
            tip_record = TipRecord(
                staff_id=staff_id,
                amount=amount,
                date=date,
                distribution_id=distribution_id,
                status='pending'
            )
            db.add(tip_record)
        except Exception as e:
            # Log but don't fail if payroll module doesn't have TipRecord
            logger.warning(f"Could not create tip record: {e}")
    
    async def get_staff_tips_summary(
        self,
        db: AsyncSession,
        staff_id: int,
        start_date: date,
        end_date: date
    ) -> Dict[str, Any]:
        """
        Get tip summary for a staff member
        
        Args:
            db: Database session
            staff_id: Staff member ID
            start_date: Start of period
            end_date: End of period
            
        Returns:
            Summary of tips for the period
        """
        
        # Get all distributions for the period
        result = await db.execute(
            select(TipDistribution).where(
                and_(
                    TipDistribution.is_distributed == True,
                    TipDistribution.distributed_at >= start_date,
                    TipDistribution.distributed_at <= end_date
                )
            )
        )
        distributions = result.scalars().all()
        
        # Calculate totals for this staff member
        total_tips = Decimal('0')
        distribution_count = 0
        daily_totals = {}
        
        for distribution in distributions:
            for staff_dist in distribution.distributions:
                if staff_dist.get('staff_id') == staff_id:
                    amount = Decimal(str(staff_dist.get('amount', 0)))
                    total_tips += amount
                    distribution_count += 1
                    
                    # Track daily totals
                    dist_date = distribution.distributed_at.date()
                    if dist_date not in daily_totals:
                        daily_totals[dist_date] = Decimal('0')
                    daily_totals[dist_date] += amount
        
        # Calculate averages
        days_worked = len(daily_totals)
        avg_daily = total_tips / days_worked if days_worked > 0 else Decimal('0')
        
        return {
            'staff_id': staff_id,
            'period_start': start_date,
            'period_end': end_date,
            'total_tips': float(total_tips),
            'distribution_count': distribution_count,
            'days_worked': days_worked,
            'average_daily': float(avg_daily),
            'daily_breakdown': {
                str(date): float(amount) 
                for date, amount in daily_totals.items()
            }
        }
    
    async def get_tip_pool_summary(
        self,
        db: AsyncSession,
        date: date
    ) -> Dict[str, Any]:
        """
        Get summary of tip pool for a specific date
        
        Args:
            db: Database session
            date: Date to get summary for
            
        Returns:
            Summary of tip pool activity
        """
        
        # Get all distributions for the date
        result = await db.execute(
            select(TipDistribution).where(
                and_(
                    func.date(TipDistribution.created_at) == date,
                    TipDistribution.is_distributed == True
                )
            )
        )
        distributions = result.scalars().all()
        
        # Calculate totals
        total_tips = sum(d.tip_amount for d in distributions)
        total_distributed = Decimal('0')
        staff_totals = {}
        
        for distribution in distributions:
            for staff_dist in distribution.distributions:
                staff_id = staff_dist.get('staff_id')
                amount = Decimal(str(staff_dist.get('amount', 0)))
                
                total_distributed += amount
                
                if staff_id not in staff_totals:
                    staff_totals[staff_id] = {
                        'amount': Decimal('0'),
                        'count': 0,
                        'name': staff_dist.get('staff_name', 'Unknown')
                    }
                
                staff_totals[staff_id]['amount'] += amount
                staff_totals[staff_id]['count'] += 1
        
        return {
            'date': date,
            'total_tips': float(total_tips),
            'total_distributed': float(total_distributed),
            'distribution_count': len(distributions),
            'staff_summary': [
                {
                    'staff_id': staff_id,
                    'staff_name': data['name'],
                    'total_amount': float(data['amount']),
                    'distribution_count': data['count']
                }
                for staff_id, data in staff_totals.items()
            ]
        }
    
    async def adjust_tip_distribution(
        self,
        db: AsyncSession,
        distribution_id: int,
        adjustments: List[Dict[str, Any]],
        adjusted_by: int,
        reason: str
    ) -> TipDistribution:
        """
        Adjust an existing tip distribution
        
        Args:
            db: Database session
            distribution_id: Distribution to adjust
            adjustments: List of adjustments to make
            adjusted_by: User making adjustments
            reason: Reason for adjustment
            
        Returns:
            Updated distribution
        """
        
        try:
            distribution = await db.get(TipDistribution, distribution_id)
            if not distribution:
                raise ValueError(f"Distribution {distribution_id} not found")
            
            # Store original distributions
            if 'adjustment_history' not in distribution.metadata:
                distribution.metadata['adjustment_history'] = []
            
            distribution.metadata['adjustment_history'].append({
                'timestamp': datetime.utcnow().isoformat(),
                'adjusted_by': adjusted_by,
                'reason': reason,
                'original_distributions': distribution.distributions
            })
            
            # Apply adjustments
            current_distributions = distribution.distributions or []
            
            for adjustment in adjustments:
                staff_id = adjustment['staff_id']
                new_amount = adjustment['new_amount']
                
                # Find and update the staff distribution
                for dist in current_distributions:
                    if dist['staff_id'] == staff_id:
                        dist['amount'] = float(new_amount)
                        dist['adjusted'] = True
                        dist['adjustment_reason'] = reason
                        break
            
            distribution.distributions = current_distributions
            await db.commit()
            
            return distribution
            
        except Exception as e:
            await db.rollback()
            logger.error(f"Failed to adjust tip distribution: {e}")
            raise


# Global service instance
tip_service = TipService()