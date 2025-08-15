# backend/modules/customers/services/order_history_service.py

from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_, func, desc, extract
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, timedelta
from decimal import Decimal
import logging

from modules.orders.models.order_models import Order, OrderItem
from core.menu_models import MenuItem
from ..models.customer_models import Customer
from ..schemas.customer_schemas import OrderSummary, MenuItemSummary


logger = logging.getLogger(__name__)


class OrderHistoryService:
    """Service for managing customer order history and analytics"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_customer_orders(
        self, 
        customer_id: int, 
        status_filter: Optional[List[str]] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        limit: int = 20,
        offset: int = 0
    ) -> Tuple[List[Order], int]:
        """Get customer's order history with filtering"""
        query = self.db.query(Order).filter(
            and_(
                Order.customer_id == customer_id,
                Order.deleted_at.is_(None)
            )
        )
        
        # Apply filters
        if status_filter:
            query = query.filter(Order.status.in_(status_filter))
        
        if date_from:
            query = query.filter(Order.created_at >= date_from)
        
        if date_to:
            query = query.filter(Order.created_at <= date_to)
        
        # Get total count before pagination
        total = query.count()
        
        # Get orders with pagination and eager load order_items to avoid N+1
        orders = query.options(joinedload(Order.order_items))\
                     .order_by(desc(Order.created_at))\
                     .offset(offset)\
                     .limit(limit)\
                     .all()
        
        return orders, total
    
    def get_order_summaries(
        self, 
        customer_id: int, 
        limit: int = 10
    ) -> List[OrderSummary]:
        """Get simplified order summaries for customer profile"""
        orders = self.db.query(Order).options(
            joinedload(Order.order_items)  # Fix N+1: Eager load order_items
        ).filter(
            and_(
                Order.customer_id == customer_id,
                Order.deleted_at.is_(None)
            )
        ).order_by(desc(Order.created_at)).limit(limit).all()
        
        summaries = []
        for order in orders:
            # Calculate total amount and item count
            total_amount = sum(item.price * item.quantity for item in order.order_items)
            item_count = sum(item.quantity for item in order.order_items)
            
            summary = OrderSummary(
                id=order.id,
                order_number=f"ORD-{order.id:06d}",
                status=order.status,
                total_amount=float(total_amount),
                item_count=item_count,
                created_at=order.created_at,
                fulfilled_at=order.updated_at if order.status == "completed" else None
            )
            summaries.append(summary)
        
        return summaries
    
    def get_favorite_items(
        self, 
        customer_id: int, 
        limit: int = 10,
        min_orders: int = 2
    ) -> List[MenuItemSummary]:
        """Get customer's most frequently ordered items"""
        # Query to get item order counts
        item_counts = self.db.query(
            OrderItem.menu_item_id,
            func.count(OrderItem.id).label('order_count'),
            func.sum(OrderItem.quantity).label('total_quantity')
        ).join(
            Order
        ).filter(
            and_(
                Order.customer_id == customer_id,
                Order.deleted_at.is_(None),
                Order.status.in_(['completed', 'delivered'])
            )
        ).group_by(
            OrderItem.menu_item_id
        ).having(
            func.count(OrderItem.id) >= min_orders
        ).order_by(
            desc('order_count')
        ).limit(limit).all()
        
        # Fix N+1: Batch load menu items with eager loading for categories
        item_ids = [item_id for item_id, _, _ in item_counts]
        menu_items = self.db.query(MenuItem).options(
            joinedload(MenuItem.category)  # Eager load category relationship
        ).filter(
            MenuItem.id.in_(item_ids)
        ).all()
        
        # Create a mapping for quick lookup
        menu_item_map = {item.id: item for item in menu_items}
        
        # Build favorites list using the pre-loaded items
        favorites = []
        for item_id, order_count, total_quantity in item_counts:
            menu_item = menu_item_map.get(item_id)
            
            if menu_item:
                favorite = MenuItemSummary(
                    id=menu_item.id,
                    name=menu_item.name,
                    category=menu_item.category.name if menu_item.category else "Uncategorized",
                    price=float(menu_item.price),
                    image_url=menu_item.image_url,
                    order_count=order_count
                )
                favorites.append(favorite)
        
        return favorites
    
    def get_order_analytics(
        self, 
        customer_id: int,
        period_days: int = 365
    ) -> Dict[str, Any]:
        """Get detailed order analytics for a customer"""
        since_date = datetime.utcnow() - timedelta(days=period_days)
        
        # Get all orders in period
        orders = self.db.query(Order).filter(
            and_(
                Order.customer_id == customer_id,
                Order.deleted_at.is_(None),
                Order.created_at >= since_date
            )
        ).all()
        
        if not orders:
            return {
                "total_orders": 0,
                "total_spent": 0,
                "average_order_value": 0,
                "order_frequency_days": None,
                "preferred_order_times": {},
                "preferred_order_days": {},
                "monthly_spending": {},
                "order_status_breakdown": {}
            }
        
        # Calculate metrics
        total_orders = len(orders)
        total_spent = 0
        order_times = {}
        order_days = {}
        monthly_spending = {}
        status_breakdown = {}
        
        for order in orders:
            # Calculate order total
            order_total = sum(
                item.price * item.quantity 
                for item in order.order_items
            )
            total_spent += float(order_total)
            
            # Track order time patterns
            hour = order.created_at.hour
            order_times[hour] = order_times.get(hour, 0) + 1
            
            # Track order day patterns
            day_name = order.created_at.strftime("%A")
            order_days[day_name] = order_days.get(day_name, 0) + 1
            
            # Track monthly spending
            month_key = order.created_at.strftime("%Y-%m")
            monthly_spending[month_key] = monthly_spending.get(month_key, 0) + float(order_total)
            
            # Track status breakdown
            status_breakdown[order.status] = status_breakdown.get(order.status, 0) + 1
        
        # Calculate order frequency
        if total_orders > 1:
            first_order = min(orders, key=lambda x: x.created_at)
            last_order = max(orders, key=lambda x: x.created_at)
            days_between = (last_order.created_at - first_order.created_at).days
            order_frequency_days = days_between / (total_orders - 1) if days_between > 0 else None
        else:
            order_frequency_days = None
        
        return {
            "total_orders": total_orders,
            "total_spent": total_spent,
            "average_order_value": total_spent / total_orders if total_orders > 0 else 0,
            "order_frequency_days": order_frequency_days,
            "preferred_order_times": order_times,
            "preferred_order_days": order_days,
            "monthly_spending": monthly_spending,
            "order_status_breakdown": status_breakdown
        }
    
    def get_reorder_suggestions(
        self, 
        customer_id: int,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Get intelligent reorder suggestions based on order history"""
        # Get last order date
        last_order = self.db.query(Order).filter(
            and_(
                Order.customer_id == customer_id,
                Order.deleted_at.is_(None)
            )
        ).order_by(desc(Order.created_at)).first()
        
        if not last_order:
            return []
        
        days_since_last_order = (datetime.utcnow() - last_order.created_at).days
        
        # Get items ordered multiple times
        frequent_items = self.db.query(
            OrderItem.menu_item_id,
            func.count(OrderItem.id).label('order_count'),
            func.max(Order.created_at).label('last_ordered')
        ).join(
            Order
        ).filter(
            and_(
                Order.customer_id == customer_id,
                Order.deleted_at.is_(None),
                Order.status.in_(['completed', 'delivered'])
            )
        ).group_by(
            OrderItem.menu_item_id
        ).having(
            func.count(OrderItem.id) >= 2
        ).all()
        
        suggestions = []
        for item_id, order_count, last_ordered in frequent_items:
            # Calculate average days between orders
            days_since_item_ordered = (datetime.utcnow() - last_ordered).days
            
            # Get item details
            menu_item = self.db.query(MenuItem).filter(
                MenuItem.id == item_id
            ).first()
            
            if menu_item and menu_item.is_available:
                # Simple reorder score based on frequency and recency
                reorder_score = order_count / (days_since_item_ordered + 1)
                
                suggestions.append({
                    "item_id": menu_item.id,
                    "item_name": menu_item.name,
                    "category": menu_item.category.name if menu_item.category else "Uncategorized",
                    "price": float(menu_item.price),
                    "order_count": order_count,
                    "days_since_last_ordered": days_since_item_ordered,
                    "reorder_score": reorder_score
                })
        
        # Sort by reorder score and return top suggestions
        suggestions.sort(key=lambda x: x['reorder_score'], reverse=True)
        return suggestions[:limit]
    
    def get_spending_trends(
        self, 
        customer_id: int,
        period_months: int = 12
    ) -> Dict[str, Any]:
        """Analyze customer spending trends"""
        since_date = datetime.utcnow() - timedelta(days=period_months * 30)
        
        # Get monthly spending data
        monthly_data = self.db.query(
            extract('year', Order.created_at).label('year'),
            extract('month', Order.created_at).label('month'),
            func.count(Order.id).label('order_count'),
            func.sum(
                self.db.query(
                    func.sum(OrderItem.price * OrderItem.quantity)
                ).filter(
                    OrderItem.order_id == Order.id
                ).scalar_subquery()
            ).label('total_spent')
        ).filter(
            and_(
                Order.customer_id == customer_id,
                Order.deleted_at.is_(None),
                Order.created_at >= since_date,
                Order.status.in_(['completed', 'delivered'])
            )
        ).group_by(
            'year', 'month'
        ).order_by(
            'year', 'month'
        ).all()
        
        # Format data
        trends = []
        for year, month, order_count, total_spent in monthly_data:
            trends.append({
                "year": int(year),
                "month": int(month),
                "month_name": datetime(int(year), int(month), 1).strftime("%B"),
                "order_count": order_count,
                "total_spent": float(total_spent) if total_spent else 0,
                "average_order_value": float(total_spent) / order_count if order_count > 0 else 0
            })
        
        # Calculate trend direction
        if len(trends) >= 2:
            recent_avg = sum(t['total_spent'] for t in trends[-3:]) / min(3, len(trends))
            older_avg = sum(t['total_spent'] for t in trends[:-3]) / max(1, len(trends) - 3)
            trend_direction = "increasing" if recent_avg > older_avg else "decreasing"
            trend_percentage = ((recent_avg - older_avg) / older_avg * 100) if older_avg > 0 else 0
        else:
            trend_direction = "stable"
            trend_percentage = 0
        
        return {
            "monthly_data": trends,
            "trend_direction": trend_direction,
            "trend_percentage": trend_percentage,
            "highest_spending_month": max(trends, key=lambda x: x['total_spent']) if trends else None,
            "most_active_month": max(trends, key=lambda x: x['order_count']) if trends else None
        }
    
    def update_customer_order_stats(self, customer_id: int) -> Customer:
        """Update customer's order statistics (should be called after order completion)"""
        customer = self.db.query(Customer).filter(
            Customer.id == customer_id
        ).first()
        
        if not customer:
            raise ValueError(f"Customer {customer_id} not found")
        
        # Calculate order statistics
        order_stats = self.db.query(
            func.count(Order.id).label('total_orders'),
            func.sum(
                self.db.query(
                    func.sum(OrderItem.price * OrderItem.quantity)
                ).filter(
                    OrderItem.order_id == Order.id
                ).scalar_subquery()
            ).label('total_spent'),
            func.min(Order.created_at).label('first_order_date'),
            func.max(Order.created_at).label('last_order_date')
        ).filter(
            and_(
                Order.customer_id == customer_id,
                Order.deleted_at.is_(None),
                Order.status.in_(['completed', 'delivered'])
            )
        ).first()
        
        # Update customer stats
        if order_stats.total_orders:
            customer.total_orders = order_stats.total_orders
            new_total_spent = float(order_stats.total_spent) if order_stats.total_spent else 0
            
            # Handle null safety for lifetime_value
            if customer.lifetime_value is None:
                # For existing customers without lifetime_value, initialize it to total_spent
                customer.lifetime_value = float(customer.total_spent) if customer.total_spent else 0
            
            # Calculate refunds as the difference between current total_spent and lifetime_value
            # This represents the total amount refunded to the customer
            current_lifetime_value = float(customer.lifetime_value)
            current_total_spent = float(customer.total_spent) if customer.total_spent else 0
            
            # Safeguard: lifetime_value should never exceed total_spent
            if current_lifetime_value > current_total_spent:
                logger.warning(f"Data inconsistency for customer {customer.id}: lifetime_value ({current_lifetime_value}) > total_spent ({current_total_spent}). Correcting...")
                current_lifetime_value = current_total_spent
            
            # Calculate total refunds (should always be >= 0)
            total_refunds = max(0, current_total_spent - current_lifetime_value)
            
            # Update total_spent to the newly calculated value
            customer.total_spent = new_total_spent
            
            # Apply the refund history to the new total_spent
            # Ensure lifetime_value is between 0 and total_spent
            customer.lifetime_value = max(0, min(new_total_spent, new_total_spent - total_refunds))
            
            customer.average_order_value = customer.total_spent / customer.total_orders if customer.total_orders else 0
            customer.first_order_date = order_stats.first_order_date
            customer.last_order_date = order_stats.last_order_date
        
        self.db.commit()
        self.db.refresh(customer)
        
        logger.info(f"Updated order stats for customer {customer_id}")
        return customer