# backend/modules/email/services/tracking_service.py

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func

from modules.email.models.email_models import (
    EmailMessage, EmailBounce, EmailStatus, EmailProvider
)

logger = logging.getLogger(__name__)


class EmailTrackingService:
    """Service for tracking email delivery and engagement"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def record_bounce(
        self,
        email: str,
        email_message_id: Optional[int],
        bounce_type: str,
        bounce_subtype: Optional[str],
        provider: EmailProvider,
        provider_response: Optional[Dict[str, Any]],
        diagnostic_code: Optional[str],
        is_permanent: bool
    ) -> EmailBounce:
        """
        Record an email bounce
        
        Args:
            email: Bounced email address
            email_message_id: Associated message ID
            bounce_type: Type of bounce (hard, soft, block)
            bounce_subtype: Subtype of bounce
            provider: Email provider
            provider_response: Provider's response data
            diagnostic_code: Diagnostic information
            is_permanent: Whether bounce is permanent
        
        Returns:
            EmailBounce record
        """
        bounce = EmailBounce(
            email=email,
            email_message_id=email_message_id,
            bounce_type=bounce_type,
            bounce_subtype=bounce_subtype,
            provider=provider,
            provider_response=provider_response,
            diagnostic_code=diagnostic_code,
            is_permanent=is_permanent
        )
        
        self.db.add(bounce)
        self.db.commit()
        self.db.refresh(bounce)
        
        logger.info(f"Recorded {bounce_type} bounce for {email}")
        return bounce
    
    def is_email_bounced(self, email: str, check_permanent_only: bool = True) -> bool:
        """
        Check if an email address has bounced
        
        Args:
            email: Email address to check
            check_permanent_only: Only check for permanent bounces
        
        Returns:
            True if email has bounced
        """
        query = self.db.query(EmailBounce).filter(
            EmailBounce.email == email
        )
        
        if check_permanent_only:
            query = query.filter(EmailBounce.is_permanent == True)
        
        return query.first() is not None
    
    def get_bounce_count(self, email: str) -> int:
        """
        Get bounce count for an email address
        
        Args:
            email: Email address
        
        Returns:
            Number of bounces
        """
        return self.db.query(EmailBounce).filter(
            EmailBounce.email == email
        ).count()
    
    def get_recent_bounces(
        self,
        days: int = 7,
        limit: int = 100
    ) -> List[EmailBounce]:
        """
        Get recent bounces
        
        Args:
            days: Number of days to look back
            limit: Maximum results
        
        Returns:
            List of recent bounces
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        return self.db.query(EmailBounce).filter(
            EmailBounce.bounced_at >= cutoff_date
        ).order_by(EmailBounce.bounced_at.desc()).limit(limit).all()
    
    def track_open(
        self,
        message_id: int,
        opened_at: Optional[datetime] = None,
        user_agent: Optional[str] = None,
        ip_address: Optional[str] = None
    ) -> bool:
        """
        Track email open event
        
        Args:
            message_id: Email message ID
            opened_at: When the email was opened
            user_agent: User agent string
            ip_address: IP address
        
        Returns:
            True if tracked successfully
        """
        message = self.db.query(EmailMessage).filter(
            EmailMessage.id == message_id
        ).first()
        
        if not message:
            logger.warning(f"Email message {message_id} not found")
            return False
        
        # Only record first open
        if not message.opened_at:
            message.opened_at = opened_at or datetime.utcnow()
            message.status = EmailStatus.OPENED
            
            # Store additional data in metadata
            if user_agent or ip_address:
                if not message.metadata:
                    message.metadata = {}
                
                message.metadata['open_tracking'] = {
                    'user_agent': user_agent,
                    'ip_address': ip_address,
                    'timestamp': (opened_at or datetime.utcnow()).isoformat()
                }
            
            self.db.commit()
            logger.info(f"Tracked open for email {message_id}")
            return True
        
        return False
    
    def track_click(
        self,
        message_id: int,
        url: str,
        clicked_at: Optional[datetime] = None,
        user_agent: Optional[str] = None,
        ip_address: Optional[str] = None
    ) -> bool:
        """
        Track email click event
        
        Args:
            message_id: Email message ID
            url: Clicked URL
            clicked_at: When the link was clicked
            user_agent: User agent string
            ip_address: IP address
        
        Returns:
            True if tracked successfully
        """
        message = self.db.query(EmailMessage).filter(
            EmailMessage.id == message_id
        ).first()
        
        if not message:
            logger.warning(f"Email message {message_id} not found")
            return False
        
        # Update click status
        if not message.clicked_at:
            message.clicked_at = clicked_at or datetime.utcnow()
            message.status = EmailStatus.CLICKED
        
        # Store click data in metadata
        if not message.metadata:
            message.metadata = {}
        
        if 'click_tracking' not in message.metadata:
            message.metadata['click_tracking'] = []
        
        message.metadata['click_tracking'].append({
            'url': url,
            'user_agent': user_agent,
            'ip_address': ip_address,
            'timestamp': (clicked_at or datetime.utcnow()).isoformat()
        })
        
        self.db.commit()
        logger.info(f"Tracked click for email {message_id}: {url}")
        return True
    
    def get_engagement_metrics(
        self,
        start_date: datetime,
        end_date: datetime,
        customer_id: Optional[int] = None,
        template_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Get email engagement metrics for a period
        
        Args:
            start_date: Start date
            end_date: End date
            customer_id: Filter by customer
            template_id: Filter by template
        
        Returns:
            Dictionary with engagement metrics
        """
        query = self.db.query(EmailMessage).filter(
            and_(
                EmailMessage.created_at >= start_date,
                EmailMessage.created_at <= end_date,
                EmailMessage.direction == EmailDirection.OUTBOUND
            )
        )
        
        if customer_id:
            query = query.filter(EmailMessage.customer_id == customer_id)
        
        if template_id:
            query = query.filter(EmailMessage.template_id == template_id)
        
        messages = query.all()
        
        # Calculate metrics
        total = len(messages)
        sent = sum(1 for m in messages if m.sent_at is not None)
        delivered = sum(1 for m in messages if m.delivered_at is not None)
        opened = sum(1 for m in messages if m.opened_at is not None)
        clicked = sum(1 for m in messages if m.clicked_at is not None)
        bounced = sum(1 for m in messages if m.bounced_at is not None)
        complained = sum(1 for m in messages if m.complained_at is not None)
        
        # Calculate average times
        delivery_times = []
        open_times = []
        
        for message in messages:
            if message.sent_at and message.delivered_at:
                delivery_times.append(
                    (message.delivered_at - message.sent_at).total_seconds()
                )
            
            if message.delivered_at and message.opened_at:
                open_times.append(
                    (message.opened_at - message.delivered_at).total_seconds() / 3600  # hours
                )
        
        avg_delivery_time = sum(delivery_times) / len(delivery_times) if delivery_times else 0
        avg_time_to_open = sum(open_times) / len(open_times) if open_times else 0
        
        return {
            'total_emails': total,
            'sent': sent,
            'delivered': delivered,
            'opened': opened,
            'clicked': clicked,
            'bounced': bounced,
            'complained': complained,
            'delivery_rate': (delivered / sent * 100) if sent > 0 else 0,
            'open_rate': (opened / delivered * 100) if delivered > 0 else 0,
            'click_rate': (clicked / opened * 100) if opened > 0 else 0,
            'click_to_open_rate': (clicked / opened * 100) if opened > 0 else 0,
            'bounce_rate': (bounced / sent * 100) if sent > 0 else 0,
            'complaint_rate': (complained / delivered * 100) if delivered > 0 else 0,
            'avg_delivery_time_seconds': avg_delivery_time,
            'avg_time_to_open_hours': avg_time_to_open
        }
    
    def get_top_performing_templates(
        self,
        start_date: datetime,
        end_date: datetime,
        metric: str = 'open_rate',
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get top performing email templates
        
        Args:
            start_date: Start date
            end_date: End date
            metric: Metric to sort by (open_rate, click_rate, etc.)
            limit: Number of results
        
        Returns:
            List of template performance data
        """
        # Query to aggregate by template
        results = self.db.query(
            EmailMessage.template_id,
            func.count(EmailMessage.id).label('total'),
            func.sum(func.cast(EmailMessage.delivered_at.isnot(None), Integer)).label('delivered'),
            func.sum(func.cast(EmailMessage.opened_at.isnot(None), Integer)).label('opened'),
            func.sum(func.cast(EmailMessage.clicked_at.isnot(None), Integer)).label('clicked')
        ).filter(
            and_(
                EmailMessage.created_at >= start_date,
                EmailMessage.created_at <= end_date,
                EmailMessage.template_id.isnot(None)
            )
        ).group_by(EmailMessage.template_id).all()
        
        # Calculate metrics for each template
        template_metrics = []
        
        for result in results:
            if result.delivered > 0:
                open_rate = (result.opened / result.delivered) * 100
                click_rate = (result.clicked / result.delivered) * 100
                click_to_open_rate = (result.clicked / result.opened * 100) if result.opened > 0 else 0
                
                template = self.db.query(EmailTemplate).filter(
                    EmailTemplate.id == result.template_id
                ).first()
                
                if template:
                    template_metrics.append({
                        'template_id': result.template_id,
                        'template_name': template.name,
                        'category': template.category.value,
                        'total_sent': result.total,
                        'delivered': result.delivered,
                        'opened': result.opened,
                        'clicked': result.clicked,
                        'open_rate': open_rate,
                        'click_rate': click_rate,
                        'click_to_open_rate': click_to_open_rate
                    })
        
        # Sort by requested metric
        if metric in ['open_rate', 'click_rate', 'click_to_open_rate']:
            template_metrics.sort(key=lambda x: x[metric], reverse=True)
        
        return template_metrics[:limit]
    
    def get_email_health_score(self) -> Dict[str, Any]:
        """
        Calculate overall email health score based on recent performance
        
        Returns:
            Dictionary with health score and factors
        """
        # Look at last 30 days
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=30)
        
        metrics = self.get_engagement_metrics(start_date, end_date)
        
        # Calculate health score (0-100)
        score = 100
        factors = []
        
        # Delivery rate factor
        if metrics['delivery_rate'] < 95:
            score -= 10
            factors.append(f"Low delivery rate: {metrics['delivery_rate']:.1f}%")
        
        # Bounce rate factor
        if metrics['bounce_rate'] > 5:
            score -= 15
            factors.append(f"High bounce rate: {metrics['bounce_rate']:.1f}%")
        elif metrics['bounce_rate'] > 2:
            score -= 5
            factors.append(f"Elevated bounce rate: {metrics['bounce_rate']:.1f}%")
        
        # Complaint rate factor
        if metrics['complaint_rate'] > 0.1:
            score -= 20
            factors.append(f"High complaint rate: {metrics['complaint_rate']:.2f}%")
        
        # Engagement factors
        if metrics['open_rate'] < 15:
            score -= 10
            factors.append(f"Low open rate: {metrics['open_rate']:.1f}%")
        elif metrics['open_rate'] > 25:
            score += 5
            factors.append(f"Excellent open rate: {metrics['open_rate']:.1f}%")
        
        if metrics['click_rate'] < 2:
            score -= 5
            factors.append(f"Low click rate: {metrics['click_rate']:.1f}%")
        elif metrics['click_rate'] > 5:
            score += 5
            factors.append(f"Excellent click rate: {metrics['click_rate']:.1f}%")
        
        # Ensure score is within bounds
        score = max(0, min(100, score))
        
        # Determine health status
        if score >= 90:
            status = "Excellent"
        elif score >= 75:
            status = "Good"
        elif score >= 60:
            status = "Fair"
        else:
            status = "Poor"
        
        return {
            'score': score,
            'status': status,
            'factors': factors,
            'metrics': metrics,
            'recommendations': self._get_health_recommendations(score, metrics, factors)
        }
    
    def _get_health_recommendations(
        self,
        score: int,
        metrics: Dict[str, Any],
        factors: List[str]
    ) -> List[str]:
        """Generate recommendations based on health score and metrics"""
        recommendations = []
        
        if metrics['bounce_rate'] > 2:
            recommendations.append(
                "Review and clean your email list to remove invalid addresses"
            )
        
        if metrics['complaint_rate'] > 0.05:
            recommendations.append(
                "Review email content and frequency to reduce complaints"
            )
        
        if metrics['open_rate'] < 20:
            recommendations.append(
                "Improve subject lines and sender reputation to increase opens"
            )
        
        if metrics['click_rate'] < 2:
            recommendations.append(
                "Enhance email content and CTAs to improve engagement"
            )
        
        if score < 75:
            recommendations.append(
                "Consider implementing a re-engagement campaign for inactive subscribers"
            )
        
        return recommendations