# backend/modules/promotions/services/async_analytics_service.py

import asyncio
import aioredis
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
from typing import Optional, List, Dict, Any, Callable
from datetime import datetime, timedelta
import logging
import json
from concurrent.futures import ThreadPoolExecutor
import time

from backend.core.config import settings
from backend.modules.promotions.services.cache_service import cache_service

logger = logging.getLogger(__name__)


class AsyncAnalyticsService:
    """Asynchronous analytics service for high-performance data processing"""
    
    def __init__(self):
        self.cache = cache_service
        self.thread_pool = ThreadPoolExecutor(max_workers=4)
        self._async_engine = None
        self._async_session_factory = None
        self._redis_pool = None
    
    async def _get_async_engine(self):
        """Get or create async database engine"""
        if not self._async_engine:
            # Convert sync database URL to async
            database_url = getattr(settings, 'DATABASE_URL', 'postgresql://localhost/auraconnect')
            async_url = database_url.replace('postgresql://', 'postgresql+asyncpg://')
            
            self._async_engine = create_async_engine(
                async_url,
                echo=False,
                pool_size=5,
                max_overflow=10,
                pool_pre_ping=True
            )
            
            self._async_session_factory = sessionmaker(
                self._async_engine,
                class_=AsyncSession,
                expire_on_commit=False
            )
        
        return self._async_engine
    
    async def _get_async_session(self) -> AsyncSession:
        """Get async database session"""
        if not self._async_session_factory:
            await self._get_async_engine()
        
        return self._async_session_factory()
    
    async def _get_redis_pool(self):
        """Get or create Redis connection pool"""
        if not self._redis_pool and self.cache.cache_enabled:
            try:
                self._redis_pool = aioredis.ConnectionPool.from_url(
                    f"redis://{getattr(settings, 'REDIS_HOST', 'localhost')}:{getattr(settings, 'REDIS_PORT', 6379)}",
                    password=getattr(settings, 'REDIS_PASSWORD', None),
                    db=getattr(settings, 'REDIS_DB', 0)
                )
            except Exception as e:
                logger.error(f"Failed to create Redis pool: {e}")
                self._redis_pool = None
        
        return self._redis_pool
    
    async def generate_daily_analytics_batch(
        self,
        start_date: datetime,
        end_date: datetime,
        batch_size: int = 1000
    ) -> Dict[str, Any]:
        """Generate analytics for multiple days in parallel"""
        
        tasks = []
        current_date = start_date
        
        while current_date <= end_date:
            task = self.generate_daily_analytics_async(current_date)
            tasks.append(task)
            current_date += timedelta(days=1)
        
        # Process all days concurrently
        start_time = time.time()
        results = await asyncio.gather(*tasks, return_exceptions=True)
        processing_time = time.time() - start_time
        
        # Aggregate results
        successful_results = []
        errors = []
        
        for i, result in enumerate(results):
            target_date = start_date + timedelta(days=i)
            
            if isinstance(result, Exception):
                errors.append({
                    "date": target_date.isoformat(),
                    "error": str(result)
                })
            else:
                successful_results.append({
                    "date": target_date.isoformat(),
                    "result": result
                })
        
        return {
            "batch_summary": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "days_processed": len(successful_results),
                "errors": len(errors),
                "processing_time_seconds": processing_time,
                "avg_time_per_day": processing_time / len(tasks) if tasks else 0
            },
            "successful_results": successful_results,
            "errors": errors
        }
    
    async def generate_daily_analytics_async(self, target_date: datetime) -> Dict[str, Any]:
        """Generate daily analytics asynchronously"""
        
        try:
            async with await self._get_async_session() as session:
                # Use raw SQL for better performance
                promotion_query = text("""
                    SELECT 
                        p.id,
                        p.name,
                        COUNT(pu.id) as usage_count,
                        COALESCE(SUM(pu.discount_amount), 0) as total_discount,
                        COALESCE(SUM(pu.final_order_amount), 0) as total_revenue,
                        COUNT(DISTINCT pu.customer_id) as unique_customers,
                        p.impressions,
                        p.clicks
                    FROM promotions p
                    LEFT JOIN promotion_usage pu ON p.id = pu.promotion_id 
                        AND DATE(pu.created_at) = :target_date
                    WHERE p.status = 'active'
                    GROUP BY p.id, p.name, p.impressions, p.clicks
                    HAVING COUNT(pu.id) > 0
                """)
                
                result = await session.execute(
                    promotion_query,
                    {"target_date": target_date.date()}
                )
                
                promotion_data = result.fetchall()
                
                # Process coupon analytics
                coupon_query = text("""
                    SELECT 
                        c.id,
                        c.code,
                        c.promotion_id,
                        COUNT(cu.id) as usage_count,
                        COALESCE(SUM(cu.discount_amount), 0) as total_discount,
                        COUNT(DISTINCT cu.customer_id) as unique_customers
                    FROM coupons c
                    LEFT JOIN coupon_usage cu ON c.id = cu.coupon_id 
                        AND DATE(cu.created_at) = :target_date
                    WHERE c.status = 'active'
                    GROUP BY c.id, c.code, c.promotion_id
                    HAVING COUNT(cu.id) > 0
                """)
                
                coupon_result = await session.execute(
                    coupon_query,
                    {"target_date": target_date.date()}
                )
                
                coupon_data = coupon_result.fetchall()
                
                # Process referral analytics
                referral_query = text("""
                    SELECT 
                        rp.id,
                        rp.name,
                        COUNT(cr.id) as new_referrals,
                        COUNT(CASE WHEN cr.status = 'completed' THEN 1 END) as completed_referrals,
                        COALESCE(SUM(
                            CASE WHEN cr.status = 'completed' 
                            THEN rp.referrer_reward_value + rp.referee_reward_value 
                            ELSE 0 END
                        ), 0) as total_rewards_issued
                    FROM referral_programs rp
                    LEFT JOIN customer_referrals cr ON rp.id = cr.referral_program_id 
                        AND DATE(cr.created_at) = :target_date
                    WHERE rp.status = 'active'
                    GROUP BY rp.id, rp.name
                    HAVING COUNT(cr.id) > 0
                """)
                
                referral_result = await session.execute(
                    referral_query,
                    {"target_date": target_date.date()}
                )
                
                referral_data = referral_result.fetchall()
                
                # Format results
                aggregates = {
                    "target_date": target_date.date().isoformat(),
                    "promotion_aggregates": [
                        {
                            "promotion_id": row.id,
                            "promotion_name": row.name,
                            "usage_count": row.usage_count,
                            "total_discount": float(row.total_discount),
                            "total_revenue": float(row.total_revenue),
                            "unique_customers": row.unique_customers,
                            "impressions": row.impressions or 0,
                            "clicks": row.clicks or 0,
                            "conversion_rate": (row.usage_count / max(row.impressions or 1, 1)) * 100
                        }
                        for row in promotion_data
                    ],
                    "coupon_aggregates": [
                        {
                            "coupon_id": row.id,
                            "coupon_code": row.code,
                            "promotion_id": row.promotion_id,
                            "usage_count": row.usage_count,
                            "total_discount": float(row.total_discount),
                            "unique_customers": row.unique_customers
                        }
                        for row in coupon_data
                    ],
                    "referral_aggregates": [
                        {
                            "program_id": row.id,
                            "program_name": row.name,
                            "new_referrals": row.new_referrals,
                            "completed_referrals": row.completed_referrals,
                            "total_rewards_issued": float(row.total_rewards_issued)
                        }
                        for row in referral_data
                    ],
                    "generated_at": datetime.utcnow().isoformat()
                }
                
                return aggregates
                
        except Exception as e:
            logger.error(f"Error generating async daily analytics for {target_date}: {e}")
            raise
    
    async def generate_real_time_metrics(self) -> Dict[str, Any]:
        """Generate real-time metrics using async queries"""
        
        try:
            async with await self._get_async_session() as session:
                # Get current hour metrics
                current_hour = datetime.utcnow().replace(minute=0, second=0, microsecond=0)
                
                metrics_query = text("""
                    SELECT 
                        COUNT(DISTINCT pu.id) as current_hour_usage,
                        COUNT(DISTINCT pu.customer_id) as current_hour_customers,
                        COALESCE(SUM(pu.discount_amount), 0) as current_hour_discount,
                        COALESCE(SUM(pu.final_order_amount), 0) as current_hour_revenue,
                        COUNT(DISTINCT pu.promotion_id) as active_promotions
                    FROM promotion_usage pu
                    WHERE pu.created_at >= :current_hour
                """)
                
                result = await session.execute(
                    metrics_query,
                    {"current_hour": current_hour}
                )
                
                metrics_row = result.fetchone()
                
                # Get trending promotions
                trending_query = text("""
                    SELECT 
                        p.id,
                        p.name,
                        COUNT(pu.id) as recent_usage,
                        COALESCE(SUM(pu.discount_amount), 0) as recent_discount
                    FROM promotions p
                    JOIN promotion_usage pu ON p.id = pu.promotion_id
                    WHERE pu.created_at >= :since_time
                    GROUP BY p.id, p.name
                    ORDER BY recent_usage DESC
                    LIMIT 10
                """)
                
                trending_result = await session.execute(
                    trending_query,
                    {"since_time": datetime.utcnow() - timedelta(hours=24)}
                )
                
                trending_data = trending_result.fetchall()
                
                return {
                    "timestamp": datetime.utcnow().isoformat(),
                    "current_hour_metrics": {
                        "usage_count": metrics_row.current_hour_usage,
                        "unique_customers": metrics_row.current_hour_customers,
                        "total_discount": float(metrics_row.current_hour_discount),
                        "total_revenue": float(metrics_row.current_hour_revenue),
                        "active_promotions": metrics_row.active_promotions
                    },
                    "trending_promotions": [
                        {
                            "promotion_id": row.id,
                            "promotion_name": row.name,
                            "recent_usage": row.recent_usage,
                            "recent_discount": float(row.recent_discount)
                        }
                        for row in trending_data
                    ]
                }
                
        except Exception as e:
            logger.error(f"Error generating real-time metrics: {e}")
            raise
    
    async def stream_analytics_updates(
        self,
        callback: Callable[[Dict[str, Any]], None],
        interval_seconds: int = 60
    ):
        """Stream real-time analytics updates"""
        
        while True:
            try:
                metrics = await self.generate_real_time_metrics()
                
                # Call the callback with new metrics
                if asyncio.iscoroutinefunction(callback):
                    await callback(metrics)
                else:
                    callback(metrics)
                
                # Cache the metrics
                cache_key = "real_time_metrics"
                self.cache.set(cache_key, metrics, ttl=interval_seconds * 2)
                
            except Exception as e:
                logger.error(f"Error in analytics stream: {e}")
            
            await asyncio.sleep(interval_seconds)
    
    async def batch_update_promotion_metrics(
        self,
        promotion_ids: List[int],
        batch_size: int = 100
    ) -> Dict[str, Any]:
        """Update promotion metrics in batches asynchronously"""
        
        # Split promotion IDs into batches
        batches = [
            promotion_ids[i:i + batch_size]
            for i in range(0, len(promotion_ids), batch_size)
        ]
        
        # Process batches concurrently
        tasks = [
            self._update_promotion_batch_metrics(batch)
            for batch in batches
        ]
        
        start_time = time.time()
        results = await asyncio.gather(*tasks, return_exceptions=True)
        processing_time = time.time() - start_time
        
        # Aggregate results
        total_updated = 0
        errors = []
        
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                errors.append({
                    "batch_index": i,
                    "error": str(result)
                })
            else:
                total_updated += result.get("updated_count", 0)
        
        return {
            "total_promotions": len(promotion_ids),
            "total_updated": total_updated,
            "batches_processed": len(batches),
            "processing_time_seconds": processing_time,
            "errors": errors
        }
    
    async def _update_promotion_batch_metrics(
        self,
        promotion_ids: List[int]
    ) -> Dict[str, Any]:
        """Update metrics for a batch of promotions"""
        
        try:
            async with await self._get_async_session() as session:
                # Update promotion metrics using raw SQL for performance
                update_query = text("""
                    UPDATE promotions SET 
                        current_uses = subquery.usage_count,
                        revenue_generated = subquery.total_revenue,
                        conversions = subquery.usage_count,
                        conversion_rate = CASE 
                            WHEN impressions > 0 THEN (subquery.usage_count::float / impressions) * 100
                            ELSE 0
                        END,
                        updated_at = NOW()
                    FROM (
                        SELECT 
                            p.id,
                            COALESCE(COUNT(pu.id), 0) as usage_count,
                            COALESCE(SUM(pu.final_order_amount), 0) as total_revenue
                        FROM promotions p
                        LEFT JOIN promotion_usage pu ON p.id = pu.promotion_id
                        WHERE p.id = ANY(:promotion_ids)
                        GROUP BY p.id
                    ) as subquery
                    WHERE promotions.id = subquery.id
                """)
                
                result = await session.execute(
                    update_query,
                    {"promotion_ids": promotion_ids}
                )
                
                updated_count = result.rowcount
                await session.commit()
                
                return {"updated_count": updated_count}
                
        except Exception as e:
            logger.error(f"Error updating promotion batch metrics: {e}")
            raise
    
    async def generate_analytics_summary_async(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Any]:
        """Generate comprehensive analytics summary asynchronously"""
        
        try:
            # Run multiple analytics queries concurrently
            tasks = [
                self._get_promotion_summary_async(start_date, end_date),
                self._get_coupon_summary_async(start_date, end_date),
                self._get_referral_summary_async(start_date, end_date),
                self._get_customer_summary_async(start_date, end_date)
            ]
            
            results = await asyncio.gather(*tasks)
            
            promotion_summary, coupon_summary, referral_summary, customer_summary = results
            
            return {
                "period": {
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                    "duration_days": (end_date - start_date).days
                },
                "promotion_summary": promotion_summary,
                "coupon_summary": coupon_summary,
                "referral_summary": referral_summary,
                "customer_summary": customer_summary,
                "generated_at": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error generating analytics summary: {e}")
            raise
    
    async def _get_promotion_summary_async(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Any]:
        """Get promotion summary statistics"""
        
        async with await self._get_async_session() as session:
            query = text("""
                SELECT 
                    COUNT(DISTINCT p.id) as total_promotions,
                    COUNT(DISTINCT CASE WHEN p.status = 'active' THEN p.id END) as active_promotions,
                    COALESCE(SUM(pu.discount_amount), 0) as total_discount,
                    COALESCE(SUM(pu.final_order_amount), 0) as total_revenue,
                    COUNT(pu.id) as total_usage,
                    COUNT(DISTINCT pu.customer_id) as unique_customers
                FROM promotions p
                LEFT JOIN promotion_usage pu ON p.id = pu.promotion_id
                    AND pu.created_at BETWEEN :start_date AND :end_date
            """)
            
            result = await session.execute(query, {
                "start_date": start_date,
                "end_date": end_date
            })
            
            row = result.fetchone()
            
            return {
                "total_promotions": row.total_promotions,
                "active_promotions": row.active_promotions,
                "total_discount": float(row.total_discount),
                "total_revenue": float(row.total_revenue),
                "total_usage": row.total_usage,
                "unique_customers": row.unique_customers,
                "avg_discount_per_order": float(row.total_discount) / max(row.total_usage, 1),
                "roi_percentage": ((float(row.total_revenue) - float(row.total_discount)) / max(float(row.total_discount), 1)) * 100
            }
    
    async def _get_coupon_summary_async(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Any]:
        """Get coupon summary statistics"""
        
        async with await self._get_async_session() as session:
            query = text("""
                SELECT 
                    COUNT(DISTINCT c.id) as total_coupons,
                    COUNT(DISTINCT CASE WHEN c.status = 'active' THEN c.id END) as active_coupons,
                    COUNT(cu.id) as total_usage,
                    COALESCE(SUM(cu.discount_amount), 0) as total_discount,
                    COUNT(DISTINCT cu.customer_id) as unique_customers
                FROM coupons c
                LEFT JOIN coupon_usage cu ON c.id = cu.coupon_id
                    AND cu.created_at BETWEEN :start_date AND :end_date
            """)
            
            result = await session.execute(query, {
                "start_date": start_date,
                "end_date": end_date
            })
            
            row = result.fetchone()
            
            return {
                "total_coupons": row.total_coupons,
                "active_coupons": row.active_coupons,
                "total_usage": row.total_usage,
                "total_discount": float(row.total_discount),
                "unique_customers": row.unique_customers,
                "usage_rate": (row.total_usage / max(row.active_coupons, 1)) * 100
            }
    
    async def _get_referral_summary_async(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Any]:
        """Get referral summary statistics"""
        
        async with await self._get_async_session() as session:
            query = text("""
                SELECT 
                    COUNT(DISTINCT rp.id) as total_programs,
                    COUNT(DISTINCT CASE WHEN rp.status = 'active' THEN rp.id END) as active_programs,
                    COUNT(cr.id) as total_referrals,
                    COUNT(CASE WHEN cr.status = 'completed' THEN 1 END) as completed_referrals,
                    COUNT(DISTINCT cr.referrer_customer_id) as unique_referrers,
                    COUNT(DISTINCT cr.referee_customer_id) as unique_referees
                FROM referral_programs rp
                LEFT JOIN customer_referrals cr ON rp.id = cr.referral_program_id
                    AND cr.created_at BETWEEN :start_date AND :end_date
            """)
            
            result = await session.execute(query, {
                "start_date": start_date,
                "end_date": end_date
            })
            
            row = result.fetchone()
            
            return {
                "total_programs": row.total_programs,
                "active_programs": row.active_programs,
                "total_referrals": row.total_referrals,
                "completed_referrals": row.completed_referrals,
                "unique_referrers": row.unique_referrers,
                "unique_referees": row.unique_referees,
                "completion_rate": (row.completed_referrals / max(row.total_referrals, 1)) * 100
            }
    
    async def _get_customer_summary_async(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Any]:
        """Get customer engagement summary"""
        
        async with await self._get_async_session() as session:
            query = text("""
                SELECT 
                    COUNT(DISTINCT customer_id) as total_customers_engaged,
                    COUNT(*) as total_interactions,
                    AVG(discount_amount) as avg_discount_per_customer,
                    AVG(final_order_amount) as avg_order_value
                FROM (
                    SELECT customer_id, discount_amount, final_order_amount 
                    FROM promotion_usage 
                    WHERE created_at BETWEEN :start_date AND :end_date
                    UNION ALL
                    SELECT customer_id, discount_amount, 0 as final_order_amount 
                    FROM coupon_usage 
                    WHERE created_at BETWEEN :start_date AND :end_date
                ) combined
            """)
            
            result = await session.execute(query, {
                "start_date": start_date,
                "end_date": end_date
            })
            
            row = result.fetchone()
            
            return {
                "total_customers_engaged": row.total_customers_engaged or 0,
                "total_interactions": row.total_interactions or 0,
                "avg_discount_per_customer": float(row.avg_discount_per_customer or 0),
                "avg_order_value": float(row.avg_order_value or 0),
                "interactions_per_customer": (row.total_interactions or 0) / max(row.total_customers_engaged or 1, 1)
            }
    
    async def cleanup_old_analytics_async(
        self,
        retention_days: int = 365
    ) -> Dict[str, Any]:
        """Clean up old analytics data asynchronously"""
        
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=retention_days)
            
            async with await self._get_async_session() as session:
                # Delete old analytics records
                delete_query = text("""
                    DELETE FROM promotion_analytics 
                    WHERE date < :cutoff_date
                """)
                
                result = await session.execute(
                    delete_query,
                    {"cutoff_date": cutoff_date.date()}
                )
                
                deleted_count = result.rowcount
                await session.commit()
                
                return {
                    "success": True,
                    "records_deleted": deleted_count,
                    "cutoff_date": cutoff_date.date().isoformat(),
                    "retention_days": retention_days,
                    "completed_at": datetime.utcnow().isoformat()
                }
                
        except Exception as e:
            logger.error(f"Error in async analytics cleanup: {e}")
            return {
                "success": False,
                "error": str(e),
                "completed_at": datetime.utcnow().isoformat()
            }
    
    async def close(self):
        """Clean up async resources"""
        if self._async_engine:
            await self._async_engine.dispose()
        
        if self._redis_pool:
            await self._redis_pool.disconnect()
        
        if self.thread_pool:
            self.thread_pool.shutdown(wait=True)


# Global async analytics service instance
async_analytics_service = AsyncAnalyticsService()