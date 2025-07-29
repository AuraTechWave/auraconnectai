# backend/modules/promotions/services/analytics_service.py

from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_, desc, case
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, timedelta
import logging
from decimal import Decimal

from ..models.promotion_models import (
    Promotion, PromotionUsage, PromotionAnalytics, CouponUsage, 
    CustomerReferral, ReferralProgram, PromotionStatus, ReferralStatus
)
from backend.modules.orders.models.order_models import Order
from backend.modules.customers.models.customer_models import Customer

logger = logging.getLogger(__name__)


class PromotionAnalyticsService:
    """Service for generating comprehensive promotion analytics and reports"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def generate_promotion_performance_report(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        promotion_ids: Optional[List[int]] = None,
        include_inactive: bool = False
    ) -> Dict[str, Any]:
        """
        Generate comprehensive promotion performance report
        
        Args:
            start_date: Report start date
            end_date: Report end date
            promotion_ids: Specific promotions to include
            include_inactive: Include inactive promotions
            
        Returns:
            Dictionary with promotion performance metrics
        """
        try:
            # Set default date range if not provided
            if not end_date:
                end_date = datetime.utcnow()
            if not start_date:
                start_date = end_date - timedelta(days=30)
            
            # Build base query
            query = self.db.query(Promotion)
            
            if not include_inactive:
                query = query.filter(Promotion.status.in_([
                    PromotionStatus.ACTIVE, PromotionStatus.PAUSED, PromotionStatus.ENDED
                ]))
            
            if promotion_ids:
                query = query.filter(Promotion.id.in_(promotion_ids))
            
            promotions = query.all()
            
            # Calculate metrics for each promotion
            promotion_metrics = []
            total_revenue_generated = 0
            total_discounts_given = 0
            total_orders_affected = 0
            
            for promotion in promotions:
                metrics = self._calculate_promotion_metrics(
                    promotion, start_date, end_date
                )
                promotion_metrics.append(metrics)
                
                total_revenue_generated += metrics["revenue_generated"]
                total_discounts_given += metrics["total_discount_given"]
                total_orders_affected += metrics["orders_count"]
            
            # Calculate overall performance
            roi_percentage = 0
            if total_discounts_given > 0:
                roi_percentage = ((total_revenue_generated - total_discounts_given) / total_discounts_given) * 100
            
            # Top performing promotions
            top_promotions = sorted(
                promotion_metrics,
                key=lambda x: x["roi_percentage"],
                reverse=True
            )[:5]
            
            # Promotion type analysis
            type_analysis = self._analyze_promotion_types(promotion_metrics)
            
            # Customer engagement analysis
            engagement_metrics = self._calculate_customer_engagement(start_date, end_date)
            
            return {
                "report_period": {
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                    "days": (end_date - start_date).days
                },
                "summary": {
                    "total_promotions": len(promotions),
                    "active_promotions": len([p for p in promotions if p.status == PromotionStatus.ACTIVE]),
                    "total_revenue_generated": round(total_revenue_generated, 2),
                    "total_discounts_given": round(total_discounts_given, 2),
                    "total_orders_affected": total_orders_affected,
                    "overall_roi_percentage": round(roi_percentage, 2),
                    "average_discount_per_order": round(
                        total_discounts_given / total_orders_affected if total_orders_affected > 0 else 0, 2
                    )
                },
                "promotion_details": promotion_metrics,
                "top_performing_promotions": top_promotions,
                "promotion_type_analysis": type_analysis,
                "customer_engagement": engagement_metrics
            }
            
        except Exception as e:
            logger.error(f"Error generating promotion performance report: {str(e)}")
            raise
    
    def _calculate_promotion_metrics(
        self,
        promotion: Promotion,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Any]:
        """Calculate detailed metrics for a single promotion"""
        
        # Get usage data within date range
        usage_query = self.db.query(PromotionUsage).filter(
            PromotionUsage.promotion_id == promotion.id,
            PromotionUsage.created_at >= start_date,
            PromotionUsage.created_at <= end_date
        )
        
        usages = usage_query.all()
        
        # Basic metrics
        total_usage = len(usages)
        total_discount = sum(usage.discount_amount for usage in usages)
        total_revenue = sum(usage.final_order_amount for usage in usages)
        unique_customers = len(set(usage.customer_id for usage in usages if usage.customer_id))
        
        # Calculate ROI
        roi_percentage = 0
        if total_discount > 0:
            roi_percentage = ((total_revenue - total_discount) / total_discount) * 100
        
        # Usage rate
        usage_rate = 0
        if promotion.max_uses_total:
            usage_rate = (total_usage / promotion.max_uses_total) * 100
        
        # Conversion metrics (if available)
        conversion_rate = 0
        if promotion.impressions > 0:
            conversion_rate = (total_usage / promotion.impressions) * 100
        
        # Average order value
        avg_order_value = total_revenue / total_usage if total_usage > 0 else 0
        
        return {
            "promotion_id": promotion.id,
            "promotion_name": promotion.name,
            "promotion_type": promotion.promotion_type,
            "status": promotion.status,
            "usage_metrics": {
                "total_usage": total_usage,
                "unique_customers": unique_customers,
                "usage_rate_percentage": round(usage_rate, 2),
                "max_uses_total": promotion.max_uses_total
            },
            "financial_metrics": {
                "total_discount_given": round(total_discount, 2),
                "revenue_generated": round(total_revenue, 2),
                "average_order_value": round(avg_order_value, 2),
                "roi_percentage": round(roi_percentage, 2)
            },
            "engagement_metrics": {
                "impressions": promotion.impressions,
                "clicks": promotion.clicks,
                "conversions": total_usage,
                "conversion_rate_percentage": round(conversion_rate, 2),
                "click_through_rate": round(
                    (promotion.clicks / promotion.impressions * 100) if promotion.impressions > 0 else 0, 2
                )
            },
            "time_metrics": {
                "days_active": (datetime.utcnow() - promotion.start_date).days,
                "days_remaining": max(0, (promotion.end_date - datetime.utcnow()).days) if promotion.end_date else None
            }
        }
    
    def _analyze_promotion_types(self, promotion_metrics: List[Dict]) -> Dict[str, Any]:
        """Analyze performance by promotion type"""
        
        type_stats = {}
        
        for metrics in promotion_metrics:
            promo_type = metrics["promotion_type"]
            
            if promo_type not in type_stats:
                type_stats[promo_type] = {
                    "count": 0,
                    "total_usage": 0,
                    "total_discount": 0,
                    "total_revenue": 0,
                    "avg_roi": 0
                }
            
            stats = type_stats[promo_type]
            stats["count"] += 1
            stats["total_usage"] += metrics["usage_metrics"]["total_usage"]
            stats["total_discount"] += metrics["financial_metrics"]["total_discount_given"]
            stats["total_revenue"] += metrics["financial_metrics"]["revenue_generated"]
        
        # Calculate averages
        for promo_type, stats in type_stats.items():
            if stats["total_discount"] > 0:
                stats["avg_roi"] = ((stats["total_revenue"] - stats["total_discount"]) / stats["total_discount"]) * 100
            stats["avg_usage_per_promotion"] = stats["total_usage"] / stats["count"]
            stats["avg_discount_per_promotion"] = stats["total_discount"] / stats["count"]
        
        return type_stats
    
    def _calculate_customer_engagement(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Any]:
        """Calculate customer engagement metrics"""
        
        # Get customers who used promotions in the period
        customer_usage = self.db.query(
            PromotionUsage.customer_id,
            func.count(PromotionUsage.id).label('usage_count'),
            func.sum(PromotionUsage.discount_amount).label('total_savings'),
            func.count(func.distinct(PromotionUsage.promotion_id)).label('unique_promotions')
        ).filter(
            PromotionUsage.created_at >= start_date,
            PromotionUsage.created_at <= end_date,
            PromotionUsage.customer_id.isnot(None)
        ).group_by(PromotionUsage.customer_id).all()
        
        if not customer_usage:
            return {
                "total_customers_engaged": 0,
                "average_promotions_per_customer": 0,
                "average_savings_per_customer": 0,
                "customer_segments": {}
            }
        
        total_customers = len(customer_usage)
        total_usage = sum(cu.usage_count for cu in customer_usage)
        total_savings = sum(float(cu.total_savings) for cu in customer_usage)
        
        # Segment customers by usage
        segments = {
            "light_users": len([cu for cu in customer_usage if cu.usage_count <= 2]),
            "medium_users": len([cu for cu in customer_usage if 3 <= cu.usage_count <= 5]),
            "heavy_users": len([cu for cu in customer_usage if cu.usage_count > 5])
        }
        
        return {
            "total_customers_engaged": total_customers,
            "average_promotions_per_customer": round(total_usage / total_customers, 2),
            "average_savings_per_customer": round(total_savings / total_customers, 2),
            "customer_segments": segments,
            "engagement_distribution": {
                "light_users_percentage": round((segments["light_users"] / total_customers) * 100, 1),
                "medium_users_percentage": round((segments["medium_users"] / total_customers) * 100, 1),
                "heavy_users_percentage": round((segments["heavy_users"] / total_customers) * 100, 1)
            }
        }
    
    def generate_coupon_analytics_report(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        promotion_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Generate coupon usage analytics report"""
        
        try:
            if not end_date:
                end_date = datetime.utcnow()
            if not start_date:
                start_date = end_date - timedelta(days=30)
            
            # Base query for coupon usage
            from ..models.promotion_models import Coupon
            
            query = self.db.query(CouponUsage).join(Coupon).filter(
                CouponUsage.created_at >= start_date,
                CouponUsage.created_at <= end_date
            )
            
            if promotion_id:
                query = query.filter(Coupon.promotion_id == promotion_id)
            
            coupon_usages = query.all()
            
            # Calculate metrics
            total_coupons_used = len(coupon_usages)
            total_discount = sum(usage.discount_amount for usage in coupon_usages)
            unique_customers = len(set(usage.customer_id for usage in coupon_usages if usage.customer_id))
            unique_coupons = len(set(usage.coupon_id for usage in coupon_usages))
            
            # Coupon performance by type
            from ..models.promotion_models import CouponType
            type_performance = self.db.query(
                Coupon.coupon_type,
                func.count(CouponUsage.id).label('usage_count'),
                func.sum(CouponUsage.discount_amount).label('total_discount')
            ).join(CouponUsage).filter(
                CouponUsage.created_at >= start_date,
                CouponUsage.created_at <= end_date
            ).group_by(Coupon.coupon_type).all()
            
            # Top performing coupons
            top_coupons = self.db.query(
                Coupon.code,
                Coupon.coupon_type,
                func.count(CouponUsage.id).label('usage_count'),
                func.sum(CouponUsage.discount_amount).label('total_discount')
            ).join(CouponUsage).filter(
                CouponUsage.created_at >= start_date,
                CouponUsage.created_at <= end_date
            ).group_by(Coupon.id, Coupon.code, Coupon.coupon_type).order_by(
                desc('usage_count')
            ).limit(10).all()
            
            return {
                "report_period": {
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat()
                },
                "summary": {
                    "total_coupons_used": total_coupons_used,
                    "unique_coupons_used": unique_coupons,
                    "total_discount_given": round(total_discount, 2),
                    "unique_customers": unique_customers,
                    "average_discount_per_coupon": round(
                        total_discount / total_coupons_used if total_coupons_used > 0 else 0, 2
                    )
                },
                "type_performance": [
                    {
                        "coupon_type": tp.coupon_type,
                        "usage_count": tp.usage_count,
                        "total_discount": float(tp.total_discount),
                        "average_discount": float(tp.total_discount) / tp.usage_count
                    }
                    for tp in type_performance
                ],
                "top_performing_coupons": [
                    {
                        "coupon_code": tc.code,
                        "coupon_type": tc.coupon_type,
                        "usage_count": tc.usage_count,
                        "total_discount": float(tc.total_discount)
                    }
                    for tc in top_coupons
                ]
            }
            
        except Exception as e:
            logger.error(f"Error generating coupon analytics report: {str(e)}")
            raise
    
    def generate_referral_analytics_report(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        program_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Generate referral program analytics report"""
        
        try:
            if not end_date:
                end_date = datetime.utcnow()
            if not start_date:
                start_date = end_date - timedelta(days=30)
            
            # Base query
            query = self.db.query(CustomerReferral).filter(
                CustomerReferral.created_at >= start_date,
                CustomerReferral.created_at <= end_date
            )
            
            if program_id:
                query = query.filter(CustomerReferral.program_id == program_id)
            
            referrals = query.all()
            
            # Calculate metrics by status
            status_counts = {}
            for status in ReferralStatus:
                status_counts[status.value] = len([r for r in referrals if r.status == status])
            
            # Calculate completion rate
            total_referrals = len(referrals)
            completed_referrals = status_counts.get('completed', 0) + status_counts.get('rewarded', 0)
            completion_rate = (completed_referrals / total_referrals * 100) if total_referrals > 0 else 0
            
            # Calculate rewards issued
            rewarded_referrals = [r for r in referrals if r.status == ReferralStatus.REWARDED]
            total_rewards = sum(
                (r.referrer_reward_amount or 0) + (r.referee_reward_amount or 0)
                for r in rewarded_referrals
            )
            
            # Top referrers
            top_referrers = self.db.query(
                CustomerReferral.referrer_id,
                func.count(CustomerReferral.id).label('referral_count'),
                func.count(case([(CustomerReferral.status.in_(['completed', 'rewarded']), 1)])).label('successful_referrals')
            ).filter(
                CustomerReferral.created_at >= start_date,
                CustomerReferral.created_at <= end_date
            ).group_by(CustomerReferral.referrer_id).order_by(
                desc('successful_referrals')
            ).limit(10).all()
            
            # Program performance (if multiple programs)
            program_performance = self.db.query(
                ReferralProgram.id,
                ReferralProgram.name,
                func.count(CustomerReferral.id).label('total_referrals'),
                func.count(case([(CustomerReferral.status.in_(['completed', 'rewarded']), 1)])).label('successful_referrals')
            ).join(CustomerReferral).filter(
                CustomerReferral.created_at >= start_date,
                CustomerReferral.created_at <= end_date
            ).group_by(ReferralProgram.id, ReferralProgram.name).all()
            
            return {
                "report_period": {
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat()
                },
                "summary": {
                    "total_referrals": total_referrals,
                    "completed_referrals": completed_referrals,
                    "completion_rate_percentage": round(completion_rate, 2),
                    "total_rewards_issued": round(total_rewards, 2),
                    "unique_referrers": len(set(r.referrer_id for r in referrals)),
                    "unique_referees": len(set(r.referee_id for r in referrals if r.referee_id))
                },
                "status_breakdown": status_counts,
                "top_referrers": [
                    {
                        "referrer_id": tr.referrer_id,
                        "total_referrals": tr.referral_count,
                        "successful_referrals": tr.successful_referrals,
                        "success_rate": round((tr.successful_referrals / tr.referral_count * 100), 2)
                    }
                    for tr in top_referrers
                ],
                "program_performance": [
                    {
                        "program_id": pp.id,
                        "program_name": pp.name,
                        "total_referrals": pp.total_referrals,
                        "successful_referrals": pp.successful_referrals,
                        "success_rate": round((pp.successful_referrals / pp.total_referrals * 100), 2) if pp.total_referrals > 0 else 0
                    }
                    for pp in program_performance
                ]
            }
            
        except Exception as e:
            logger.error(f"Error generating referral analytics report: {str(e)}")
            raise
    
    def generate_daily_analytics_aggregates(self, target_date: datetime) -> Dict[str, Any]:
        """Generate daily analytics aggregates for a specific date"""
        
        try:
            start_of_day = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
            end_of_day = start_of_day + timedelta(days=1)
            
            results = {}
            
            # Promotion usage aggregates
            promotion_usage = self.db.query(
                PromotionUsage.promotion_id,
                func.count(PromotionUsage.id).label('usage_count'),
                func.sum(PromotionUsage.discount_amount).label('total_discount'),
                func.sum(PromotionUsage.final_order_amount).label('total_revenue'),
                func.count(func.distinct(PromotionUsage.customer_id)).label('unique_customers')
            ).filter(
                PromotionUsage.created_at >= start_of_day,
                PromotionUsage.created_at < end_of_day
            ).group_by(PromotionUsage.promotion_id).all()
            
            results["promotion_aggregates"] = [
                {
                    "promotion_id": pu.promotion_id,
                    "date": target_date.date().isoformat(),
                    "usage_count": pu.usage_count,
                    "total_discount": float(pu.total_discount),
                    "total_revenue": float(pu.total_revenue),
                    "unique_customers": pu.unique_customers
                }
                for pu in promotion_usage
            ]
            
            # Coupon usage aggregates
            coupon_usage = self.db.query(
                func.count(CouponUsage.id).label('total_usage'),
                func.sum(CouponUsage.discount_amount).label('total_discount'),
                func.count(func.distinct(CouponUsage.customer_id)).label('unique_customers')
            ).filter(
                CouponUsage.created_at >= start_of_day,
                CouponUsage.created_at < end_of_day
            ).first()
            
            results["coupon_aggregates"] = {
                "date": target_date.date().isoformat(),
                "total_usage": coupon_usage.total_usage or 0,
                "total_discount": float(coupon_usage.total_discount or 0),
                "unique_customers": coupon_usage.unique_customers or 0
            }
            
            # Referral aggregates
            referral_stats = self.db.query(
                func.count(CustomerReferral.id).label('total_referrals'),
                func.count(case([(CustomerReferral.status == ReferralStatus.COMPLETED, 1)])).label('completed_referrals'),
                func.count(case([(CustomerReferral.status == ReferralStatus.REWARDED, 1)])).label('rewarded_referrals')
            ).filter(
                CustomerReferral.created_at >= start_of_day,
                CustomerReferral.created_at < end_of_day
            ).first()
            
            results["referral_aggregates"] = {
                "date": target_date.date().isoformat(),
                "total_referrals": referral_stats.total_referrals or 0,
                "completed_referrals": referral_stats.completed_referrals or 0,
                "rewarded_referrals": referral_stats.rewarded_referrals or 0
            }
            
            return results
            
        except Exception as e:
            logger.error(f"Error generating daily analytics for {target_date}: {str(e)}")
            raise