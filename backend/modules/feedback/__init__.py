# backend/modules/feedback/__init__.py

"""
Customer Feedback and Reviews Module

This module provides comprehensive functionality for:
- Product and service reviews
- Customer feedback collection
- Sentiment analysis and categorization
- Review moderation and verification
- Feedback analytics and insights
- Review aggregation and scoring
- Notification system for reviews

Key Components:
- Models: Database models for reviews, feedback, and related entities
- Services: Business logic for review management, feedback processing
- Routers: API endpoints for feedback and review operations
- Analytics: Review analytics, sentiment analysis, and reporting
- Moderation: Content moderation and review verification
- Notifications: Real-time notifications for review events

Integration Points:
- Orders: Review requests after order completion
- Products: Product review aggregation and display
- Customers: Customer review history and preferences
- Notifications: Email/SMS notifications for review events
- Analytics: Review performance and sentiment insights
"""

__version__ = "1.0.0"
__author__ = "AuraConnect AI"