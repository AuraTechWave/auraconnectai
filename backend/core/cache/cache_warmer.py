"""
Cache Warming Utilities

Pre-populate cache with frequently accessed data to improve performance.
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional, Callable
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from sqlalchemy.orm import Session

from .cache_manager import cache_manager, CacheTTL
from core.database import get_db

logger = logging.getLogger(__name__)


class CacheWarmer:
    """
    Cache warming coordinator
    """
    
    def __init__(self, db: Session):
        """
        Initialize cache warmer
        
        Args:
            db: Database session
        """
        self.db = db
        self.warmers: Dict[str, Callable] = {}
        self._register_warmers()
    
    def _register_warmers(self):
        """Register all cache warming functions"""
        self.warmers = {
            'menu': self.warm_menu_cache,
            'permissions': self.warm_permissions_cache,
            'settings': self.warm_settings_cache,
            'analytics': self.warm_analytics_cache,
        }
    
    def warm_menu_cache(self, tenant_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Warm menu items and categories cache
        
        Args:
            tenant_id: Optional tenant ID to warm cache for specific tenant
            
        Returns:
            Warming statistics
        """
        stats = {'items_cached': 0, 'categories_cached': 0, 'errors': 0}
        
        try:
            from modules.menu.models import MenuItem, MenuCategory
            
            # Query scope
            if tenant_id:
                menu_items = self.db.query(MenuItem).filter_by(
                    restaurant_id=tenant_id,
                    is_active=True
                ).all()
                categories = self.db.query(MenuCategory).filter_by(
                    restaurant_id=tenant_id,
                    is_active=True
                ).all()
            else:
                # Warm cache for all active restaurants (be careful with large datasets)
                menu_items = self.db.query(MenuItem).filter_by(is_active=True).limit(1000).all()
                categories = self.db.query(MenuCategory).filter_by(is_active=True).limit(100).all()
            
            # Cache menu items
            for item in menu_items:
                cache_key = cache_manager.generate_key(
                    'menu',
                    'item',
                    item.id,
                    tenant_id=item.restaurant_id
                )
                
                item_data = {
                    'id': item.id,
                    'name': item.name,
                    'description': item.description,
                    'price': float(item.price),
                    'category_id': item.category_id,
                    'is_available': item.is_available,
                    'restaurant_id': item.restaurant_id
                }
                
                if cache_manager.set('menu', cache_key, item_data, CacheTTL.MENU_ITEMS.value):
                    stats['items_cached'] += 1
                else:
                    stats['errors'] += 1
            
            # Cache categories
            for category in categories:
                cache_key = cache_manager.generate_key(
                    'menu',
                    'category',
                    category.id,
                    tenant_id=category.restaurant_id
                )
                
                category_data = {
                    'id': category.id,
                    'name': category.name,
                    'description': category.description,
                    'display_order': category.display_order,
                    'restaurant_id': category.restaurant_id
                }
                
                if cache_manager.set('menu', cache_key, category_data, CacheTTL.MENU_ITEMS.value):
                    stats['categories_cached'] += 1
                else:
                    stats['errors'] += 1
            
            logger.info(f"Menu cache warmed: {stats}")
            
        except Exception as e:
            logger.error(f"Error warming menu cache: {e}")
            stats['errors'] += 1
        
        return stats
    
    def warm_permissions_cache(self, user_ids: Optional[List[int]] = None) -> Dict[str, Any]:
        """
        Warm user permissions cache
        
        Args:
            user_ids: Optional list of user IDs to warm cache for
            
        Returns:
            Warming statistics
        """
        stats = {'users_cached': 0, 'permissions_cached': 0, 'errors': 0}
        
        try:
            from modules.auth.models import User, Permission, Role
            
            # Query scope
            if user_ids:
                users = self.db.query(User).filter(User.id.in_(user_ids)).all()
            else:
                # Get recently active users
                cutoff_time = datetime.utcnow() - timedelta(hours=24)
                users = self.db.query(User).filter(
                    User.last_login >= cutoff_time
                ).limit(100).all()
            
            for user in users:
                # Cache user permissions
                permissions = []
                if user.role:
                    permissions = [p.name for p in user.role.permissions]
                
                cache_key = cache_manager.generate_key(
                    'permissions',
                    'user',
                    user_id=user.id
                )
                
                permission_data = {
                    'user_id': user.id,
                    'role': user.role.name if user.role else None,
                    'permissions': permissions,
                    'restaurant_id': user.restaurant_id
                }
                
                if cache_manager.set('permissions', cache_key, permission_data, CacheTTL.USER_PERMISSIONS.value):
                    stats['users_cached'] += 1
                    stats['permissions_cached'] += len(permissions)
                else:
                    stats['errors'] += 1
            
            logger.info(f"Permissions cache warmed: {stats}")
            
        except Exception as e:
            logger.error(f"Error warming permissions cache: {e}")
            stats['errors'] += 1
        
        return stats
    
    def warm_settings_cache(self, tenant_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Warm restaurant settings cache
        
        Args:
            tenant_id: Optional tenant ID to warm cache for specific tenant
            
        Returns:
            Warming statistics
        """
        stats = {'settings_cached': 0, 'errors': 0}
        
        try:
            from modules.restaurants.models import Restaurant, RestaurantSettings
            
            # Query scope
            if tenant_id:
                restaurants = self.db.query(Restaurant).filter_by(id=tenant_id).all()
            else:
                # Get all active restaurants
                restaurants = self.db.query(Restaurant).filter_by(is_active=True).limit(100).all()
            
            for restaurant in restaurants:
                # Get settings
                settings = self.db.query(RestaurantSettings).filter_by(
                    restaurant_id=restaurant.id
                ).first()
                
                if settings:
                    cache_key = cache_manager.generate_key(
                        'settings',
                        'restaurant',
                        tenant_id=restaurant.id
                    )
                    
                    settings_data = {
                        'restaurant_id': restaurant.id,
                        'name': restaurant.name,
                        'timezone': settings.timezone,
                        'currency': settings.currency,
                        'tax_rate': float(settings.tax_rate) if settings.tax_rate else 0,
                        'service_charge': float(settings.service_charge) if settings.service_charge else 0,
                        'opening_hours': settings.opening_hours,
                        'features': settings.features or {}
                    }
                    
                    if cache_manager.set('settings', cache_key, settings_data, CacheTTL.RESTAURANT_SETTINGS.value):
                        stats['settings_cached'] += 1
                    else:
                        stats['errors'] += 1
            
            logger.info(f"Settings cache warmed: {stats}")
            
        except Exception as e:
            logger.error(f"Error warming settings cache: {e}")
            stats['errors'] += 1
        
        return stats
    
    def warm_analytics_cache(self, tenant_id: int, days: int = 7) -> Dict[str, Any]:
        """
        Warm analytics aggregations cache
        
        Args:
            tenant_id: Tenant ID to warm cache for
            days: Number of days to pre-calculate
            
        Returns:
            Warming statistics
        """
        stats = {'days_cached': 0, 'metrics_cached': 0, 'errors': 0}
        
        try:
            from modules.analytics.services import AnalyticsService
            
            service = AnalyticsService(self.db)
            end_date = datetime.utcnow().date()
            
            for i in range(days):
                date = end_date - timedelta(days=i)
                
                # Cache daily metrics
                metrics = [
                    'total_revenue',
                    'total_orders',
                    'average_order_value',
                    'top_items',
                    'peak_hours'
                ]
                
                for metric in metrics:
                    cache_key = cache_manager.generate_key(
                        'analytics',
                        metric,
                        date.isoformat(),
                        tenant_id=tenant_id
                    )
                    
                    # Calculate metric (this would call actual analytics service)
                    metric_data = self._calculate_metric(tenant_id, date, metric)
                    
                    if metric_data and cache_manager.set(
                        'analytics',
                        cache_key,
                        metric_data,
                        CacheTTL.ANALYTICS_AGGREGATIONS.value
                    ):
                        stats['metrics_cached'] += 1
                    else:
                        stats['errors'] += 1
                
                stats['days_cached'] += 1
            
            logger.info(f"Analytics cache warmed: {stats}")
            
        except Exception as e:
            logger.error(f"Error warming analytics cache: {e}")
            stats['errors'] += 1
        
        return stats
    
    def _calculate_metric(self, tenant_id: int, date: datetime.date, metric: str) -> Optional[Dict[str, Any]]:
        """Calculate analytics metric (placeholder)"""
        # This would call actual analytics calculation
        # For now, return sample data
        return {
            'metric': metric,
            'date': date.isoformat(),
            'value': 0,
            'tenant_id': tenant_id
        }
    
    def warm_all(self, tenant_id: Optional[int] = None, parallel: bool = True) -> Dict[str, Any]:
        """
        Warm all caches
        
        Args:
            tenant_id: Optional tenant ID to warm cache for specific tenant
            parallel: Run warmers in parallel
            
        Returns:
            Combined warming statistics
        """
        all_stats = {}
        
        if parallel:
            # Run warmers in parallel
            with ThreadPoolExecutor(max_workers=4) as executor:
                futures = {}
                
                # Submit warming tasks
                for name, warmer in self.warmers.items():
                    if name == 'analytics' and tenant_id:
                        future = executor.submit(warmer, tenant_id)
                    elif name in ['menu', 'settings']:
                        future = executor.submit(warmer, tenant_id)
                    elif name == 'permissions':
                        future = executor.submit(warmer)
                    else:
                        continue
                    
                    futures[future] = name
                
                # Collect results
                for future in as_completed(futures):
                    name = futures[future]
                    try:
                        stats = future.result()
                        all_stats[name] = stats
                    except Exception as e:
                        logger.error(f"Error in {name} warmer: {e}")
                        all_stats[name] = {'error': str(e)}
        else:
            # Run warmers sequentially
            for name, warmer in self.warmers.items():
                try:
                    if name == 'analytics' and tenant_id:
                        stats = warmer(tenant_id)
                    elif name in ['menu', 'settings']:
                        stats = warmer(tenant_id)
                    elif name == 'permissions':
                        stats = warmer()
                    else:
                        continue
                    
                    all_stats[name] = stats
                except Exception as e:
                    logger.error(f"Error in {name} warmer: {e}")
                    all_stats[name] = {'error': str(e)}
        
        # Add summary
        total_cached = sum(
            sum(v for k, v in stats.items() if k.endswith('_cached'))
            for stats in all_stats.values()
            if isinstance(stats, dict) and 'error' not in stats
        )
        
        total_errors = sum(
            stats.get('errors', 0)
            for stats in all_stats.values()
            if isinstance(stats, dict)
        )
        
        all_stats['summary'] = {
            'total_items_cached': total_cached,
            'total_errors': total_errors,
            'warmers_run': len(all_stats) - 1
        }
        
        logger.info(f"Cache warming complete: {all_stats['summary']}")
        
        return all_stats


async def warm_cache_async(tenant_id: Optional[int] = None) -> Dict[str, Any]:
    """
    Asynchronous cache warming
    
    Args:
        tenant_id: Optional tenant ID to warm cache for specific tenant
        
    Returns:
        Warming statistics
    """
    # Properly manage database session
    db_gen = get_db()
    db = None
    
    try:
        db = next(db_gen)
        warmer = CacheWarmer(db)
        stats = warmer.warm_all(tenant_id, parallel=True)
        return stats
    finally:
        if db:
            db.close()
        try:
            next(db_gen)  # Trigger generator cleanup
        except StopIteration:
            pass


def schedule_cache_warming(tenant_id: Optional[int] = None, interval_minutes: int = 30):
    """
    Schedule periodic cache warming
    
    Args:
        tenant_id: Optional tenant ID to warm cache for specific tenant
        interval_minutes: Warming interval in minutes
    """
    import schedule
    import time
    import threading
    
    def warm_job():
        # Properly manage database session
        db_gen = get_db()
        db = None
        
        try:
            db = next(db_gen)
            warmer = CacheWarmer(db)
            warmer.warm_all(tenant_id)
        except Exception as e:
            logger.error(f"Scheduled cache warming failed: {e}")
        finally:
            if db:
                db.close()
            try:
                next(db_gen)  # Trigger generator cleanup
            except StopIteration:
                pass
    
    # Schedule job
    schedule.every(interval_minutes).minutes.do(warm_job)
    
    # Run in background thread
    def run_schedule():
        while True:
            schedule.run_pending()
            time.sleep(60)  # Check every minute
    
    thread = threading.Thread(target=run_schedule, daemon=True)
    thread.start()
    
    logger.info(f"Cache warming scheduled every {interval_minutes} minutes")