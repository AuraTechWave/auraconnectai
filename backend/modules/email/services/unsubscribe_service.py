# backend/modules/email/services/unsubscribe_service.py

import logging
import secrets
import hashlib
from typing import Optional, List
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from modules.email.models.email_models import EmailUnsubscribe, EmailTemplateCategory
from modules.email.schemas.email_schemas import EmailUnsubscribeRequest

logger = logging.getLogger(__name__)


class UnsubscribeService:
    """Service for managing email unsubscribes"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def unsubscribe(
        self,
        request: EmailUnsubscribeRequest,
        customer_id: Optional[int] = None
    ) -> EmailUnsubscribe:
        """
        Process unsubscribe request
        
        Args:
            request: Unsubscribe request data
            customer_id: Optional customer ID
        
        Returns:
            EmailUnsubscribe record
        """
        # Check if already unsubscribed
        existing = self.db.query(EmailUnsubscribe).filter(
            and_(
                EmailUnsubscribe.email == request.email,
                EmailUnsubscribe.is_active == True
            )
        ).first()
        
        if existing:
            # Update existing record
            if request.unsubscribe_all:
                existing.unsubscribe_all = True
                existing.unsubscribed_categories = None
            elif request.categories:
                if existing.unsubscribe_all:
                    # Already unsubscribed from all
                    logger.info(f"Email {request.email} already unsubscribed from all categories")
                    return existing
                
                # Add categories to existing list
                current_categories = set(existing.unsubscribed_categories or [])
                current_categories.update(cat.value for cat in request.categories)
                existing.unsubscribed_categories = list(current_categories)
            
            existing.unsubscribe_reason = request.reason or existing.unsubscribe_reason
            existing.updated_at = datetime.utcnow()
            
            self.db.commit()
            self.db.refresh(existing)
            
            logger.info(f"Updated unsubscribe for {request.email}")
            return existing
        
        # Create new unsubscribe record
        unsubscribe = EmailUnsubscribe(
            email=request.email,
            customer_id=customer_id,
            unsubscribe_all=request.unsubscribe_all,
            unsubscribed_categories=[cat.value for cat in request.categories] if request.categories else None,
            unsubscribe_token=self.generate_token(request.email),
            unsubscribe_reason=request.reason,
            is_active=True
        )
        
        self.db.add(unsubscribe)
        self.db.commit()
        self.db.refresh(unsubscribe)
        
        logger.info(f"Created unsubscribe for {request.email}")
        return unsubscribe
    
    def resubscribe(self, email: str) -> bool:
        """
        Resubscribe an email address
        
        Args:
            email: Email address to resubscribe
        
        Returns:
            True if resubscribed successfully
        """
        unsubscribe = self.db.query(EmailUnsubscribe).filter(
            and_(
                EmailUnsubscribe.email == email,
                EmailUnsubscribe.is_active == True
            )
        ).first()
        
        if not unsubscribe:
            logger.warning(f"No active unsubscribe found for {email}")
            return False
        
        unsubscribe.is_active = False
        unsubscribe.resubscribed_at = datetime.utcnow()
        
        self.db.commit()
        
        logger.info(f"Resubscribed {email}")
        return True
    
    def is_unsubscribed(self, email: str) -> bool:
        """
        Check if email is unsubscribed from all emails
        
        Args:
            email: Email address to check
        
        Returns:
            True if unsubscribed from all
        """
        unsubscribe = self.db.query(EmailUnsubscribe).filter(
            and_(
                EmailUnsubscribe.email == email,
                EmailUnsubscribe.is_active == True,
                EmailUnsubscribe.unsubscribe_all == True
            )
        ).first()
        
        return unsubscribe is not None
    
    def is_unsubscribed_from_category(
        self,
        email: str,
        category: EmailTemplateCategory
    ) -> bool:
        """
        Check if email is unsubscribed from specific category
        
        Args:
            email: Email address to check
            category: Email category
        
        Returns:
            True if unsubscribed from category
        """
        unsubscribe = self.db.query(EmailUnsubscribe).filter(
            and_(
                EmailUnsubscribe.email == email,
                EmailUnsubscribe.is_active == True
            )
        ).first()
        
        if not unsubscribe:
            return False
        
        # Check if unsubscribed from all
        if unsubscribe.unsubscribe_all:
            return True
        
        # Check if unsubscribed from specific category
        if unsubscribe.unsubscribed_categories:
            return category.value in unsubscribe.unsubscribed_categories
        
        return False
    
    def get_unsubscribed_categories(self, email: str) -> List[EmailTemplateCategory]:
        """
        Get list of categories an email is unsubscribed from
        
        Args:
            email: Email address
        
        Returns:
            List of unsubscribed categories
        """
        unsubscribe = self.db.query(EmailUnsubscribe).filter(
            and_(
                EmailUnsubscribe.email == email,
                EmailUnsubscribe.is_active == True
            )
        ).first()
        
        if not unsubscribe:
            return []
        
        if unsubscribe.unsubscribe_all:
            # Return all categories
            return list(EmailTemplateCategory)
        
        if unsubscribe.unsubscribed_categories:
            return [
                EmailTemplateCategory(cat) 
                for cat in unsubscribe.unsubscribed_categories
            ]
        
        return []
    
    def verify_token(self, email: str, token: str) -> bool:
        """
        Verify unsubscribe token
        
        Args:
            email: Email address
            token: Unsubscribe token
        
        Returns:
            True if token is valid
        """
        unsubscribe = self.db.query(EmailUnsubscribe).filter(
            and_(
                EmailUnsubscribe.email == email,
                EmailUnsubscribe.unsubscribe_token == token
            )
        ).first()
        
        return unsubscribe is not None
    
    def generate_token(self, email: str) -> str:
        """
        Generate unique unsubscribe token for an email
        
        Args:
            email: Email address
        
        Returns:
            Unsubscribe token
        """
        # Create a unique token using email and random value
        random_value = secrets.token_hex(16)
        token_string = f"{email}:{random_value}"
        
        # Create hash of the token
        token_hash = hashlib.sha256(token_string.encode()).hexdigest()[:32]
        
        return token_hash
    
    def process_unsubscribe_link(
        self,
        email: str,
        token: str,
        categories: Optional[List[EmailTemplateCategory]] = None
    ) -> bool:
        """
        Process unsubscribe from link click
        
        Args:
            email: Email address
            token: Unsubscribe token
            categories: Optional specific categories to unsubscribe from
        
        Returns:
            True if processed successfully
        """
        # Verify token
        if not self.verify_token(email, token):
            logger.warning(f"Invalid unsubscribe token for {email}")
            return False
        
        # Process unsubscribe
        request = EmailUnsubscribeRequest(
            email=email,
            unsubscribe_all=categories is None,
            categories=categories,
            reason="Unsubscribed via link"
        )
        
        self.unsubscribe(request)
        return True
    
    def get_unsubscribe_stats(self) -> Dict[str, Any]:
        """
        Get unsubscribe statistics
        
        Returns:
            Dictionary with statistics
        """
        total_unsubscribes = self.db.query(EmailUnsubscribe).filter(
            EmailUnsubscribe.is_active == True
        ).count()
        
        unsubscribe_all_count = self.db.query(EmailUnsubscribe).filter(
            and_(
                EmailUnsubscribe.is_active == True,
                EmailUnsubscribe.unsubscribe_all == True
            )
        ).count()
        
        resubscribed_count = self.db.query(EmailUnsubscribe).filter(
            EmailUnsubscribe.resubscribed_at.isnot(None)
        ).count()
        
        # Count by category
        category_counts = {}
        partial_unsubscribes = self.db.query(EmailUnsubscribe).filter(
            and_(
                EmailUnsubscribe.is_active == True,
                EmailUnsubscribe.unsubscribe_all == False,
                EmailUnsubscribe.unsubscribed_categories.isnot(None)
            )
        ).all()
        
        for unsubscribe in partial_unsubscribes:
            for category in unsubscribe.unsubscribed_categories:
                category_counts[category] = category_counts.get(category, 0) + 1
        
        return {
            'total_unsubscribes': total_unsubscribes,
            'unsubscribe_all_count': unsubscribe_all_count,
            'partial_unsubscribe_count': total_unsubscribes - unsubscribe_all_count,
            'resubscribed_count': resubscribed_count,
            'by_category': category_counts
        }