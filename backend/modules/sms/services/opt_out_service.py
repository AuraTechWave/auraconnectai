# backend/modules/sms/services/opt_out_service.py

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from modules.sms.models.sms_models import SMSOptOut, SMSTemplateCategory
from modules.sms.schemas.sms_schemas import SMSOptOutCreate, SMSOptOutUpdate

logger = logging.getLogger(__name__)


class OptOutService:
    """Service for managing SMS opt-out preferences"""
    
    OPT_OUT_KEYWORDS = ['STOP', 'UNSUBSCRIBE', 'CANCEL', 'END', 'QUIT', 'STOPALL']
    OPT_IN_KEYWORDS = ['START', 'SUBSCRIBE', 'YES', 'UNSTOP']
    
    def __init__(self, db: Session):
        self.db = db
    
    def process_opt_out(
        self,
        phone_number: str,
        reason: Optional[str] = None,
        method: str = 'sms_reply',
        customer_id: Optional[int] = None,
        categories: Optional[List[SMSTemplateCategory]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> SMSOptOut:
        """
        Process an opt-out request
        
        Args:
            phone_number: Phone number opting out
            reason: Reason for opt-out
            method: Method of opt-out (sms_reply, web, phone, email)
            customer_id: Associated customer ID
            categories: Specific categories to opt out from (None = all)
            ip_address: IP address for web opt-outs
            user_agent: User agent for web opt-outs
        
        Returns:
            SMSOptOut record
        """
        # Check if already exists
        opt_out = self.db.query(SMSOptOut).filter(
            SMSOptOut.phone_number == phone_number
        ).first()
        
        if opt_out:
            # Update existing record
            opt_out.opted_out = True
            opt_out.opt_out_date = datetime.utcnow()
            opt_out.opt_out_reason = reason or opt_out.opt_out_reason
            opt_out.opt_out_method = method
            
            if categories:
                existing_categories = opt_out.categories_opted_out or []
                opt_out.categories_opted_out = list(set(existing_categories + [c.value for c in categories]))
            else:
                opt_out.categories_opted_out = None  # Opt out from all
            
            if customer_id:
                opt_out.customer_id = customer_id
            if ip_address:
                opt_out.ip_address = ip_address
            if user_agent:
                opt_out.user_agent = user_agent
            
        else:
            # Create new opt-out record
            opt_out = SMSOptOut(
                phone_number=phone_number,
                customer_id=customer_id,
                opted_out=True,
                opt_out_date=datetime.utcnow(),
                opt_out_reason=reason,
                opt_out_method=method,
                categories_opted_out=[c.value for c in categories] if categories else None,
                ip_address=ip_address,
                user_agent=user_agent
            )
            self.db.add(opt_out)
        
        self.db.commit()
        self.db.refresh(opt_out)
        
        logger.info(f"Processed opt-out for {phone_number} via {method}")
        return opt_out
    
    def process_opt_in(
        self,
        phone_number: str,
        method: str = 'sms_reply',
        customer_id: Optional[int] = None,
        categories: Optional[List[SMSTemplateCategory]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> Optional[SMSOptOut]:
        """
        Process an opt-in request (re-subscribe)
        
        Args:
            phone_number: Phone number opting in
            method: Method of opt-in
            customer_id: Associated customer ID
            categories: Specific categories to opt into (None = all)
            ip_address: IP address for web opt-ins
            user_agent: User agent for web opt-ins
        
        Returns:
            Updated SMSOptOut record or None
        """
        opt_out = self.db.query(SMSOptOut).filter(
            SMSOptOut.phone_number == phone_number
        ).first()
        
        if not opt_out:
            # No opt-out record exists, nothing to do
            logger.info(f"No opt-out record found for {phone_number}")
            return None
        
        if categories and opt_out.categories_opted_out:
            # Remove specific categories from opt-out list
            remaining_categories = [
                cat for cat in opt_out.categories_opted_out 
                if cat not in [c.value for c in categories]
            ]
            opt_out.categories_opted_out = remaining_categories if remaining_categories else None
            
            # If no categories left, fully opt in
            if not opt_out.categories_opted_out:
                opt_out.opted_out = False
        else:
            # Full opt-in
            opt_out.opted_out = False
            opt_out.categories_opted_out = None
        
        opt_out.opted_in_date = datetime.utcnow()
        opt_out.opt_in_method = method
        
        if customer_id:
            opt_out.customer_id = customer_id
        if ip_address:
            opt_out.ip_address = ip_address
        if user_agent:
            opt_out.user_agent = user_agent
        
        self.db.commit()
        self.db.refresh(opt_out)
        
        logger.info(f"Processed opt-in for {phone_number} via {method}")
        return opt_out
    
    def is_opted_out(
        self,
        phone_number: str,
        category: Optional[SMSTemplateCategory] = None
    ) -> bool:
        """
        Check if a phone number is opted out
        
        Args:
            phone_number: Phone number to check
            category: Specific category to check (None = check general opt-out)
        
        Returns:
            True if opted out, False otherwise
        """
        opt_out = self.db.query(SMSOptOut).filter(
            SMSOptOut.phone_number == phone_number
        ).first()
        
        if not opt_out:
            return False
        
        if not opt_out.opted_out:
            return False
        
        if category and opt_out.categories_opted_out:
            # Check if specific category is opted out
            return category.value in opt_out.categories_opted_out
        
        # If no specific categories, user is opted out from all
        return opt_out.categories_opted_out is None or len(opt_out.categories_opted_out) == 0
    
    def process_inbound_message(
        self,
        phone_number: str,
        message_body: str,
        customer_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Process inbound SMS for opt-out/opt-in keywords
        
        Args:
            phone_number: Sender's phone number
            message_body: Message content
            customer_id: Associated customer ID
        
        Returns:
            Processing result with action taken
        """
        message_upper = message_body.strip().upper()
        
        # Check for opt-out keywords
        if any(keyword in message_upper for keyword in self.OPT_OUT_KEYWORDS):
            opt_out = self.process_opt_out(
                phone_number=phone_number,
                reason='SMS keyword',
                method='sms_reply',
                customer_id=customer_id
            )
            return {
                'action': 'opt_out',
                'message': 'You have been unsubscribed from SMS messages. Reply START to re-subscribe.',
                'opt_out_record': opt_out
            }
        
        # Check for opt-in keywords
        if any(keyword in message_upper for keyword in self.OPT_IN_KEYWORDS):
            opt_out = self.process_opt_in(
                phone_number=phone_number,
                method='sms_reply',
                customer_id=customer_id
            )
            return {
                'action': 'opt_in',
                'message': 'You have been re-subscribed to SMS messages. Reply STOP to unsubscribe.',
                'opt_out_record': opt_out
            }
        
        return {
            'action': 'none',
            'message': None,
            'opt_out_record': None
        }
    
    def get_opt_out_list(
        self,
        opted_out_only: bool = True,
        limit: int = 100,
        offset: int = 0
    ) -> List[SMSOptOut]:
        """
        Get list of opt-out records
        
        Args:
            opted_out_only: Only return currently opted-out numbers
            limit: Maximum number of results
            offset: Pagination offset
        
        Returns:
            List of opt-out records
        """
        query = self.db.query(SMSOptOut)
        
        if opted_out_only:
            query = query.filter(SMSOptOut.opted_out == True)
        
        return query.order_by(SMSOptOut.opt_out_date.desc()).offset(offset).limit(limit).all()
    
    def get_opt_out_statistics(self) -> Dict[str, Any]:
        """
        Get opt-out statistics
        
        Returns:
            Dictionary with statistics
        """
        total_records = self.db.query(SMSOptOut).count()
        currently_opted_out = self.db.query(SMSOptOut).filter(
            SMSOptOut.opted_out == True
        ).count()
        
        by_method = {}
        for record in self.db.query(SMSOptOut).filter(SMSOptOut.opted_out == True).all():
            method = record.opt_out_method or 'unknown'
            by_method[method] = by_method.get(method, 0) + 1
        
        return {
            'total_records': total_records,
            'currently_opted_out': currently_opted_out,
            'opt_out_rate': (currently_opted_out / total_records * 100) if total_records > 0 else 0,
            'by_method': by_method
        }
    
    def bulk_opt_out(
        self,
        phone_numbers: List[str],
        reason: str = 'Bulk opt-out',
        method: str = 'admin'
    ) -> int:
        """
        Bulk opt-out multiple phone numbers
        
        Args:
            phone_numbers: List of phone numbers to opt out
            reason: Reason for opt-out
            method: Method of opt-out
        
        Returns:
            Number of records processed
        """
        count = 0
        for phone_number in phone_numbers:
            try:
                self.process_opt_out(
                    phone_number=phone_number,
                    reason=reason,
                    method=method
                )
                count += 1
            except Exception as e:
                logger.error(f"Error processing opt-out for {phone_number}: {str(e)}")
        
        logger.info(f"Bulk opted out {count} phone numbers")
        return count
    
    def export_opt_out_list(self) -> List[Dict[str, Any]]:
        """
        Export opt-out list for compliance purposes
        
        Returns:
            List of opt-out records as dictionaries
        """
        opt_outs = self.db.query(SMSOptOut).filter(
            SMSOptOut.opted_out == True
        ).all()
        
        return [
            {
                'phone_number': opt_out.phone_number,
                'customer_id': opt_out.customer_id,
                'opt_out_date': opt_out.opt_out_date.isoformat(),
                'opt_out_reason': opt_out.opt_out_reason,
                'opt_out_method': opt_out.opt_out_method,
                'categories_opted_out': opt_out.categories_opted_out
            }
            for opt_out in opt_outs
        ]