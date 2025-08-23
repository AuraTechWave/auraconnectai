# backend/modules/email/templates/base_templates.py

"""
Default email templates for the system
"""

from modules.email.models.email_models import EmailTemplateCategory

# Base HTML template wrapper
BASE_HTML_WRAPPER = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ subject }}</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            line-height: 1.6;
            color: #333333;
            margin: 0;
            padding: 0;
            background-color: #f4f4f4;
        }
        .container {
            max-width: 600px;
            margin: 0 auto;
            padding: 20px;
            background-color: #ffffff;
        }
        .header {
            text-align: center;
            padding: 20px 0;
            border-bottom: 1px solid #e0e0e0;
            margin-bottom: 30px;
        }
        .logo {
            max-width: 200px;
            height: auto;
        }
        .content {
            padding: 0 20px;
        }
        .button {
            display: inline-block;
            padding: 12px 30px;
            background-color: #007bff;
            color: #ffffff;
            text-decoration: none;
            border-radius: 5px;
            margin: 20px 0;
        }
        .button:hover {
            background-color: #0056b3;
        }
        .footer {
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid #e0e0e0;
            text-align: center;
            font-size: 14px;
            color: #666666;
        }
        .footer a {
            color: #007bff;
            text-decoration: none;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>{{ restaurant_name }}</h1>
        </div>
        <div class="content">
            {% block content %}{% endblock %}
        </div>
        <div class="footer">
            <p>&copy; {{ current_year }} {{ restaurant_name }}. All rights reserved.</p>
            <p>
                {{ restaurant_address }}<br>
                Phone: {{ restaurant_phone }} | Email: {{ restaurant_email }}
            </p>
        </div>
    </div>
</body>
</html>
"""

# Template definitions
EMAIL_TEMPLATES = [
    # Order Confirmation
    {
        "name": "order_confirmation",
        "description": "Sent when a customer places an order",
        "category": EmailTemplateCategory.ORDER,
        "subject_template": "Order Confirmation - #{{ order_number }}",
        "html_body_template": """
<h2>Thank you for your order!</h2>
<p>Hi {{ customer_name }},</p>
<p>We've received your order and are preparing it with care.</p>

<div style="background-color: #f8f9fa; padding: 20px; border-radius: 5px; margin: 20px 0;">
    <h3>Order Details</h3>
    <p><strong>Order Number:</strong> #{{ order_number }}<br>
    <strong>Order Date:</strong> {{ order_date }}<br>
    <strong>Estimated Ready Time:</strong> {{ estimated_ready_time }}</p>
</div>

<h3>Order Summary</h3>
<table style="width: 100%; border-collapse: collapse;">
    {% for item in order_items %}
    <tr>
        <td style="padding: 10px 0; border-bottom: 1px solid #e0e0e0;">
            {{ item.quantity }}x {{ item.name }}
            {% if item.modifiers %}
            <br><small style="color: #666;">{{ item.modifiers }}</small>
            {% endif %}
        </td>
        <td style="padding: 10px 0; border-bottom: 1px solid #e0e0e0; text-align: right;">
            ${{ item.total }}
        </td>
    </tr>
    {% endfor %}
    <tr>
        <td style="padding: 10px 0;"><strong>Subtotal</strong></td>
        <td style="padding: 10px 0; text-align: right;">${{ subtotal }}</td>
    </tr>
    {% if tax_amount %}
    <tr>
        <td style="padding: 10px 0;">Tax</td>
        <td style="padding: 10px 0; text-align: right;">${{ tax_amount }}</td>
    </tr>
    {% endif %}
    {% if delivery_fee %}
    <tr>
        <td style="padding: 10px 0;">Delivery Fee</td>
        <td style="padding: 10px 0; text-align: right;">${{ delivery_fee }}</td>
    </tr>
    {% endif %}
    <tr>
        <td style="padding: 10px 0; font-size: 18px;"><strong>Total</strong></td>
        <td style="padding: 10px 0; text-align: right; font-size: 18px;"><strong>${{ total_amount }}</strong></td>
    </tr>
</table>

{% if delivery_address %}
<h3>Delivery Information</h3>
<p>{{ delivery_address }}</p>
{% endif %}

{% if special_instructions %}
<h3>Special Instructions</h3>
<p>{{ special_instructions }}</p>
{% endif %}

<div style="text-align: center; margin: 30px 0;">
    <a href="{{ order_tracking_url }}" class="button">Track Your Order</a>
</div>

<p>If you have any questions about your order, please don't hesitate to contact us.</p>
<p>Thank you for choosing {{ restaurant_name }}!</p>
""",
        "text_body_template": """
Thank you for your order!

Hi {{ customer_name }},

We've received your order and are preparing it with care.

ORDER DETAILS
Order Number: #{{ order_number }}
Order Date: {{ order_date }}
Estimated Ready Time: {{ estimated_ready_time }}

ORDER SUMMARY
{% for item in order_items %}
{{ item.quantity }}x {{ item.name }} - ${{ item.total }}
{% if item.modifiers %}   {{ item.modifiers }}{% endif %}
{% endfor %}

Subtotal: ${{ subtotal }}
{% if tax_amount %}Tax: ${{ tax_amount }}{% endif %}
{% if delivery_fee %}Delivery Fee: ${{ delivery_fee }}{% endif %}
Total: ${{ total_amount }}

{% if delivery_address %}
DELIVERY INFORMATION
{{ delivery_address }}
{% endif %}

{% if special_instructions %}
SPECIAL INSTRUCTIONS
{{ special_instructions }}
{% endif %}

Track your order: {{ order_tracking_url }}

If you have any questions about your order, please don't hesitate to contact us.

Thank you for choosing {{ restaurant_name }}!
""",
        "is_transactional": True
    },
    
    # Reservation Confirmation
    {
        "name": "reservation_confirmation",
        "description": "Sent when a reservation is confirmed",
        "category": EmailTemplateCategory.RESERVATION,
        "subject_template": "Reservation Confirmed - {{ reservation_date }}",
        "html_body_template": """
<h2>Your reservation is confirmed!</h2>
<p>Hi {{ customer_name }},</p>
<p>We're looking forward to seeing you at {{ restaurant_name }}.</p>

<div style="background-color: #f8f9fa; padding: 20px; border-radius: 5px; margin: 20px 0;">
    <h3>Reservation Details</h3>
    <p><strong>Date:</strong> {{ reservation_date }}<br>
    <strong>Time:</strong> {{ reservation_time }}<br>
    <strong>Party Size:</strong> {{ party_size }} guests<br>
    <strong>Confirmation Code:</strong> {{ confirmation_code }}</p>
</div>

{% if special_requests %}
<h3>Special Requests</h3>
<p>{{ special_requests }}</p>
<p><em>We'll do our best to accommodate your requests.</em></p>
{% endif %}

<h3>Location</h3>
<p>{{ restaurant_name }}<br>
{{ restaurant_address }}<br>
Phone: {{ restaurant_phone }}</p>

<div style="text-align: center; margin: 30px 0;">
    <a href="{{ modify_reservation_url }}" class="button">Modify Reservation</a>
</div>

<p><strong>Cancellation Policy:</strong> Please cancel at least 2 hours before your reservation time if your plans change.</p>

<p>We look forward to serving you!</p>
""",
        "text_body_template": """
Your reservation is confirmed!

Hi {{ customer_name }},

We're looking forward to seeing you at {{ restaurant_name }}.

RESERVATION DETAILS
Date: {{ reservation_date }}
Time: {{ reservation_time }}
Party Size: {{ party_size }} guests
Confirmation Code: {{ confirmation_code }}

{% if special_requests %}
SPECIAL REQUESTS
{{ special_requests }}
We'll do our best to accommodate your requests.
{% endif %}

LOCATION
{{ restaurant_name }}
{{ restaurant_address }}
Phone: {{ restaurant_phone }}

To modify your reservation: {{ modify_reservation_url }}

CANCELLATION POLICY: Please cancel at least 2 hours before your reservation time if your plans change.

We look forward to serving you!
""",
        "is_transactional": True
    },
    
    # Password Reset
    {
        "name": "password_reset",
        "description": "Password reset request email",
        "category": EmailTemplateCategory.AUTHENTICATION,
        "subject_template": "Password Reset Request",
        "html_body_template": """
<h2>Password Reset Request</h2>
<p>Hi {{ user_name }},</p>
<p>We received a request to reset your password for your {{ restaurant_name }} account.</p>

<div style="text-align: center; margin: 30px 0;">
    <a href="{{ reset_link }}" class="button">Reset Password</a>
</div>

<p>Or copy and paste this link into your browser:</p>
<p style="word-break: break-all; color: #007bff;">{{ reset_link }}</p>

<p><strong>This link will expire in {{ expiry_hours }} hours.</strong></p>

<p>If you didn't request a password reset, please ignore this email. Your password won't be changed.</p>

<p>For security reasons, we recommend that you:</p>
<ul>
    <li>Use a strong, unique password</li>
    <li>Enable two-factor authentication if available</li>
    <li>Never share your password with anyone</li>
</ul>
""",
        "text_body_template": """
Password Reset Request

Hi {{ user_name }},

We received a request to reset your password for your {{ restaurant_name }} account.

To reset your password, click the following link:
{{ reset_link }}

This link will expire in {{ expiry_hours }} hours.

If you didn't request a password reset, please ignore this email. Your password won't be changed.

For security reasons, we recommend that you:
- Use a strong, unique password
- Enable two-factor authentication if available
- Never share your password with anyone
""",
        "is_transactional": True
    },
    
    # Welcome Email
    {
        "name": "welcome_email",
        "description": "Welcome email for new customers",
        "category": EmailTemplateCategory.NOTIFICATION,
        "subject_template": "Welcome to {{ restaurant_name }}!",
        "html_body_template": """
<h2>Welcome to {{ restaurant_name }}!</h2>
<p>Hi {{ customer_name }},</p>
<p>Thank you for joining our community! We're excited to have you as part of the {{ restaurant_name }} family.</p>

<h3>Here's what you can do with your account:</h3>
<ul>
    <li>📱 Order online for pickup or delivery</li>
    <li>🎯 Earn rewards with every purchase</li>
    <li>📅 Make reservations</li>
    <li>⭐ Leave reviews and feedback</li>
    <li>💳 Save your favorite payment methods</li>
    <li>📍 Save multiple delivery addresses</li>
</ul>

{% if welcome_offer %}
<div style="background-color: #fff3cd; padding: 20px; border-radius: 5px; margin: 20px 0; border: 1px solid #ffeaa7;">
    <h3 style="margin-top: 0;">🎉 Special Welcome Offer!</h3>
    <p>{{ welcome_offer_description }}</p>
    <p><strong>Use code: {{ welcome_offer_code }}</strong></p>
    <p><em>Valid until {{ welcome_offer_expiry }}</em></p>
</div>
{% endif %}

<div style="text-align: center; margin: 30px 0;">
    <a href="{{ menu_url }}" class="button">View Our Menu</a>
</div>

<h3>Stay Connected</h3>
<p>Follow us on social media for updates, special offers, and more!</p>
<p>
{% if facebook_url %}<a href="{{ facebook_url }}">Facebook</a> | {% endif %}
{% if instagram_url %}<a href="{{ instagram_url }}">Instagram</a> | {% endif %}
{% if twitter_url %}<a href="{{ twitter_url }}">Twitter</a>{% endif %}
</p>

<p>We look forward to serving you soon!</p>
""",
        "text_body_template": """
Welcome to {{ restaurant_name }}!

Hi {{ customer_name }},

Thank you for joining our community! We're excited to have you as part of the {{ restaurant_name }} family.

Here's what you can do with your account:
- Order online for pickup or delivery
- Earn rewards with every purchase
- Make reservations
- Leave reviews and feedback
- Save your favorite payment methods
- Save multiple delivery addresses

{% if welcome_offer %}
🎉 SPECIAL WELCOME OFFER!
{{ welcome_offer_description }}
Use code: {{ welcome_offer_code }}
Valid until {{ welcome_offer_expiry }}
{% endif %}

View our menu: {{ menu_url }}

STAY CONNECTED
Follow us on social media for updates, special offers, and more!
{% if facebook_url %}Facebook: {{ facebook_url }}{% endif %}
{% if instagram_url %}Instagram: {{ instagram_url }}{% endif %}
{% if twitter_url %}Twitter: {{ twitter_url }}{% endif %}

We look forward to serving you soon!
""",
        "is_transactional": False
    },
    
    # Receipt/Invoice
    {
        "name": "receipt",
        "description": "Payment receipt/invoice email",
        "category": EmailTemplateCategory.RECEIPT,
        "subject_template": "Receipt for Order #{{ order_number }}",
        "html_body_template": """
<h2>Payment Receipt</h2>
<p>Hi {{ customer_name }},</p>
<p>Thank you for your payment. Here's your receipt for your records.</p>

<div style="background-color: #f8f9fa; padding: 20px; border-radius: 5px; margin: 20px 0;">
    <h3>Receipt Details</h3>
    <p><strong>Receipt Number:</strong> {{ receipt_number }}<br>
    <strong>Order Number:</strong> #{{ order_number }}<br>
    <strong>Payment Date:</strong> {{ payment_date }}<br>
    <strong>Payment Method:</strong> {{ payment_method }}</p>
</div>

<h3>Order Summary</h3>
<table style="width: 100%; border-collapse: collapse;">
    {% for item in order_items %}
    <tr>
        <td style="padding: 10px 0; border-bottom: 1px solid #e0e0e0;">
            {{ item.quantity }}x {{ item.name }}
        </td>
        <td style="padding: 10px 0; border-bottom: 1px solid #e0e0e0; text-align: right;">
            ${{ item.total }}
        </td>
    </tr>
    {% endfor %}
    <tr>
        <td style="padding: 10px 0;"><strong>Subtotal</strong></td>
        <td style="padding: 10px 0; text-align: right;">${{ subtotal }}</td>
    </tr>
    <tr>
        <td style="padding: 10px 0;">Tax ({{ tax_rate }}%)</td>
        <td style="padding: 10px 0; text-align: right;">${{ tax_amount }}</td>
    </tr>
    {% if tip_amount %}
    <tr>
        <td style="padding: 10px 0;">Tip</td>
        <td style="padding: 10px 0; text-align: right;">${{ tip_amount }}</td>
    </tr>
    {% endif %}
    <tr>
        <td style="padding: 10px 0; font-size: 18px;"><strong>Total Paid</strong></td>
        <td style="padding: 10px 0; text-align: right; font-size: 18px;"><strong>${{ total_paid }}</strong></td>
    </tr>
</table>

<p style="margin-top: 30px;"><strong>{{ restaurant_name }}</strong><br>
{{ restaurant_address }}<br>
Tax ID: {{ restaurant_tax_id }}</p>

<div style="text-align: center; margin: 30px 0;">
    <a href="{{ download_receipt_url }}" class="button">Download PDF Receipt</a>
</div>
""",
        "text_body_template": """
Payment Receipt

Hi {{ customer_name }},

Thank you for your payment. Here's your receipt for your records.

RECEIPT DETAILS
Receipt Number: {{ receipt_number }}
Order Number: #{{ order_number }}
Payment Date: {{ payment_date }}
Payment Method: {{ payment_method }}

ORDER SUMMARY
{% for item in order_items %}
{{ item.quantity }}x {{ item.name }} - ${{ item.total }}
{% endfor %}

Subtotal: ${{ subtotal }}
Tax ({{ tax_rate }}%): ${{ tax_amount }}
{% if tip_amount %}Tip: ${{ tip_amount }}{% endif %}
Total Paid: ${{ total_paid }}

{{ restaurant_name }}
{{ restaurant_address }}
Tax ID: {{ restaurant_tax_id }}

Download PDF Receipt: {{ download_receipt_url }}
""",
        "is_transactional": True
    }
]