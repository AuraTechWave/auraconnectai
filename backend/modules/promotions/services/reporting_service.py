# backend/modules/promotions/services/reporting_service.py

from sqlalchemy.orm import Session
from typing import Optional, List, Dict, Any, Union
from datetime import datetime, timedelta
import logging
import csv
import io
import json

from .analytics_service import PromotionAnalyticsService

logger = logging.getLogger(__name__)


class PromotionReportingService:
    """Service for generating formatted promotion reports"""
    
    def __init__(self, db: Session):
        self.db = db
        self.analytics_service = PromotionAnalyticsService(db)
    
    def generate_executive_summary(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Generate executive summary report for promotion performance
        
        Args:
            start_date: Report start date
            end_date: Report end date
            
        Returns:
            Executive summary with key metrics and insights
        """
        try:
            if not end_date:
                end_date = datetime.utcnow()
            if not start_date:
                start_date = end_date - timedelta(days=30)
            
            # Get comprehensive analytics
            performance_report = self.analytics_service.generate_promotion_performance_report(
                start_date=start_date,
                end_date=end_date
            )
            
            coupon_report = self.analytics_service.generate_coupon_analytics_report(
                start_date=start_date,
                end_date=end_date
            )
            
            referral_report = self.analytics_service.generate_referral_analytics_report(
                start_date=start_date,
                end_date=end_date
            )
            
            # Calculate period-over-period comparison
            prev_start = start_date - (end_date - start_date)
            prev_end = start_date
            
            prev_performance = self.analytics_service.generate_promotion_performance_report(
                start_date=prev_start,
                end_date=prev_end
            )
            
            # Key performance indicators
            current_revenue = performance_report["summary"]["total_revenue_generated"]
            prev_revenue = prev_performance["summary"]["total_revenue_generated"]
            revenue_growth = ((current_revenue - prev_revenue) / prev_revenue * 100) if prev_revenue > 0 else 0
            
            current_orders = performance_report["summary"]["total_orders_affected"]
            prev_orders = prev_performance["summary"]["total_orders_affected"]
            order_growth = ((current_orders - prev_orders) / prev_orders * 100) if prev_orders > 0 else 0
            
            # Generate insights
            insights = self._generate_insights(performance_report, coupon_report, referral_report)
            
            # Recommendations
            recommendations = self._generate_recommendations(performance_report, insights)
            
            return {
                "report_metadata": {
                    "generated_at": datetime.utcnow().isoformat(),
                    "report_period": {
                        "start_date": start_date.isoformat(),
                        "end_date": end_date.isoformat(),
                        "days": (end_date - start_date).days
                    },
                    "comparison_period": {
                        "start_date": prev_start.isoformat(),
                        "end_date": prev_end.isoformat()
                    }
                },
                "key_metrics": {
                    "revenue_generated": {
                        "current": round(current_revenue, 2),
                        "previous": round(prev_revenue, 2),
                        "growth_percentage": round(revenue_growth, 2)
                    },
                    "orders_with_promotions": {
                        "current": current_orders,
                        "previous": prev_orders,
                        "growth_percentage": round(order_growth, 2)
                    },
                    "total_discounts_given": round(performance_report["summary"]["total_discounts_given"], 2),
                    "overall_roi": round(performance_report["summary"]["overall_roi_percentage"], 2),
                    "customer_engagement": performance_report["customer_engagement"]["total_customers_engaged"]
                },
                "performance_highlights": {
                    "top_promotion": performance_report["top_performing_promotions"][0] if performance_report["top_performing_promotions"] else None,
                    "most_popular_promotion_type": self._get_most_popular_type(performance_report["promotion_type_analysis"]),
                    "coupon_usage_rate": self._calculate_coupon_usage_rate(coupon_report),
                    "referral_success_rate": referral_report["summary"]["completion_rate_percentage"]
                },
                "channel_performance": {
                    "promotions": {
                        "active_count": performance_report["summary"]["active_promotions"],
                        "total_usage": sum(p["usage_metrics"]["total_usage"] for p in performance_report["promotion_details"]),
                        "avg_roi": performance_report["summary"]["overall_roi_percentage"]
                    },
                    "coupons": {
                        "total_used": coupon_report["summary"]["total_coupons_used"],
                        "unique_customers": coupon_report["summary"]["unique_customers"],
                        "total_discount": coupon_report["summary"]["total_discount_given"]
                    },
                    "referrals": {
                        "total_referrals": referral_report["summary"]["total_referrals"],
                        "completion_rate": referral_report["summary"]["completion_rate_percentage"],
                        "total_rewards": referral_report["summary"]["total_rewards_issued"]
                    }
                },
                "insights": insights,
                "recommendations": recommendations
            }
            
        except Exception as e:
            logger.error(f"Error generating executive summary: {str(e)}")
            raise
    
    def _generate_insights(
        self,
        performance_report: Dict,
        coupon_report: Dict,
        referral_report: Dict
    ) -> List[Dict[str, Any]]:
        """Generate actionable insights from the data"""
        
        insights = []
        
        # Performance insights
        if performance_report["summary"]["overall_roi_percentage"] > 200:
            insights.append({
                "type": "success",
                "category": "performance",
                "title": "Excellent ROI Performance",
                "description": f"Your promotions are generating an outstanding {performance_report['summary']['overall_roi_percentage']:.1f}% ROI, significantly above the 150% industry benchmark.",
                "impact": "high"
            })
        elif performance_report["summary"]["overall_roi_percentage"] < 100:
            insights.append({
                "type": "warning",
                "category": "performance",
                "title": "ROI Below Break-Even",
                "description": f"Current ROI of {performance_report['summary']['overall_roi_percentage']:.1f}% is below break-even. Consider optimizing discount amounts or targeting.",
                "impact": "high"
            })
        
        # Customer engagement insights
        engagement = performance_report["customer_engagement"]
        if engagement["engagement_distribution"]["heavy_users_percentage"] > 30:
            insights.append({
                "type": "opportunity",
                "category": "engagement",
                "title": "Strong Customer Loyalty",
                "description": f"{engagement['engagement_distribution']['heavy_users_percentage']:.1f}% of customers are heavy promotion users, indicating strong engagement.",
                "impact": "medium"
            })
        
        # Coupon insights
        if coupon_report["summary"]["total_coupons_used"] > 0:
            avg_discount = coupon_report["summary"]["average_discount_per_coupon"]
            if avg_discount > 20:
                insights.append({
                    "type": "warning",
                    "category": "coupons",
                    "title": "High Coupon Discounts",
                    "description": f"Average coupon discount of ${avg_discount:.2f} may be impacting profitability.",
                    "impact": "medium"
                })
        
        # Referral insights
        if referral_report["summary"]["completion_rate_percentage"] < 30:
            insights.append({
                "type": "opportunity",
                "category": "referrals",
                "title": "Referral Completion Rate Low",
                "description": f"Referral completion rate of {referral_report['summary']['completion_rate_percentage']:.1f}% suggests room for improvement in the referral process.",
                "impact": "medium"
            })
        
        return insights
    
    def _generate_recommendations(
        self,
        performance_report: Dict,
        insights: List[Dict]
    ) -> List[Dict[str, Any]]:
        """Generate actionable recommendations"""
        
        recommendations = []
        
        # Performance-based recommendations
        if performance_report["summary"]["overall_roi_percentage"] < 150:
            recommendations.append({
                "priority": "high",
                "category": "optimization",
                "title": "Optimize Discount Amounts",
                "description": "Consider reducing discount percentages and focus on higher-value promotions to improve ROI.",
                "action_items": [
                    "Analyze top-performing promotions and replicate their structure",
                    "A/B test lower discount amounts",
                    "Implement minimum order requirements"
                ]
            })
        
        # Top promotion type recommendation
        type_analysis = performance_report["promotion_type_analysis"]
        if type_analysis:
            best_type = max(type_analysis.items(), key=lambda x: x[1]["avg_roi"])
            recommendations.append({
                "priority": "medium",
                "category": "strategy",
                "title": f"Focus on {best_type[0].replace('_', ' ').title()} Promotions",
                "description": f"{best_type[0].replace('_', ' ').title()} promotions show the highest ROI at {best_type[1]['avg_roi']:.1f}%.",
                "action_items": [
                    f"Increase allocation to {best_type[0]} promotions",
                    "Reduce spending on lower-performing promotion types",
                    "Train team on best practices for this promotion type"
                ]
            })
        
        # Engagement recommendations
        engagement = performance_report["customer_engagement"]
        if engagement["engagement_distribution"]["light_users_percentage"] > 50:
            recommendations.append({
                "priority": "medium",
                "category": "engagement",
                "title": "Improve Customer Engagement",
                "description": "Over 50% of customers are light users. Focus on increasing engagement frequency.",
                "action_items": [
                    "Create targeted campaigns for light users",
                    "Implement progressive discount tiers",
                    "Send personalized promotion recommendations"
                ]
            })
        
        return recommendations
    
    def _get_most_popular_type(self, type_analysis: Dict) -> Optional[str]:
        """Get the most popular promotion type by usage"""
        if not type_analysis:
            return None
        
        return max(type_analysis.items(), key=lambda x: x[1]["total_usage"])[0]
    
    def _calculate_coupon_usage_rate(self, coupon_report: Dict) -> float:
        """Calculate overall coupon usage rate"""
        # This would need additional data about total coupons generated
        # For now, return a placeholder calculation
        return round(coupon_report["summary"]["total_coupons_used"] / 
                    max(coupon_report["summary"]["unique_customers"], 1), 2)
    
    def export_report_csv(
        self,
        report_data: Dict[str, Any],
        report_type: str = "performance"
    ) -> str:
        """
        Export report data to CSV format
        
        Args:
            report_data: Report data to export
            report_type: Type of report (performance, coupons, referrals)
            
        Returns:
            CSV content as string
        """
        try:
            output = io.StringIO()
            
            if report_type == "performance":
                writer = csv.writer(output)
                
                # Write header
                writer.writerow([
                    "Promotion ID", "Promotion Name", "Type", "Status",
                    "Total Usage", "Unique Customers", "Total Discount",
                    "Revenue Generated", "ROI %", "Conversion Rate %"
                ])
                
                # Write data
                for promo in report_data.get("promotion_details", []):
                    writer.writerow([
                        promo["promotion_id"],
                        promo["promotion_name"],
                        promo["promotion_type"],
                        promo["status"],
                        promo["usage_metrics"]["total_usage"],
                        promo["usage_metrics"]["unique_customers"],
                        promo["financial_metrics"]["total_discount_given"],
                        promo["financial_metrics"]["revenue_generated"],
                        promo["financial_metrics"]["roi_percentage"],
                        promo["engagement_metrics"]["conversion_rate_percentage"]
                    ])
            
            elif report_type == "coupons":
                writer = csv.writer(output)
                
                writer.writerow(["Coupon Code", "Type", "Usage Count", "Total Discount"])
                
                for coupon in report_data.get("top_performing_coupons", []):
                    writer.writerow([
                        coupon["coupon_code"],
                        coupon["coupon_type"],
                        coupon["usage_count"],
                        coupon["total_discount"]
                    ])
            
            elif report_type == "referrals":
                writer = csv.writer(output)
                
                writer.writerow(["Referrer ID", "Total Referrals", "Successful Referrals", "Success Rate %"])
                
                for referrer in report_data.get("top_referrers", []):
                    writer.writerow([
                        referrer["referrer_id"],
                        referrer["total_referrals"],
                        referrer["successful_referrals"],
                        referrer["success_rate"]
                    ])
            
            return output.getvalue()
            
        except Exception as e:
            logger.error(f"Error exporting report to CSV: {str(e)}")
            raise
    
    def export_report_json(self, report_data: Dict[str, Any]) -> str:
        """Export report data to JSON format"""
        try:
            return json.dumps(report_data, indent=2, default=str)
        except Exception as e:
            logger.error(f"Error exporting report to JSON: {str(e)}")
            raise
    
    def generate_scheduled_report(
        self,
        report_type: str,
        frequency: str = "weekly",
        recipients: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Generate a scheduled report
        
        Args:
            report_type: Type of report to generate
            frequency: Report frequency (daily, weekly, monthly)
            recipients: List of email recipients
            
        Returns:
            Generated report data
        """
        try:
            # Calculate date range based on frequency
            end_date = datetime.utcnow()
            
            if frequency == "daily":
                start_date = end_date - timedelta(days=1)
            elif frequency == "weekly":
                start_date = end_date - timedelta(days=7)
            elif frequency == "monthly":
                start_date = end_date - timedelta(days=30)
            else:
                start_date = end_date - timedelta(days=7)  # Default to weekly
            
            # Generate appropriate report
            if report_type == "executive":
                report_data = self.generate_executive_summary(start_date, end_date)
            elif report_type == "performance":
                report_data = self.analytics_service.generate_promotion_performance_report(
                    start_date, end_date
                )
            elif report_type == "coupons":
                report_data = self.analytics_service.generate_coupon_analytics_report(
                    start_date, end_date
                )
            elif report_type == "referrals":
                report_data = self.analytics_service.generate_referral_analytics_report(
                    start_date, end_date
                )
            else:
                raise ValueError(f"Unknown report type: {report_type}")
            
            # Add scheduling metadata
            report_data["scheduling_info"] = {
                "report_type": report_type,
                "frequency": frequency,
                "generated_at": datetime.utcnow().isoformat(),
                "recipients": recipients or [],
                "next_run": self._calculate_next_run(frequency)
            }
            
            logger.info(f"Generated scheduled {report_type} report for {frequency} frequency")
            
            return report_data
            
        except Exception as e:
            logger.error(f"Error generating scheduled report: {str(e)}")
            raise
    
    def _calculate_next_run(self, frequency: str) -> str:
        """Calculate next scheduled run time"""
        now = datetime.utcnow()
        
        if frequency == "daily":
            next_run = now + timedelta(days=1)
        elif frequency == "weekly":
            next_run = now + timedelta(days=7)
        elif frequency == "monthly":
            next_run = now + timedelta(days=30)
        else:
            next_run = now + timedelta(days=7)
        
        return next_run.isoformat()
    
    def generate_comparison_report(
        self,
        period1_start: datetime,
        period1_end: datetime,
        period2_start: datetime,
        period2_end: datetime
    ) -> Dict[str, Any]:
        """Generate a comparison report between two periods"""
        
        try:
            # Generate reports for both periods
            period1_report = self.analytics_service.generate_promotion_performance_report(
                period1_start, period1_end
            )
            
            period2_report = self.analytics_service.generate_promotion_performance_report(
                period2_start, period2_end
            )
            
            # Calculate comparisons
            comparisons = {}
            
            for metric in ["total_revenue_generated", "total_discounts_given", "total_orders_affected", "overall_roi_percentage"]:
                period1_value = period1_report["summary"][metric]
                period2_value = period2_report["summary"][metric]
                
                change = period1_value - period2_value
                percentage_change = (change / period2_value * 100) if period2_value != 0 else 0
                
                comparisons[metric] = {
                    "period1_value": period1_value,
                    "period2_value": period2_value,
                    "absolute_change": change,
                    "percentage_change": round(percentage_change, 2)
                }
            
            return {
                "comparison_metadata": {
                    "period1": {
                        "start_date": period1_start.isoformat(),
                        "end_date": period1_end.isoformat(),
                        "label": "Current Period"
                    },
                    "period2": {
                        "start_date": period2_start.isoformat(),
                        "end_date": period2_end.isoformat(),
                        "label": "Previous Period"
                    }
                },
                "metric_comparisons": comparisons,
                "period1_details": period1_report,
                "period2_details": period2_report,
                "insights": self._generate_comparison_insights(comparisons)
            }
            
        except Exception as e:
            logger.error(f"Error generating comparison report: {str(e)}")
            raise
    
    def _generate_comparison_insights(self, comparisons: Dict) -> List[Dict[str, Any]]:
        """Generate insights from period comparison"""
        
        insights = []
        
        # Revenue insights
        revenue_change = comparisons["total_revenue_generated"]["percentage_change"]
        if revenue_change > 10:
            insights.append({
                "type": "success",
                "title": "Strong Revenue Growth",
                "description": f"Revenue increased by {revenue_change:.1f}% compared to the previous period."
            })
        elif revenue_change < -10:
            insights.append({
                "type": "warning",
                "title": "Revenue Decline",
                "description": f"Revenue decreased by {abs(revenue_change):.1f}% compared to the previous period."
            })
        
        # ROI insights
        roi_change = comparisons["overall_roi_percentage"]["percentage_change"]
        if roi_change > 5:
            insights.append({
                "type": "success",
                "title": "Improved Efficiency",
                "description": f"ROI improved by {roi_change:.1f}%, indicating better promotion efficiency."
            })
        elif roi_change < -5:
            insights.append({
                "type": "warning",
                "title": "Efficiency Decline",
                "description": f"ROI decreased by {abs(roi_change):.1f}%, suggesting less efficient promotions."
            })
        
        return insights