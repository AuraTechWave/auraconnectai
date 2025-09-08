"""
Example analytics service using enhanced caching features.

Demonstrates:
- Multi-level caching
- Compression for large datasets
- Versioned caching
- Pattern-based preloading
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta, date
from sqlalchemy.orm import Session

from core.enhanced_redis_cache import cached_with_compression
from core.memory_cache import with_memory_cache
from core.cache_versioning import versioned_cache, CacheVersion
from core.cache_preloader import pattern_analyzer

logger = logging.getLogger(__name__)


class EnhancedAnalyticsService:
    """Analytics service with advanced caching capabilities."""
    
    def __init__(self, db: Session):
        self.db = db
    
    @cached_with_compression(
        namespace="analytics",
        ttl=3600,  # 1 hour
        compress=True,  # Enable compression for large reports
        memory_cache_ttl=300  # 5 minutes in memory cache
    )
    @with_memory_cache(namespace="analytics", ttl=300)
    async def get_sales_report(
        self,
        start_date: date,
        end_date: date,
        include_details: bool = False
    ) -> Dict[str, Any]:
        """
        Get sales report with multi-level caching and compression.
        
        This method demonstrates:
        - L1 cache: Memory cache for 5 minutes
        - L2 cache: Redis with compression for 1 hour
        - Automatic compression for large datasets
        """
        logger.info(f"Generating sales report for {start_date} to {end_date}")
        
        # Simulate expensive database query
        report = {
            "period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat()
            },
            "summary": {
                "total_sales": 125000.50,
                "total_orders": 3421,
                "average_order_value": 36.54,
                "top_products": [
                    {"id": 1, "name": "Burger Deluxe", "sales": 15000},
                    {"id": 2, "name": "Pizza Margherita", "sales": 12500},
                    {"id": 3, "name": "Caesar Salad", "sales": 8000},
                ]
            }
        }
        
        if include_details:
            # Add large dataset that benefits from compression
            report["daily_breakdown"] = [
                {
                    "date": (start_date + timedelta(days=i)).isoformat(),
                    "sales": 4000 + (i * 100),
                    "orders": 100 + (i * 5),
                    "hourly_data": [
                        {"hour": h, "sales": 200 + (h * 10)}
                        for h in range(24)
                    ]
                }
                for i in range((end_date - start_date).days + 1)
            ]
        
        # Record access pattern for preloading
        pattern_analyzer.record_access(
            f"sales_report:{start_date}:{end_date}",
            "analytics",
            True,  # Cache hit (simulated)
            5.2,  # Latency in ms
            len(str(report))  # Approximate size
        )
        
        return report
    
    @versioned_cache(
        version=CacheVersion.V2,
        namespace="analytics",
        ttl=7200,  # 2 hours
        fallback_versions=[CacheVersion.V1]  # Support old cache format
    )
    async def get_customer_insights(
        self,
        customer_segment: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get customer insights with versioned caching.
        
        This method demonstrates:
        - Versioned cache keys for backward compatibility
        - Automatic migration from old cache formats
        """
        logger.info(f"Generating customer insights for segment: {customer_segment}")
        
        # V2 format includes new fields
        insights = {
            "generated_at": datetime.utcnow().isoformat(),
            "segment": customer_segment or "all",
            "metrics": {
                "total_customers": 15000,
                "active_customers": 8500,
                "churn_rate": 0.05,
                "lifetime_value_avg": 450.00,
                # V2 additions
                "engagement_score": 0.72,
                "satisfaction_index": 4.2
            },
            "trends": {
                "new_customers_monthly": 500,
                "growth_rate": 0.08,
                # V2 additions
                "retention_trend": "improving",
                "sentiment_analysis": {
                    "positive": 0.75,
                    "neutral": 0.20,
                    "negative": 0.05
                }
            }
        }
        
        return insights
    
    @cached_with_compression(
        namespace="analytics_realtime",
        ttl=60,  # 1 minute for real-time data
        compress=False  # No compression for small, frequent updates
    )
    async def get_realtime_metrics(self) -> Dict[str, Any]:
        """
        Get real-time metrics with short TTL and no compression.
        
        This method demonstrates:
        - Short TTL for frequently changing data
        - No compression for small payloads
        - High-frequency access pattern tracking
        """
        metrics = {
            "timestamp": datetime.utcnow().isoformat(),
            "active_orders": 42,
            "kitchen_load": 0.65,
            "average_wait_time": 12.5,
            "staff_available": 8,
            "tables_occupied": 15,
            "revenue_today": 8543.25
        }
        
        # Track for pattern analysis
        pattern_analyzer.record_access(
            "realtime_metrics",
            "analytics_realtime",
            True,
            1.2,  # Very low latency
            len(str(metrics))
        )
        
        return metrics
    
    async def get_large_dataset_example(
        self,
        year: int
    ) -> Dict[str, Any]:
        """
        Example of caching a very large dataset with compression.
        
        This demonstrates maximum compression benefits.
        """
        # Use the enhanced cache directly for fine control
        from core.enhanced_redis_cache import cache_large_object, get_large_object
        
        cache_key = f"yearly_analysis:{year}"
        
        # Try to get from cache
        cached_data = await get_large_object(cache_key, namespace="analytics_large")
        if cached_data:
            return cached_data
        
        # Generate large dataset
        logger.info(f"Generating large dataset for year {year}")
        
        large_data = {
            "year": year,
            "monthly_data": []
        }
        
        # Simulate large dataset (would be from database in reality)
        for month in range(1, 13):
            month_data = {
                "month": month,
                "daily_transactions": []
            }
            
            for day in range(1, 32):
                transactions = []
                for trans_id in range(100):  # 100 transactions per day
                    transactions.append({
                        "id": f"{year}-{month:02d}-{day:02d}-{trans_id:04d}",
                        "amount": 10.0 + (trans_id % 100),
                        "items": ["item1", "item2", "item3"],
                        "customer": f"customer_{trans_id % 1000}",
                        "timestamp": f"{year}-{month:02d}-{day:02d}T{trans_id % 24:02d}:00:00",
                        "metadata": {
                            "source": "POS",
                            "register": trans_id % 5,
                            "staff": f"staff_{trans_id % 20}"
                        }
                    })
                
                month_data["daily_transactions"].append({
                    "day": day,
                    "transactions": transactions
                })
            
            large_data["monthly_data"].append(month_data)
        
        # Cache with compression (will compress ~37,000+ transactions)
        await cache_large_object(
            cache_key,
            large_data,
            namespace="analytics_large",
            ttl=86400  # 24 hours
        )
        
        return large_data
    
    async def demonstrate_pattern_preloading(self):
        """
        Demonstrate how pattern-based preloading works.
        """
        # Simulate regular access pattern
        now = datetime.utcnow()
        today = now.date()
        
        # These accesses will be tracked and analyzed
        common_reports = [
            (today, today),  # Today's report
            (today - timedelta(days=7), today),  # Last 7 days
            (today - timedelta(days=30), today),  # Last 30 days
        ]
        
        for start_date, end_date in common_reports:
            # Access multiple times to establish pattern
            for _ in range(5):
                await self.get_sales_report(start_date, end_date)
        
        # The pattern analyzer will identify these as DAILY or PERIODIC patterns
        # and recommend them for preloading during off-peak hours


# Example usage in routes
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from core.database import get_db

router = APIRouter()

@router.get("/analytics/sales")
async def get_sales_analytics(
    start_date: date,
    end_date: date,
    include_details: bool = False,
    db: Session = Depends(get_db)
):
    service = EnhancedAnalyticsService(db)
    return await service.get_sales_report(start_date, end_date, include_details)

@router.get("/analytics/realtime")
async def get_realtime_analytics(
    db: Session = Depends(get_db)
):
    service = EnhancedAnalyticsService(db)
    return await service.get_realtime_metrics()

@router.get("/analytics/large-dataset/{year}")
async def get_yearly_analytics(
    year: int,
    db: Session = Depends(get_db)
):
    service = EnhancedAnalyticsService(db)
    
    # This will return compressed data from cache or generate and compress
    data = await service.get_large_dataset_example(year)
    
    # Return summary instead of full data for API response
    return {
        "year": year,
        "total_months": len(data["monthly_data"]),
        "total_transactions": sum(
            len(day["transactions"])
            for month in data["monthly_data"]
            for day in month["daily_transactions"]
        ),
        "cached": True,
        "message": "Full data available via dedicated endpoint"
    }
"""