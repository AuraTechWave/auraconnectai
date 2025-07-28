# backend/modules/customers/services/customer_service.py

from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_, func, desc
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, timedelta
import hashlib
import secrets
import logging

from ..models.customer_models import (
    Customer, CustomerAddress, CustomerPaymentMethod, CustomerNotification,
    CustomerReward, CustomerPreference, CustomerSegment, CustomerStatus, CustomerTier
)
from ..schemas.customer_schemas import (
    CustomerCreate, CustomerUpdate, CustomerSearchParams, CustomerStatusUpdate,
    CustomerTierUpdate, CustomerAddressCreate, CustomerAddressUpdate,
    CustomerPreferenceCreate, CustomerAnalytics
)
from backend.core.auth import get_password_hash, verify_password
from .security_service import CustomerSecurityService


logger = logging.getLogger(__name__)


class CustomerService:
    """Service for managing customer profiles and related operations"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create_customer(self, customer_data: CustomerCreate) -> Customer:
        """Create a new customer profile"""
        try:
            # Check if customer already exists
            existing = self.db.query(Customer).filter(
                Customer.email == customer_data.email
            ).first()
            
            if existing:
                if existing.deleted_at:
                    # Reactivate deleted customer
                    existing.deleted_at = None
                    existing.status = CustomerStatus.ACTIVE
                    self.db.commit()
                    return existing
                else:
                    raise ValueError(f"Customer with email {customer_data.email} already exists")
            
            # Create new customer
            customer = Customer(
                **customer_data.model_dump(exclude={'password', 'referral_code'})
            )
            
            # Validate and hash password if provided
            if customer_data.password:
                # Validate password strength
                password_validation = CustomerSecurityService.validate_password_strength(customer_data.password)
                if not password_validation['is_valid']:
                    raise ValueError(f"Password validation failed: {', '.join(password_validation['errors'])}")
                
                customer.password_hash = CustomerSecurityService.hash_password(customer_data.password)
                
                # Log security event
                CustomerSecurityService.log_security_event(
                    customer_id=None,
                    event_type="password_creation",
                    details=f"Password created for new customer {customer_data.email}"
                )
            
            # Generate referral code
            customer.referral_code = CustomerSecurityService.generate_referral_code()
            
            # Handle referral
            if customer_data.referral_code:
                referrer = self.db.query(Customer).filter(
                    Customer.referral_code == customer_data.referral_code
                ).first()
                if referrer:
                    customer.referred_by_customer_id = referrer.id
                    # Award referral points to referrer
                    self._award_referral_points(referrer)
            
            self.db.add(customer)
            self.db.commit()
            self.db.refresh(customer)
            
            # Create default preferences
            self._create_default_preferences(customer.id)
            
            logger.info(f"Created new customer: {customer.id}")
            return customer
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error creating customer: {str(e)}")
            raise
    
    def get_customer(self, customer_id: int, include_deleted: bool = False) -> Optional[Customer]:
        """Get customer by ID"""
        query = self.db.query(Customer).filter(Customer.id == customer_id)
        
        if not include_deleted:
            query = query.filter(Customer.deleted_at.is_(None))
        
        return query.first()
    
    def get_customer_by_email(self, email: str, include_deleted: bool = False) -> Optional[Customer]:
        """Get customer by email"""
        query = self.db.query(Customer).filter(Customer.email == email)
        
        if not include_deleted:
            query = query.filter(Customer.deleted_at.is_(None))
        
        return query.first()
    
    def update_customer(self, customer_id: int, update_data: CustomerUpdate) -> Customer:
        """Update customer profile"""
        customer = self.get_customer(customer_id)
        if not customer:
            raise ValueError(f"Customer {customer_id} not found")
        
        # Update fields
        update_dict = update_data.model_dump(exclude_unset=True)
        for field, value in update_dict.items():
            setattr(customer, field, value)
        
        customer.updated_at = datetime.utcnow()
        
        self.db.commit()
        self.db.refresh(customer)
        
        logger.info(f"Updated customer: {customer_id}")
        return customer
    
    def update_customer_status(self, customer_id: int, status_update: CustomerStatusUpdate) -> Customer:
        """Update customer status"""
        customer = self.get_customer(customer_id)
        if not customer:
            raise ValueError(f"Customer {customer_id} not found")
        
        old_status = customer.status
        customer.status = status_update.status
        
        # Handle soft delete
        if status_update.status == CustomerStatus.DELETED:
            customer.deleted_at = datetime.utcnow()
        
        self.db.commit()
        
        logger.info(f"Updated customer {customer_id} status from {old_status} to {status_update.status}")
        return customer
    
    def update_customer_tier(self, customer_id: int, tier_update: CustomerTierUpdate) -> Customer:
        """Update customer loyalty tier"""
        customer = self.get_customer(customer_id)
        if not customer:
            raise ValueError(f"Customer {customer_id} not found")
        
        old_tier = customer.tier
        customer.tier = tier_update.tier
        customer.tier_updated_at = datetime.utcnow()
        
        self.db.commit()
        
        # Create notification for tier change
        if old_tier != tier_update.tier:
            self._notify_tier_change(customer, old_tier, tier_update.tier)
        
        logger.info(f"Updated customer {customer_id} tier from {old_tier} to {tier_update.tier}")
        return customer
    
    def search_customers(self, params: CustomerSearchParams) -> Tuple[List[Customer], int]:
        """Search and filter customers with optimized queries"""
        # Base query with eager loading to avoid N+1 queries
        query = self.db.query(Customer).options(
            joinedload(Customer.addresses),
            joinedload(Customer.rewards).joinedload(CustomerReward.template),
            joinedload(Customer.preferences),
            joinedload(Customer.payment_methods),
            joinedload(Customer.notifications).load_only('id', 'type', 'status', 'created_at')
        ).filter(Customer.deleted_at.is_(None))
        
        # Text search with database-level filtering
        if params.query:
            search_term = f"%{params.query}%"
            query = query.filter(
                or_(
                    Customer.first_name.ilike(search_term),
                    Customer.last_name.ilike(search_term),
                    Customer.email.ilike(search_term),
                    Customer.phone.ilike(search_term)
                )
            )
        
        # Exact matches
        if params.email:
            query = query.filter(Customer.email == params.email)
        if params.phone:
            query = query.filter(Customer.phone == params.phone)
        
        # Filters with proper indexing
        if params.tier:
            query = query.filter(Customer.tier.in_(params.tier))
        if params.status:
            query = query.filter(Customer.status.in_(params.status))
        
        # Order metrics - using indexed columns
        if params.min_orders is not None:
            query = query.filter(Customer.total_orders >= params.min_orders)
        if params.max_orders is not None:
            query = query.filter(Customer.total_orders <= params.max_orders)
        if params.min_spent is not None:
            query = query.filter(Customer.total_spent >= params.min_spent)
        if params.max_spent is not None:
            query = query.filter(Customer.total_spent <= params.max_spent)
        
        # Date filters with indexed columns
        if params.created_after:
            query = query.filter(Customer.created_at >= params.created_after)
        if params.created_before:
            query = query.filter(Customer.created_at <= params.created_before)
        if params.last_order_after:
            query = query.filter(Customer.last_order_date >= params.last_order_after)
        if params.last_order_before:
            query = query.filter(Customer.last_order_date <= params.last_order_before)
        
        # Location filter
        if params.location_id:
            query = query.filter(Customer.preferred_location_id == params.location_id)
        
        # Tags filter using JSONB operators for better performance
        if params.tags:
            for tag in params.tags:
                query = query.filter(Customer.tags.op('?')(tag))
        
        # Active rewards filter with optimized subquery
        if params.has_active_rewards is not None:
            if params.has_active_rewards:
                # Use exists() subquery for better performance
                reward_subquery = self.db.query(CustomerReward.customer_id).filter(
                    and_(
                        CustomerReward.customer_id == Customer.id,
                        CustomerReward.status == "available",
                        or_(
                            CustomerReward.valid_until.is_(None),
                            CustomerReward.valid_until > datetime.utcnow()
                        )
                    )
                )
                query = query.filter(reward_subquery.exists())
        
        # Get total count with optimized query (without joins for counting)
        count_query = self.db.query(func.count(Customer.id)).filter(Customer.deleted_at.is_(None))
        
        # Apply same filters to count query
        if params.query:
            search_term = f"%{params.query}%"
            count_query = count_query.filter(
                or_(
                    Customer.first_name.ilike(search_term),
                    Customer.last_name.ilike(search_term),
                    Customer.email.ilike(search_term),
                    Customer.phone.ilike(search_term)
                )
            )
        if params.email:
            count_query = count_query.filter(Customer.email == params.email)
        if params.phone:
            count_query = count_query.filter(Customer.phone == params.phone)
        if params.tier:
            count_query = count_query.filter(Customer.tier.in_(params.tier))
        if params.status:
            count_query = count_query.filter(Customer.status.in_(params.status))
            
        total = count_query.scalar()
        
        # Sorting with proper column reference
        sort_column = getattr(Customer, params.sort_by)
        if params.sort_order == "desc":
            query = query.order_by(desc(sort_column))
        else:
            query = query.order_by(sort_column)
        
        # Pagination
        offset = (params.page - 1) * params.page_size
        customers = query.offset(offset).limit(params.page_size).all()
        
        return customers, total
    
    def get_customer_analytics(self, customer_id: int) -> CustomerAnalytics:
        """Get customer analytics and insights with optimized queries"""
        # Use joinedload to fetch customer with related data in one query
        customer = self.db.query(Customer).options(
            joinedload(Customer.orders),
            joinedload(Customer.preferences)
        ).filter(
            and_(
                Customer.id == customer_id,
                Customer.deleted_at.is_(None)
            )
        ).first()
        
        if not customer:
            raise ValueError(f"Customer {customer_id} not found")
        
        # Calculate order frequency
        order_frequency_days = None
        if customer.total_orders > 1 and customer.first_order_date and customer.last_order_date:
            days_active = (customer.last_order_date - customer.first_order_date).days
            if days_active > 0:
                order_frequency_days = days_active / (customer.total_orders - 1)
        
        # Get analytics data with optimized queries
        from backend.modules.orders.models.order_models import Order, OrderItem
        
        # Get favorite categories and items with single query
        favorite_data = self.db.query(
            OrderItem.menu_item_id,
            func.count(OrderItem.id).label('order_count'),
            func.sum(OrderItem.quantity).label('total_quantity')
        ).join(Order).filter(
            and_(
                Order.customer_id == customer_id,
                Order.deleted_at.is_(None),
                Order.status.in_(['completed', 'delivered'])
            )
        ).group_by(OrderItem.menu_item_id).order_by(desc('order_count')).limit(10).all()
        
        # Process favorite items
        favorite_items = []
        for item_id, order_count, total_quantity in favorite_data:
            favorite_items.append({
                "item_id": item_id,
                "order_count": order_count,
                "total_quantity": total_quantity
            })
        
        # Get order timing patterns with single query
        timing_data = self.db.query(
            extract('hour', Order.created_at).label('hour'),
            extract('dow', Order.created_at).label('day_of_week'),
            func.count(Order.id).label('order_count')
        ).filter(
            and_(
                Order.customer_id == customer_id,
                Order.deleted_at.is_(None)
            )
        ).group_by('hour', 'day_of_week').all()
        
        # Process timing patterns
        preferred_order_times = {}
        preferred_order_days = {}
        
        for hour, dow, count in timing_data:
            preferred_order_times[str(int(hour))] = preferred_order_times.get(str(int(hour)), 0) + count
            day_names = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
            day_name = day_names[int(dow)]
            preferred_order_days[day_name] = preferred_order_days.get(day_name, 0) + count
        
        # Calculate lifetime value and churn risk
        lifetime_value = customer.total_spent
        churn_risk_score = self._calculate_churn_risk(customer)
        
        # Days since last order
        last_order_days_ago = None
        if customer.last_order_date:
            last_order_days_ago = (datetime.utcnow() - customer.last_order_date).days
        
        return CustomerAnalytics(
            customer_id=customer_id,
            total_orders=customer.total_orders,
            total_spent=customer.total_spent,
            average_order_value=customer.average_order_value,
            order_frequency_days=order_frequency_days,
            favorite_categories=[],  # Will be populated by menu item lookup
            favorite_items=favorite_items,
            preferred_order_times=preferred_order_times,
            preferred_order_days=preferred_order_days,
            lifetime_value=lifetime_value,
            churn_risk_score=churn_risk_score,
            last_order_days_ago=last_order_days_ago
        )
    
    def add_loyalty_points(self, customer_id: int, points: int, reason: str) -> Customer:
        """Add loyalty points to customer"""
        customer = self.get_customer(customer_id)
        if not customer:
            raise ValueError(f"Customer {customer_id} not found")
        
        customer.loyalty_points += points
        customer.lifetime_points += points
        
        # Check for tier upgrade
        self._check_tier_upgrade(customer)
        
        self.db.commit()
        
        logger.info(f"Added {points} points to customer {customer_id} for {reason}")
        return customer
    
    def redeem_loyalty_points(self, customer_id: int, points: int, reward_id: Optional[int] = None) -> bool:
        """Redeem loyalty points"""
        customer = self.get_customer(customer_id)
        if not customer:
            raise ValueError(f"Customer {customer_id} not found")
        
        if customer.loyalty_points < points:
            raise ValueError("Insufficient loyalty points")
        
        customer.loyalty_points -= points
        
        # Mark reward as redeemed if provided
        if reward_id:
            reward = self.db.query(CustomerReward).filter(
                and_(
                    CustomerReward.id == reward_id,
                    CustomerReward.customer_id == customer_id
                )
            ).first()
            
            if reward:
                reward.status = "redeemed"
                reward.redeemed_at = datetime.utcnow()
        
        self.db.commit()
        
        logger.info(f"Redeemed {points} points for customer {customer_id}")
        return True
    
    # Address management
    def add_customer_address(self, customer_id: int, address_data: CustomerAddressCreate) -> CustomerAddress:
        """Add a new address for customer"""
        customer = self.get_customer(customer_id)
        if not customer:
            raise ValueError(f"Customer {customer_id} not found")
        
        # If this is the first or default address, set as default
        is_first_address = self.db.query(CustomerAddress).filter(
            CustomerAddress.customer_id == customer_id
        ).count() == 0
        
        address = CustomerAddress(
            customer_id=customer_id,
            **address_data.model_dump()
        )
        
        if is_first_address or address_data.is_default:
            # Remove default flag from other addresses
            self.db.query(CustomerAddress).filter(
                and_(
                    CustomerAddress.customer_id == customer_id,
                    CustomerAddress.is_default == True
                )
            ).update({"is_default": False})
            
            address.is_default = True
            customer.default_address_id = None  # Will be set after commit
        
        self.db.add(address)
        self.db.commit()
        self.db.refresh(address)
        
        # Update default address reference
        if address.is_default:
            customer.default_address_id = address.id
            self.db.commit()
        
        return address
    
    def update_customer_address(self, address_id: int, update_data: CustomerAddressUpdate) -> CustomerAddress:
        """Update customer address"""
        address = self.db.query(CustomerAddress).filter(
            CustomerAddress.id == address_id
        ).first()
        
        if not address:
            raise ValueError(f"Address {address_id} not found")
        
        # Update fields
        update_dict = update_data.model_dump(exclude_unset=True)
        for field, value in update_dict.items():
            setattr(address, field, value)
        
        # Handle default address change
        if update_data.is_default is True:
            self.db.query(CustomerAddress).filter(
                and_(
                    CustomerAddress.customer_id == address.customer_id,
                    CustomerAddress.id != address_id,
                    CustomerAddress.is_default == True
                )
            ).update({"is_default": False})
            
            # Update customer's default address
            customer = self.get_customer(address.customer_id)
            if customer:
                customer.default_address_id = address_id
        
        self.db.commit()
        self.db.refresh(address)
        
        return address
    
    def delete_customer_address(self, address_id: int) -> bool:
        """Delete customer address (soft delete)"""
        address = self.db.query(CustomerAddress).filter(
            CustomerAddress.id == address_id
        ).first()
        
        if not address:
            raise ValueError(f"Address {address_id} not found")
        
        address.deleted_at = datetime.utcnow()
        
        # If this was the default address, clear it
        if address.is_default:
            customer = self.get_customer(address.customer_id)
            if customer:
                customer.default_address_id = None
        
        self.db.commit()
        return True
    
    # Preference management
    def set_customer_preference(self, customer_id: int, preference_data: CustomerPreferenceCreate) -> CustomerPreference:
        """Set or update customer preference"""
        customer = self.get_customer(customer_id)
        if not customer:
            raise ValueError(f"Customer {customer_id} not found")
        
        # Check if preference exists
        preference = self.db.query(CustomerPreference).filter(
            and_(
                CustomerPreference.customer_id == customer_id,
                CustomerPreference.category == preference_data.category,
                CustomerPreference.preference_key == preference_data.preference_key
            )
        ).first()
        
        if preference:
            # Update existing preference
            preference.preference_value = preference_data.preference_value
            preference.source = preference_data.source
            preference.confidence_score = preference_data.confidence_score
        else:
            # Create new preference
            preference = CustomerPreference(
                customer_id=customer_id,
                **preference_data.model_dump()
            )
            self.db.add(preference)
        
        self.db.commit()
        self.db.refresh(preference)
        
        return preference
    
    def get_customer_preferences(self, customer_id: int, category: Optional[str] = None) -> List[CustomerPreference]:
        """Get customer preferences"""
        query = self.db.query(CustomerPreference).filter(
            CustomerPreference.customer_id == customer_id
        )
        
        if category:
            query = query.filter(CustomerPreference.category == category)
        
        return query.all()
    
    # Helper methods
    def _generate_referral_code(self) -> str:
        """Generate unique referral code"""
        while True:
            code = secrets.token_urlsafe(6).upper()
            existing = self.db.query(Customer).filter(
                Customer.referral_code == code
            ).first()
            if not existing:
                return code
    
    def _award_referral_points(self, referrer: Customer, points: int = 100):
        """Award points for successful referral"""
        referrer.loyalty_points += points
        referrer.lifetime_points += points
        self._check_tier_upgrade(referrer)
    
    def _check_tier_upgrade(self, customer: Customer):
        """Check if customer qualifies for tier upgrade using configurable system"""
        from ..models.loyalty_config import LoyaltyService
        
        loyalty_service = LoyaltyService(self.db)
        
        # Calculate appropriate tier based on current configuration
        new_tier_name = loyalty_service.calculate_tier_for_customer(customer)
        
        # Convert string to enum (assuming tier names match enum values)
        tier_mapping = {
            'bronze': CustomerTier.BRONZE,
            'silver': CustomerTier.SILVER,
            'gold': CustomerTier.GOLD,
            'platinum': CustomerTier.PLATINUM,
            'vip': CustomerTier.VIP
        }
        
        new_tier = tier_mapping.get(new_tier_name.lower(), customer.tier)
        
        # Update tier if changed
        if new_tier != customer.tier:
            old_tier = customer.tier
            customer.tier = new_tier
            customer.tier_updated_at = datetime.utcnow()
            
            # Create notification for tier upgrade
            self._notify_tier_change(customer, old_tier, new_tier)
    
    def _calculate_churn_risk(self, customer: Customer) -> float:
        """Calculate customer churn risk score (0-1)"""
        if not customer.last_order_date:
            return 0.5  # No order history
        
        days_since_last_order = (datetime.utcnow() - customer.last_order_date).days
        
        # Simple heuristic based on days since last order
        if days_since_last_order <= 30:
            return 0.1
        elif days_since_last_order <= 60:
            return 0.3
        elif days_since_last_order <= 90:
            return 0.5
        elif days_since_last_order <= 180:
            return 0.7
        else:
            return 0.9
    
    def _notify_tier_change(self, customer: Customer, old_tier: CustomerTier, new_tier: CustomerTier):
        """Create notification for tier change"""
        notification = CustomerNotification(
            customer_id=customer.id,
            type="tier_change",
            channel="email",
            subject=f"Congratulations! You've been upgraded to {new_tier.value.title()}",
            content=f"Your loyalty tier has been upgraded from {old_tier.value.title()} to {new_tier.value.title()}!",
            metadata={"old_tier": old_tier.value, "new_tier": new_tier.value}
        )
        self.db.add(notification)
    
    def _create_default_preferences(self, customer_id: int):
        """Create default preferences for new customer"""
        default_prefs = [
            CustomerPreference(
                customer_id=customer_id,
                category="communication",
                preference_key="email_marketing",
                preference_value=True,
                source="default"
            ),
            CustomerPreference(
                customer_id=customer_id,
                category="communication",
                preference_key="sms_notifications",
                preference_value=False,
                source="default"
            )
        ]
        
        for pref in default_prefs:
            self.db.add(pref)


class CustomerAuthService:
    """Service for customer authentication"""
    
    def __init__(self, db: Session):
        self.db = db
        self.customer_service = CustomerService(db)
    
    def authenticate_customer(self, email: str, password: str) -> Optional[Customer]:
        """Authenticate customer with email and password"""
        customer = self.customer_service.get_customer_by_email(email)
        
        if not customer or not customer.password_hash:
            return None
        
        if not verify_password(password, customer.password_hash):
            return None
        
        # Update login info
        customer.last_login = datetime.utcnow()
        customer.login_count += 1
        self.db.commit()
        
        return customer
    
    def register_customer(self, customer_data: CustomerCreate) -> Customer:
        """Register new customer with password"""
        if not customer_data.password:
            raise ValueError("Password is required for registration")
        
        return self.customer_service.create_customer(customer_data)