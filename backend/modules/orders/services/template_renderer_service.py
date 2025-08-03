# backend/modules/orders/services/template_renderer_service.py

import re
from typing import Dict, Optional, Any, Tuple
from datetime import datetime
from jinja2 import Template, Environment, select_autoescape
from markupsafe import Markup

from ..models.order_tracking_models import OrderTrackingTemplate, NotificationChannel


class TemplateRendererService:
    """Service for rendering channel-specific notification templates"""
    
    def __init__(self):
        # Initialize Jinja2 environment for HTML templates
        self.jinja_env = Environment(
            autoescape=select_autoescape(['html', 'xml']),
            trim_blocks=True,
            lstrip_blocks=True
        )
        
        # Add custom filters
        self.jinja_env.filters['format_currency'] = self._format_currency
        self.jinja_env.filters['format_time'] = self._format_time
        self.jinja_env.filters['truncate_sms'] = self._truncate_sms
    
    def render_for_channel(
        self,
        template: OrderTrackingTemplate,
        channel: NotificationChannel,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Render template for specific channel
        
        Args:
            template: Template object
            channel: Target notification channel
            context: Template context variables
            
        Returns:
            Dict with rendered content for the channel
        """
        # Add default context
        context = {
            **context,
            'now': datetime.utcnow(),
            'channel': channel.value
        }
        
        result = {}
        
        if channel == NotificationChannel.EMAIL:
            result = self._render_email(template, context)
        elif channel == NotificationChannel.PUSH:
            result = self._render_push(template, context)
        elif channel == NotificationChannel.SMS:
            result = self._render_sms(template, context)
        elif channel == NotificationChannel.WEBHOOK:
            result = self._render_webhook(template, context)
        else:
            # Default rendering
            result = {
                'subject': self._render_template(template.subject_template, context),
                'message': self._render_template(template.message_template, context)
            }
        
        # Add channel settings
        if template.channel_settings:
            result['settings'] = template.channel_settings
        
        return result
    
    def _render_email(self, template: OrderTrackingTemplate, context: Dict[str, Any]) -> Dict[str, Any]:
        """Render email-specific template"""
        result = {
            'subject': self._render_template(template.subject_template, context),
            'text_body': self._render_template(template.message_template, context)
        }
        
        # Render HTML body if available
        if template.html_template:
            html_template = self.jinja_env.from_string(template.html_template)
            result['html_body'] = html_template.render(**context)
        else:
            # Auto-generate basic HTML from text
            result['html_body'] = self._text_to_html(result['text_body'])
        
        # Add email-specific settings
        settings = template.channel_settings or {}
        if 'reply_to' in settings:
            result['reply_to'] = settings['reply_to']
        if 'category' in settings:
            result['category'] = settings['category']
        
        return result
    
    def _render_push(self, template: OrderTrackingTemplate, context: Dict[str, Any]) -> Dict[str, Any]:
        """Render push notification template"""
        # Use specific push templates if available
        title = template.push_title_template or template.subject_template
        body = template.push_body_template or template.message_template
        
        result = {
            'title': self._render_template(title, context),
            'body': self._render_template(body, context, max_length=178)  # iOS limit
        }
        
        # Add rich content
        if template.push_image_url:
            result['image_url'] = self._render_template(template.push_image_url, context)
        
        if template.push_action_url:
            result['action_url'] = self._render_template(template.push_action_url, context)
        
        # Add push-specific settings
        settings = template.channel_settings or {}
        result['sound'] = settings.get('sound', 'default')
        result['badge'] = settings.get('badge', 1)
        result['priority'] = settings.get('priority', 'normal')
        
        # Platform-specific data
        result['android'] = {
            'channel_id': settings.get('android_channel_id', 'order_updates'),
            'color': settings.get('android_color', '#FF5722')
        }
        
        result['ios'] = {
            'category': settings.get('ios_category', 'ORDER_UPDATE'),
            'thread_id': f"order_{context.get('order_id', 'unknown')}"
        }
        
        return result
    
    def _render_sms(self, template: OrderTrackingTemplate, context: Dict[str, Any]) -> Dict[str, Any]:
        """Render SMS template"""
        # Use SMS-specific template if available
        if template.sms_template:
            message = self._render_template(template.sms_template, context)
        else:
            # Fallback to main template but truncate
            message = self._render_template(template.message_template, context)
            message = self._truncate_sms(message)
        
        result = {
            'message': message,
            'length': len(message)
        }
        
        # Add SMS-specific settings
        settings = template.channel_settings or {}
        if 'sender_id' in settings:
            result['sender_id'] = settings['sender_id']
        result['type'] = settings.get('type', 'transactional')
        
        # Check if message needs to be split
        if len(message) > 160:
            result['segments'] = (len(message) - 1) // 153 + 1  # Multi-part SMS
        else:
            result['segments'] = 1
        
        return result
    
    def _render_webhook(self, template: OrderTrackingTemplate, context: Dict[str, Any]) -> Dict[str, Any]:
        """Render webhook payload"""
        # For webhooks, include all available data
        result = {
            'event_type': context.get('event_type'),
            'order_id': context.get('order_id'),
            'timestamp': datetime.utcnow().isoformat(),
            'message': self._render_template(template.message_template, context),
            'data': context
        }
        
        return result
    
    def _render_template(self, template_str: Optional[str], context: Dict[str, Any], max_length: Optional[int] = None) -> str:
        """Render a template string with context"""
        if not template_str:
            return ""
        
        # Simple template rendering using format
        try:
            rendered = template_str.format(**context)
        except KeyError as e:
            # If a variable is missing, use placeholder
            rendered = template_str
            for key, value in context.items():
                rendered = rendered.replace(f"{{{key}}}", str(value))
        
        # Truncate if needed
        if max_length and len(rendered) > max_length:
            rendered = rendered[:max_length-3] + "..."
        
        return rendered
    
    def _text_to_html(self, text: str) -> str:
        """Convert plain text to basic HTML"""
        # Escape HTML
        html = Markup.escape(text)
        
        # Convert newlines to <br>
        html = html.replace('\n', '<br>\n')
        
        # Basic HTML wrapper
        return f"""
        <html>
        <body style="font-family: Arial, sans-serif; padding: 20px;">
            <div style="max-width: 600px; margin: 0 auto;">
                {html}
            </div>
        </body>
        </html>
        """
    
    def _format_currency(self, value: float, currency: str = "USD") -> str:
        """Format currency values"""
        if currency == "USD":
            return f"${value:.2f}"
        return f"{value:.2f} {currency}"
    
    def _format_time(self, value: datetime, format: str = "%I:%M %p") -> str:
        """Format datetime values"""
        if isinstance(value, str):
            value = datetime.fromisoformat(value)
        return value.strftime(format)
    
    def _truncate_sms(self, text: str, length: int = 160) -> str:
        """Truncate text for SMS with ellipsis"""
        if len(text) <= length:
            return text
        
        # Try to break at word boundary
        truncated = text[:length-3]
        last_space = truncated.rfind(' ')
        if last_space > length - 20:  # If space is reasonably close to end
            truncated = truncated[:last_space]
        
        return truncated + "..."
    
    def validate_template(self, template_str: str, available_variables: Dict[str, str]) -> Tuple[bool, Optional[str]]:
        """
        Validate a template string
        
        Args:
            template_str: Template string to validate
            available_variables: Dict of variable names to descriptions
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not template_str:
            return True, None
        
        # Extract variables from template
        pattern = r'\{(\w+)\}'
        used_variables = set(re.findall(pattern, template_str))
        
        # Check if all variables are available
        available_keys = set(available_variables.keys())
        unknown_variables = used_variables - available_keys
        
        if unknown_variables:
            return False, f"Unknown variables: {', '.join(unknown_variables)}"
        
        # Try to render with dummy data
        try:
            dummy_context = {key: "test" for key in available_variables}
            self._render_template(template_str, dummy_context)
        except Exception as e:
            return False, f"Template error: {str(e)}"
        
        return True, None


# Channel-specific template defaults
DEFAULT_TEMPLATES = {
    NotificationChannel.EMAIL: {
        'order_placed': {
            'subject_template': 'Order #{order_id} Confirmed - {restaurant_name}',
            'message_template': '''Dear {customer_name},

Thank you for your order! We've received your order #{order_id} and it's being prepared.

Order Details:
- Order ID: {order_id}
- Total: {order_total}
- Estimated Time: {estimated_time}

You can track your order at: {tracking_url}

Thank you for choosing {restaurant_name}!
''',
            'html_template': '''<!DOCTYPE html>
<html>
<head>
    <style>
        body { font-family: Arial, sans-serif; }
        .container { max-width: 600px; margin: 0 auto; padding: 20px; }
        .header { background-color: #FF5722; color: white; padding: 20px; text-align: center; }
        .content { padding: 20px; background-color: #f5f5f5; }
        .button { background-color: #FF5722; color: white; padding: 10px 20px; text-decoration: none; display: inline-block; margin: 10px 0; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Order Confirmed!</h1>
        </div>
        <div class="content">
            <p>Dear {customer_name},</p>
            <p>Thank you for your order! We've received your order <strong>#{order_id}</strong> and it's being prepared.</p>
            
            <h3>Order Details:</h3>
            <ul>
                <li>Order ID: {order_id}</li>
                <li>Total: {order_total}</li>
                <li>Estimated Time: {estimated_time}</li>
            </ul>
            
            <a href="{tracking_url}" class="button">Track Your Order</a>
            
            <p>Thank you for choosing {restaurant_name}!</p>
        </div>
    </div>
</body>
</html>'''
        }
    },
    NotificationChannel.PUSH: {
        'order_ready': {
            'push_title_template': 'Order Ready! 🍽️',
            'push_body_template': 'Your order #{order_id} is ready for pickup!',
            'push_action_url': 'app://orders/{order_id}',
            'channel_settings': {
                'sound': 'order_ready.mp3',
                'priority': 'high',
                'android_channel_id': 'order_ready'
            }
        }
    },
    NotificationChannel.SMS: {
        'order_ready': {
            'sms_template': 'Your order #{order_id} is ready for pickup at {restaurant_name}! Show this code at pickup: {pickup_code}',
            'channel_settings': {
                'sender_id': 'RESTAURANT',
                'type': 'transactional'
            }
        }
    }
}