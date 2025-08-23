# backend/modules/email/services/auth_email_service.py

import logging
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
import secrets
import hashlib

from modules.email.services.email_service import EmailService
from modules.email.schemas.email_schemas import EmailSendRequest
from modules.auth.models.user_models import User, PasswordResetToken
from core.config import settings

logger = logging.getLogger(__name__)


class AuthEmailService:
    """Service for sending authentication-related emails"""
    
    def __init__(self, db: Session):
        self.db = db
        self.email_service = EmailService(db)
        self.reset_token_expiry_hours = 24
    
    async def send_password_reset_email(self, user_id: int) -> bool:
        """
        Send password reset email to user
        
        Args:
            user_id: User ID
        
        Returns:
            True if email was sent successfully
        """
        try:
            # Get user
            user = self.db.query(User).filter(User.id == user_id).first()
            
            if not user or not user.email:
                logger.error(f"User {user_id} not found or has no email")
                return False
            
            # Generate reset token
            reset_token = self._generate_reset_token()
            
            # Store token in database
            password_reset = PasswordResetToken(
                user_id=user.id,
                token=self._hash_token(reset_token),
                expires_at=datetime.utcnow() + timedelta(hours=self.reset_token_expiry_hours),
                created_at=datetime.utcnow()
            )
            
            # Invalidate any existing tokens for this user
            self.db.query(PasswordResetToken).filter(
                PasswordResetToken.user_id == user.id,
                PasswordResetToken.used_at.is_(None)
            ).update({"used_at": datetime.utcnow()})
            
            self.db.add(password_reset)
            self.db.commit()
            
            # Prepare template variables
            template_vars = {
                "user_name": user.full_name or user.email,
                "reset_link": f"{settings.FRONTEND_URL}/auth/reset-password?token={reset_token}",
                "expiry_hours": self.reset_token_expiry_hours,
                "restaurant_name": settings.RESTAURANT_NAME
            }
            
            # Send email
            email_request = EmailSendRequest(
                to_email=user.email,
                to_name=user.full_name,
                template_id=self._get_template_id("password_reset"),
                template_variables=template_vars,
                user_id=user.id,
                tags=["auth", "password_reset"],
                metadata={
                    "user_id": user.id,
                    "token_expires": password_reset.expires_at.isoformat()
                }
            )
            
            await self.email_service.send_email(email_request)
            logger.info(f"Sent password reset email to user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error sending password reset email: {str(e)}")
            return False
    
    async def send_password_changed_notification(self, user_id: int) -> bool:
        """
        Send notification that password was changed
        
        Args:
            user_id: User ID
        
        Returns:
            True if email was sent successfully
        """
        try:
            user = self.db.query(User).filter(User.id == user_id).first()
            
            if not user or not user.email:
                return False
            
            # Prepare template variables
            template_vars = {
                "user_name": user.full_name or user.email,
                "changed_at": datetime.utcnow().strftime("%B %d, %Y at %I:%M %p UTC"),
                "restaurant_name": settings.RESTAURANT_NAME,
                "support_email": settings.SUPPORT_EMAIL or settings.RESTAURANT_EMAIL
            }
            
            # Send email
            email_request = EmailSendRequest(
                to_email=user.email,
                to_name=user.full_name,
                subject="Your password has been changed",
                html_body=self._generate_password_changed_html(template_vars),
                text_body=self._generate_password_changed_text(template_vars),
                user_id=user.id,
                tags=["auth", "password_changed"]
            )
            
            await self.email_service.send_email(email_request)
            logger.info(f"Sent password changed notification to user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error sending password changed email: {str(e)}")
            return False
    
    async def send_welcome_email(
        self, 
        user_id: int,
        is_staff: bool = False
    ) -> bool:
        """
        Send welcome email to new user
        
        Args:
            user_id: User ID
            is_staff: Whether user is staff member
        
        Returns:
            True if email was sent successfully
        """
        try:
            user = self.db.query(User).filter(User.id == user_id).first()
            
            if not user or not user.email:
                return False
            
            # Check for customer details
            customer = None
            if user.customer_id:
                from modules.customers.models.customer_models import Customer
                customer = self.db.query(Customer).filter(
                    Customer.id == user.customer_id
                ).first()
            
            # Prepare template variables
            template_vars = {
                "customer_name": user.full_name or (customer.name if customer else user.email),
                "restaurant_name": settings.RESTAURANT_NAME,
                "menu_url": f"{settings.FRONTEND_URL}/menu",
                "welcome_offer": settings.WELCOME_OFFER_ENABLED,
                "welcome_offer_description": settings.WELCOME_OFFER_DESCRIPTION,
                "welcome_offer_code": settings.WELCOME_OFFER_CODE,
                "welcome_offer_expiry": (datetime.utcnow() + timedelta(days=30)).strftime("%B %d, %Y"),
                "facebook_url": settings.FACEBOOK_URL,
                "instagram_url": settings.INSTAGRAM_URL,
                "twitter_url": settings.TWITTER_URL
            }
            
            # Send email
            email_request = EmailSendRequest(
                to_email=user.email,
                to_name=user.full_name,
                template_id=self._get_template_id("welcome_email"),
                template_variables=template_vars,
                user_id=user.id,
                customer_id=user.customer_id,
                tags=["welcome", "onboarding"],
                metadata={
                    "is_staff": is_staff,
                    "has_customer": user.customer_id is not None
                }
            )
            
            await self.email_service.send_email(email_request)
            logger.info(f"Sent welcome email to user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error sending welcome email: {str(e)}")
            return False
    
    async def send_account_verification_email(self, user_id: int) -> bool:
        """
        Send email verification link
        
        Args:
            user_id: User ID
        
        Returns:
            True if email was sent successfully
        """
        try:
            user = self.db.query(User).filter(User.id == user_id).first()
            
            if not user or not user.email:
                return False
            
            # Generate verification token
            verification_token = self._generate_verification_token()
            
            # Store token (you might want to create a separate table for this)
            user.email_verification_token = self._hash_token(verification_token)
            user.email_verification_sent_at = datetime.utcnow()
            self.db.commit()
            
            # Prepare template variables
            template_vars = {
                "user_name": user.full_name or user.email,
                "verification_link": f"{settings.FRONTEND_URL}/auth/verify-email?token={verification_token}",
                "restaurant_name": settings.RESTAURANT_NAME
            }
            
            # Send email
            email_request = EmailSendRequest(
                to_email=user.email,
                to_name=user.full_name,
                subject="Verify your email address",
                html_body=self._generate_verification_html(template_vars),
                text_body=self._generate_verification_text(template_vars),
                user_id=user.id,
                tags=["auth", "verification"]
            )
            
            await self.email_service.send_email(email_request)
            logger.info(f"Sent verification email to user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error sending verification email: {str(e)}")
            return False
    
    def _generate_reset_token(self) -> str:
        """Generate a secure random reset token"""
        return secrets.token_urlsafe(32)
    
    def _generate_verification_token(self) -> str:
        """Generate a secure random verification token"""
        return secrets.token_urlsafe(32)
    
    def _hash_token(self, token: str) -> str:
        """Hash a token for secure storage"""
        return hashlib.sha256(token.encode()).hexdigest()
    
    def _get_template_id(self, template_name: str) -> int:
        """Get template ID by name"""
        from modules.email.models.email_models import EmailTemplate
        
        template = self.db.query(EmailTemplate).filter(
            EmailTemplate.name == template_name
        ).first()
        
        if template:
            return template.id
        
        raise ValueError(f"Email template '{template_name}' not found")
    
    def _generate_password_changed_html(self, vars: Dict[str, Any]) -> str:
        """Generate HTML for password changed email"""
        return f"""
        <h2>Your password has been changed</h2>
        <p>Hi {vars['user_name']},</p>
        <p>This is a confirmation that your password was successfully changed on {vars['changed_at']}.</p>
        
        <div style="background-color: #d1ecf1; padding: 20px; border-radius: 5px; margin: 20px 0;">
            <p><strong>If you made this change:</strong> No further action is needed.</p>
            <p><strong>If you didn't make this change:</strong> Please contact us immediately at {vars['support_email']}</p>
        </div>
        
        <h3>Security Tips:</h3>
        <ul>
            <li>Always use a strong, unique password</li>
            <li>Enable two-factor authentication when available</li>
            <li>Never share your password with anyone</li>
            <li>Be cautious of phishing emails asking for your password</li>
        </ul>
        
        <p>Thank you for keeping your account secure!</p>
        """
    
    def _generate_password_changed_text(self, vars: Dict[str, Any]) -> str:
        """Generate text for password changed email"""
        return f"""
        Your password has been changed
        
        Hi {vars['user_name']},
        
        This is a confirmation that your password was successfully changed on {vars['changed_at']}.
        
        If you made this change: No further action is needed.
        If you didn't make this change: Please contact us immediately at {vars['support_email']}
        
        SECURITY TIPS:
        - Always use a strong, unique password
        - Enable two-factor authentication when available
        - Never share your password with anyone
        - Be cautious of phishing emails asking for your password
        
        Thank you for keeping your account secure!
        """
    
    def _generate_verification_html(self, vars: Dict[str, Any]) -> str:
        """Generate HTML for email verification"""
        return f"""
        <h2>Verify your email address</h2>
        <p>Hi {vars['user_name']},</p>
        <p>Thank you for creating an account with {vars['restaurant_name']}!</p>
        <p>Please verify your email address by clicking the button below:</p>
        
        <div style="text-align: center; margin: 30px 0;">
            <a href="{vars['verification_link']}" style="display: inline-block; padding: 12px 30px; background-color: #28a745; color: #ffffff; text-decoration: none; border-radius: 5px;">Verify Email Address</a>
        </div>
        
        <p>Or copy and paste this link into your browser:</p>
        <p style="word-break: break-all; color: #007bff;">{vars['verification_link']}</p>
        
        <p>Verifying your email address helps us ensure that we can communicate important information about your orders and account.</p>
        
        <p>If you didn't create an account with us, please ignore this email.</p>
        """
    
    def _generate_verification_text(self, vars: Dict[str, Any]) -> str:
        """Generate text for email verification"""
        return f"""
        Verify your email address
        
        Hi {vars['user_name']},
        
        Thank you for creating an account with {vars['restaurant_name']}!
        
        Please verify your email address by clicking the following link:
        {vars['verification_link']}
        
        Verifying your email address helps us ensure that we can communicate important information about your orders and account.
        
        If you didn't create an account with us, please ignore this email.
        """