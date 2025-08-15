# backend/modules/feedback/templates/email_templates.py

"""
Email templates for feedback and reviews notifications.

This module contains HTML email templates for various notification types.
"""

from typing import Dict, Any

# Base HTML template
BASE_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ subject }}</title>
    <style>
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 600px;
            margin: 0 auto;
            padding: 20px;
        }
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            text-align: center;
            border-radius: 8px 8px 0 0;
        }
        .content {
            background: white;
            padding: 30px;
            border: 1px solid #e1e5e9;
            border-top: none;
        }
        .footer {
            background: #f8f9fa;
            padding: 20px;
            text-align: center;
            border: 1px solid #e1e5e9;
            border-top: none;
            border-radius: 0 0 8px 8px;
            font-size: 14px;
            color: #6c757d;
        }
        .button {
            display: inline-block;
            background: #007bff;
            color: white;
            padding: 12px 24px;
            text-decoration: none;
            border-radius: 5px;
            margin: 15px 0;
        }
        .button:hover {
            background: #0056b3;
        }
        .rating {
            color: #ffc107;
            font-size: 18px;
        }
        .highlight {
            background: #fff3cd;
            padding: 15px;
            border-left: 4px solid #ffc107;
            margin: 20px 0;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>AuraConnect</h1>
        <p>{{ header_subtitle }}</p>
    </div>
    
    <div class="content">
        {{ content }}
    </div>
    
    <div class="footer">
        <p>This email was sent by AuraConnect AI</p>
        <p>If you have any questions, please contact our support team.</p>
        <p><a href="{{ unsubscribe_url }}">Unsubscribe</a> from these notifications</p>
    </div>
</body>
</html>
"""

# Review invitation template
REVIEW_INVITATION_TEMPLATE = """
<h2>We'd love to hear your feedback!</h2>

<p>Hi {{ customer_name }},</p>

<p>Thank you for your recent {{ entity_type }} purchase! We hope you're enjoying {{ entity_name }}.</p>

<p>Your opinion matters to us and helps other customers make informed decisions. Would you mind taking a few minutes to share your experience?</p>

<div class="highlight">
    <p><strong>Your review helps:</strong></p>
    <ul>
        <li>Other customers make better choices</li>
        <li>Us improve our products and services</li>
        <li>Build a stronger community</li>
    </ul>
</div>

<p style="text-align: center;">
    <a href="{{ review_url }}" class="button">Write Your Review</a>
</p>

<p><small>This invitation will expire on {{ expiry_date }}. If you've already left a review, thank you and please ignore this message.</small></p>
"""

# Review submitted confirmation template
REVIEW_SUBMITTED_TEMPLATE = """
<h2>Thank you for your review!</h2>

<p>Hi {{ customer_name }},</p>

<p>Thank you for taking the time to share your feedback about {{ entity_name }}. Your review has been submitted and is now being processed.</p>

<div class="highlight">
    <h3>Your Review Summary:</h3>
    <p><strong>Rating:</strong> <span class="rating">{{ rating_stars }}</span> ({{ rating }}/5)</p>
    <p><strong>Title:</strong> {{ review_title }}</p>
    <p><strong>Review:</strong> {{ review_content }}</p>
</div>

<p>Your review will be published after our moderation process, which typically takes 1-2 business days. We may contact you if we need any clarification.</p>

<p><strong>What happens next?</strong></p>
<ul>
    <li>Our team will review your submission for quality and guidelines compliance</li>
    <li>Once approved, your review will be visible to other customers</li>
    <li>You'll receive an email confirmation when it's published</li>
</ul>
"""

# Review approved template
REVIEW_APPROVED_TEMPLATE = """
<h2>Your review is now live!</h2>

<p>Hi {{ customer_name }},</p>

<p>Great news! Your review for {{ entity_name }} has been approved and is now visible to other customers.</p>

<div class="highlight">
    <p><strong>Your published review:</strong></p>
    <p><span class="rating">{{ rating_stars }}</span> {{ review_title }}</p>
    <p>{{ review_content }}</p>
</div>

<p style="text-align: center;">
    <a href="{{ review_url }}" class="button">View Your Review</a>
</p>

<p>Thank you for helping other customers make informed decisions! Your feedback is valuable to our community.</p>
"""

# Review rejected template
REVIEW_REJECTED_TEMPLATE = """
<h2>Review Update Required</h2>

<p>Hi {{ customer_name }},</p>

<p>Thank you for submitting your review for {{ entity_name }}. Unfortunately, we're unable to publish it in its current form as it doesn't meet our community guidelines.</p>

<div class="highlight">
    <p><strong>Reason for rejection:</strong></p>
    <p>{{ rejection_reason }}</p>
</div>

<p><strong>What you can do:</strong></p>
<ul>
    <li>Edit your review to address the issues mentioned above</li>
    <li>Resubmit your review for another review</li>
    <li>Contact our support team if you have questions</li>
</ul>

<p style="text-align: center;">
    <a href="{{ edit_review_url }}" class="button">Edit Your Review</a>
</p>

<p>We appreciate your understanding and look forward to your updated review!</p>
"""

# Feedback received template
FEEDBACK_RECEIVED_TEMPLATE = """
<h2>We received your feedback</h2>

<p>Hi {{ customer_name or 'Valued Customer' }},</p>

<p>Thank you for taking the time to share your feedback with us. We've received your message and want you to know that we take all feedback seriously.</p>

<div class="highlight">
    <h3>Your Feedback Summary:</h3>
    <p><strong>Type:</strong> {{ feedback_type }}</p>
    <p><strong>Subject:</strong> {{ feedback_subject }}</p>
    <p><strong>Priority:</strong> {{ feedback_priority }}</p>
    <p><strong>Reference ID:</strong> #{{ feedback_id }}</p>
</div>

<p><strong>What happens next?</strong></p>
<ul>
    <li>Your feedback has been assigned to our {{ feedback_type.lower() }} team</li>
    <li>You'll receive updates on the progress via email</li>
    <li>Expected response time: {{ expected_response_time }}</li>
</ul>

<p>If you need immediate assistance, please contact our support team directly.</p>
"""

# Feedback response template
FEEDBACK_RESPONSE_TEMPLATE = """
<h2>Response to your feedback</h2>

<p>Hi {{ customer_name or 'Valued Customer' }},</p>

<p>We have an update regarding your feedback submission (Reference #{{ feedback_id }}).</p>

<div class="highlight">
    <h3>Our Response:</h3>
    <p><strong>From:</strong> {{ responder_name }}</p>
    <p><strong>Date:</strong> {{ response_date }}</p>
    <p>{{ response_message }}</p>
</div>

<p><strong>Original Feedback:</strong></p>
<p><em>{{ original_feedback }}</em></p>

{% if feedback_resolved %}
<p>This issue has been marked as resolved. If you have any further questions or concerns, please don't hesitate to contact us.</p>
{% else %}
<p>Our team is continuing to work on this issue. We'll keep you updated on any progress.</p>
{% endif %}

<p style="text-align: center;">
    <a href="{{ feedback_url }}" class="button">View Full Conversation</a>
</p>
"""

# Business response to review template
BUSINESS_RESPONSE_TEMPLATE = """
<h2>The business has responded to your review</h2>

<p>Hi {{ customer_name }},</p>

<p>{{ business_name }} has responded to your review for {{ entity_name }}. They wanted to personally address your feedback.</p>

<div class="highlight">
    <h3>Business Response:</h3>
    <p><strong>From:</strong> {{ responder_name }}, {{ responder_title }}</p>
    <p><strong>Date:</strong> {{ response_date }}</p>
    <p>{{ response_content }}</p>
</div>

<p><strong>Your Original Review:</strong></p>
<p><span class="rating">{{ rating_stars }}</span> {{ review_title }}</p>
<p><em>{{ review_content }}</em></p>

<p style="text-align: center;">
    <a href="{{ review_url }}" class="button">View Full Conversation</a>
</p>

<p>Thank you for sharing your experience and helping {{ business_name }} improve their service!</p>
"""

# Template mapping
EMAIL_TEMPLATES = {
    "review_invitation": {
        "subject": "Share your experience with {{ entity_name }}",
        "header_subtitle": "Your Opinion Matters",
        "content": REVIEW_INVITATION_TEMPLATE,
    },
    "review_submitted": {
        "subject": "Thank you for your review!",
        "header_subtitle": "Review Confirmation",
        "content": REVIEW_SUBMITTED_TEMPLATE,
    },
    "review_approved": {
        "subject": "Your review is now live!",
        "header_subtitle": "Review Published",
        "content": REVIEW_APPROVED_TEMPLATE,
    },
    "review_rejected": {
        "subject": "Review Update Required",
        "header_subtitle": "Review Guidelines",
        "content": REVIEW_REJECTED_TEMPLATE,
    },
    "feedback_received": {
        "subject": "We received your feedback - Reference #{{ feedback_id }}",
        "header_subtitle": "Feedback Confirmation",
        "content": FEEDBACK_RECEIVED_TEMPLATE,
    },
    "feedback_response": {
        "subject": "Response to your feedback - Reference #{{ feedback_id }}",
        "header_subtitle": "Feedback Update",
        "content": FEEDBACK_RESPONSE_TEMPLATE,
    },
    "business_response": {
        "subject": "{{ business_name }} responded to your review",
        "header_subtitle": "Business Response",
        "content": BUSINESS_RESPONSE_TEMPLATE,
    },
}


def render_email_template(
    template_key: str, variables: Dict[str, Any]
) -> Dict[str, str]:
    """Render email template with variables"""
    template_config = EMAIL_TEMPLATES.get(template_key)

    if not template_config:
        raise ValueError(f"Template '{template_key}' not found")

    from jinja2 import Template

    # Render subject
    subject_template = Template(template_config["subject"])
    subject = subject_template.render(**variables)

    # Render content
    content_template = Template(template_config["content"])
    content = content_template.render(**variables)

    # Render full HTML
    base_template = Template(BASE_TEMPLATE)
    html_content = base_template.render(
        subject=subject,
        header_subtitle=template_config["header_subtitle"],
        content=content,
        unsubscribe_url=variables.get("unsubscribe_url", "#"),
        **variables,
    )

    # Generate text version (simplified)
    text_content = _html_to_text(content)

    return {
        "subject": subject,
        "html_content": html_content,
        "text_content": text_content,
    }


def _html_to_text(html_content: str) -> str:
    """Convert HTML content to plain text (simplified)"""
    import re

    # Remove HTML tags
    text = re.sub(r"<[^>]+>", "", html_content)

    # Clean up whitespace
    text = re.sub(r"\s+", " ", text)
    text = text.strip()

    return text


def get_rating_stars(rating: float) -> str:
    """Convert numeric rating to star representation"""
    full_stars = int(rating)
    half_star = 1 if rating - full_stars >= 0.5 else 0
    empty_stars = 5 - full_stars - half_star

    return "★" * full_stars + "☆" * half_star + "☆" * empty_stars
