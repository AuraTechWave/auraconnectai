"""
Email Service for Password Reset and Security Notifications

This module provides email functionality for password reset workflows
and security notifications.
"""

import os
import smtplib
import logging
from datetime import datetime
from email.mime.text import MimeText
from email.mime.multipart import MimeMultipart
from typing import Optional, Dict, Any
from jinja2 import Template

logger = logging.getLogger(__name__)

# Email Configuration
SMTP_HOST = os.getenv("SMTP_HOST", "localhost")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_USE_TLS = os.getenv("SMTP_USE_TLS", "true").lower() == "true"
SMTP_FROM_EMAIL = os.getenv("SMTP_FROM_EMAIL", "noreply@auraconnect.ai")
SMTP_FROM_NAME = os.getenv("SMTP_FROM_NAME", "AuraConnect Security")

# Application Configuration
APP_NAME = os.getenv("APP_NAME", "AuraConnect")
APP_URL = os.getenv("APP_URL", "https://auraconnect.ai")
SUPPORT_EMAIL = os.getenv("SUPPORT_EMAIL", "support@auraconnect.ai")

# Email Templates
PASSWORD_RESET_HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Password Reset - {{ app_name }}</title>
    <style>
        body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
        .container { max-width: 600px; margin: 0 auto; padding: 20px; }
        .header { background: #007bff; color: white; padding: 20px; text-align: center; }
        .content { padding: 30px 20px; background: #f9f9f9; }
        .button { display: inline-block; padding: 12px 24px; background: #007bff; color: white; text-decoration: none; border-radius: 4px; margin: 20px 0; }
        .footer { padding: 20px; text-align: center; font-size: 12px; color: #666; }
        .warning { background: #fff3cd; border: 1px solid #ffeaa7; padding: 15px; border-radius: 4px; margin: 20px 0; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>{{ app_name }}</h1>
            <h2>Password Reset Request</h2>
        </div>
        
        <div class="content">
            <p>Hello,</p>
            
            <p>We received a request to reset the password for your {{ app_name }} account associated with <strong>{{ email }}</strong>.</p>
            
            <p>If you made this request, click the button below to reset your password:</p>
            
            <p style="text-align: center;">
                <a href="{{ reset_url }}" class="button">Reset Password</a>
            </p>
            
            <p>Or copy and paste this link into your browser:</p>
            <p style="word-break: break-all; background: #f8f9fa; padding: 10px; border-radius: 4px;">
                {{ reset_url }}
            </p>
            
            <div class="warning">
                <strong>Important:</strong>
                <ul>
                    <li>This link will expire in <strong>{{ expires_in }} minutes</strong></li>
                    <li>This link can only be used once</li>
                    <li>If you did not request this reset, please ignore this email</li>
                </ul>
            </div>
            
            <p>For your security, we recommend:</p>
            <ul>
                <li>Using a strong, unique password</li>
                <li>Not sharing your password with anyone</li>
                <li>Enabling two-factor authentication if available</li>
            </ul>
            
            <p>If you're having trouble, please contact our support team at <a href="mailto:{{ support_email }}">{{ support_email }}</a>.</p>
            
            <p>Thank you,<br>The {{ app_name }} Security Team</p>
        </div>
        
        <div class="footer">
            <p>This email was sent to {{ email }} at {{ timestamp }}.</p>
            <p>If you did not request this password reset, please contact support immediately.</p>
            <p>&copy; {{ current_year }} {{ app_name }}. All rights reserved.</p>
        </div>
    </div>
</body>
</html>
"""

PASSWORD_RESET_TEXT_TEMPLATE = """
{{ app_name }} - Password Reset Request

Hello,

We received a request to reset the password for your {{ app_name }} account associated with {{ email }}.

If you made this request, please visit the following link to reset your password:

{{ reset_url }}

IMPORTANT:
- This link will expire in {{ expires_in }} minutes
- This link can only be used once
- If you did not request this reset, please ignore this email

For your security, we recommend:
- Using a strong, unique password
- Not sharing your password with anyone
- Enabling two-factor authentication if available

If you're having trouble, please contact our support team at {{ support_email }}.

Thank you,
The {{ app_name }} Security Team

---
This email was sent to {{ email }} at {{ timestamp }}.
If you did not request this password reset, please contact support immediately.

© {{ current_year }} {{ app_name }}. All rights reserved.
"""

SECURITY_ALERT_HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Security Alert - {{ app_name }}</title>
    <style>
        body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
        .container { max-width: 600px; margin: 0 auto; padding: 20px; }
        .header { background: #dc3545; color: white; padding: 20px; text-align: center; }
        .content { padding: 30px 20px; background: #f9f9f9; }
        .alert { background: #f8d7da; border: 1px solid #f5c6cb; padding: 15px; border-radius: 4px; margin: 20px 0; }
        .footer { padding: 20px; text-align: center; font-size: 12px; color: #666; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>{{ app_name }}</h1>
            <h2>Security Alert</h2>
        </div>
        
        <div class="content">
            <div class="alert">
                <strong>{{ alert_type }}</strong>
            </div>
            
            <p>Hello,</p>
            
            <p>{{ message }}</p>
            
            <p><strong>Event Details:</strong></p>
            <ul>
                <li><strong>Time:</strong> {{ timestamp }}</li>
                <li><strong>IP Address:</strong> {{ ip_address or 'Unknown' }}</li>
                <li><strong>User Agent:</strong> {{ user_agent or 'Unknown' }}</li>
            </ul>
            
            <p>If this was you, no action is needed. If you did not perform this action, please:</p>
            <ol>
                <li>Change your password immediately</li>
                <li>Review your account activity</li>
                <li>Contact our support team at <a href="mailto:{{ support_email }}">{{ support_email }}</a></li>
            </ol>
            
            <p>Thank you,<br>The {{ app_name }} Security Team</p>
        </div>
        
        <div class="footer">
            <p>This email was sent to {{ email }}.</p>
            <p>&copy; {{ current_year }} {{ app_name }}. All rights reserved.</p>
        </div>
    </div>
</body>
</html>
"""


class EmailService:
    """Service for sending password reset and security emails."""
    
    def __init__(self):
        """Initialize email service with configuration."""
        self.smtp_host = SMTP_HOST
        self.smtp_port = SMTP_PORT
        self.smtp_username = SMTP_USERNAME
        self.smtp_password = SMTP_PASSWORD
        self.smtp_use_tls = SMTP_USE_TLS
        self.from_email = SMTP_FROM_EMAIL
        self.from_name = SMTP_FROM_NAME
        
        # Validate configuration
        if not self.smtp_host:
            logger.warning("SMTP_HOST not configured - emails will not be sent")
    
    def _create_smtp_connection(self) -> Optional[smtplib.SMTP]:
        """Create SMTP connection."""
        try:
            server = smtplib.SMTP(self.smtp_host, self.smtp_port)
            
            if self.smtp_use_tls:
                server.starttls()
            
            if self.smtp_username and self.smtp_password:
                server.login(self.smtp_username, self.smtp_password)
            
            return server
        except Exception as e:
            logger.error(f"Failed to create SMTP connection: {e}")
            return None
    
    def _send_email(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: str
    ) -> bool:
        """Send email with both HTML and text content."""
        
        if not self.smtp_host:
            logger.warning(f"Email not sent to {to_email} - SMTP not configured")
            return False
        
        try:
            # Create message
            msg = MimeMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = f"{self.from_name} <{self.from_email}>"
            msg['To'] = to_email
            
            # Create text and HTML parts
            text_part = MimeText(text_content, 'plain')
            html_part = MimeText(html_content, 'html')
            
            msg.attach(text_part)
            msg.attach(html_part)
            
            # Send email
            server = self._create_smtp_connection()
            if not server:
                return False
            
            server.send_message(msg)
            server.quit()
            
            logger.info(f"Email sent successfully to {to_email}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {e}")
            return False
    
    def send_password_reset_email(
        self,
        email: str,
        reset_token: str,
        expires_in_minutes: int = 30
    ) -> bool:
        """
        Send password reset email.
        
        Args:
            email: Recipient email address
            reset_token: Password reset token
            expires_in_minutes: Token expiration time in minutes
            
        Returns:
            True if email sent successfully, False otherwise
        """
        
        # Create reset URL
        reset_url = f"{APP_URL}/auth/reset-password?token={reset_token}"
        
        # Template variables
        template_vars = {
            'app_name': APP_NAME,
            'email': email,
            'reset_url': reset_url,
            'expires_in': expires_in_minutes,
            'support_email': SUPPORT_EMAIL,
            'timestamp': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC'),
            'current_year': datetime.utcnow().year
        }
        
        # Render templates
        html_template = Template(PASSWORD_RESET_HTML_TEMPLATE)
        text_template = Template(PASSWORD_RESET_TEXT_TEMPLATE)
        
        html_content = html_template.render(**template_vars)
        text_content = text_template.render(**template_vars)
        
        subject = f"Password Reset Request - {APP_NAME}"
        
        return self._send_email(email, subject, html_content, text_content)
    
    def send_security_alert_email(
        self,
        email: str,
        alert_type: str,
        message: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> bool:
        """
        Send security alert email.
        
        Args:
            email: Recipient email address
            alert_type: Type of security alert
            message: Alert message
            ip_address: IP address of the event
            user_agent: User agent of the event
            
        Returns:
            True if email sent successfully, False otherwise
        """
        
        # Template variables
        template_vars = {
            'app_name': APP_NAME,
            'email': email,
            'alert_type': alert_type,
            'message': message,
            'ip_address': ip_address,
            'user_agent': user_agent,
            'support_email': SUPPORT_EMAIL,
            'timestamp': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC'),
            'current_year': datetime.utcnow().year
        }
        
        # Render template
        html_template = Template(SECURITY_ALERT_HTML_TEMPLATE)
        html_content = html_template.render(**template_vars)
        
        # Simple text version
        text_content = f"""
{APP_NAME} Security Alert

{alert_type}

{message}

Time: {template_vars['timestamp']}
IP Address: {ip_address or 'Unknown'}
User Agent: {user_agent or 'Unknown'}

If this was not you, please contact support at {SUPPORT_EMAIL}.

© {template_vars['current_year']} {APP_NAME}. All rights reserved.
        """.strip()
        
        subject = f"Security Alert - {APP_NAME}"
        
        return self._send_email(email, subject, html_content, text_content)
    
    def send_password_changed_notification(
        self,
        email: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> bool:
        """
        Send password changed notification.
        
        Args:
            email: Recipient email address
            ip_address: IP address of the change
            user_agent: User agent of the change
            
        Returns:
            True if email sent successfully, False otherwise
        """
        
        return self.send_security_alert_email(
            email=email,
            alert_type="Password Changed",
            message="Your password has been successfully changed. If you did not make this change, please contact our support team immediately.",
            ip_address=ip_address,
            user_agent=user_agent
        )
    
    def test_email_configuration(self) -> bool:
        """
        Test email configuration by attempting to connect.
        
        Returns:
            True if configuration is valid, False otherwise
        """
        
        if not self.smtp_host:
            logger.error("SMTP host not configured")
            return False
        
        try:
            server = self._create_smtp_connection()
            if server:
                server.quit()
                logger.info("Email configuration test successful")
                return True
            else:
                logger.error("Failed to create SMTP connection")
                return False
        except Exception as e:
            logger.error(f"Email configuration test failed: {e}")
            return False


# Global instance
email_service = EmailService()