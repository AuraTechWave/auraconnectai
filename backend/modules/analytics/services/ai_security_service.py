# backend/modules/analytics/services/ai_security_service.py

"""
AI Security Service for Analytics Assistant.

This service handles rate limiting, input validation, and security checks
for AI assistant queries to prevent abuse and ensure safe operations.
"""

import re
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from collections import defaultdict, deque
import hashlib
import json

from ..schemas.ai_assistant_schemas import ChatRequest, AnalyticsQuery

logger = logging.getLogger(__name__)


class AISecurityService:
    """Security service for AI analytics assistant"""

    def __init__(self):
        # Rate limiting configuration
        self.rate_limits = {
            "messages_per_minute": 20,
            "queries_per_hour": 100,
            "complex_queries_per_day": 50,
        }

        # User activity tracking
        self.user_activity: Dict[int, Dict[str, deque]] = defaultdict(
            lambda: {
                "messages": deque(maxlen=100),
                "queries": deque(maxlen=500),
                "complex_queries": deque(maxlen=100),
            }
        )

        # Blocked patterns for security
        self.blocked_patterns = self._initialize_blocked_patterns()

        # Sensitive data patterns
        self.sensitive_patterns = self._initialize_sensitive_patterns()

        # Query complexity scoring
        self.complexity_factors = {
            "time_range_days": 0.01,  # Per day in range
            "entities_count": 0.1,  # Per entity
            "metrics_count": 0.2,  # Per metric
            "grouping_count": 0.3,  # Per group by field
            "forecast": 2.0,  # Forecast queries
            "comparison": 1.5,  # Comparison queries
        }

    def _initialize_blocked_patterns(self) -> List[re.Pattern]:
        """Initialize patterns for blocking malicious input"""
        return [
            # SQL injection patterns
            re.compile(
                r"(union|select|insert|update|delete|drop|create|alter)\s+", re.I
            ),
            re.compile(r"(;|--|\*|\/\*|\*\/)", re.I),
            re.compile(r"(exec|execute|xp_|sp_)", re.I),
            # Script injection patterns
            re.compile(r"<script[^>]*>.*?</script>", re.I | re.S),
            re.compile(r"javascript:", re.I),
            re.compile(r"on\w+\s*=", re.I),
            # System command patterns
            re.compile(r"(system|eval|exec|passthru|shell_exec)", re.I),
            re.compile(r"(\||&&|;|\$\(|\`)", re.I),
            # Path traversal patterns
            re.compile(r"\.\.[\\/]"),
            re.compile(r"(etc\/passwd|windows\/system32)", re.I),
        ]

    def _initialize_sensitive_patterns(self) -> List[re.Pattern]:
        """Initialize patterns for detecting sensitive data"""
        return [
            # Credit card patterns
            re.compile(r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b"),
            # Social security numbers
            re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
            # Email addresses (to protect customer data)
            re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"),
            # Phone numbers
            re.compile(r"\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b"),
            # API keys or tokens
            re.compile(r"\b[A-Za-z0-9]{32,}\b"),
        ]

    def validate_request(
        self, request: ChatRequest, user_id: int
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate chat request for security issues.

        Args:
            request: Chat request to validate
            user_id: User making the request

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check message length
        if len(request.message) > 1000:
            return False, "Message too long (max 1000 characters)"

        # Check for blocked patterns
        for pattern in self.blocked_patterns:
            if pattern.search(request.message):
                logger.warning(
                    f"Blocked pattern detected from user {user_id}: {pattern.pattern}"
                )
                return False, "Invalid input detected"

        # Check for sensitive data
        for pattern in self.sensitive_patterns:
            if pattern.search(request.message):
                logger.warning(f"Sensitive data pattern detected from user {user_id}")
                return (
                    False,
                    "Please do not include sensitive information in your queries",
                )

        # Check rate limits
        is_allowed, limit_message = self.check_rate_limit(user_id, "messages")
        if not is_allowed:
            return False, limit_message

        return True, None

    def check_rate_limit(
        self, user_id: int, limit_type: str
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if user has exceeded rate limits.

        Args:
            user_id: User to check
            limit_type: Type of limit to check

        Returns:
            Tuple of (is_allowed, error_message)
        """
        now = datetime.now()
        activity = self.user_activity[user_id]

        if limit_type == "messages":
            # Check messages per minute
            activity["messages"].append(now)
            recent_messages = [
                msg for msg in activity["messages"] if now - msg < timedelta(minutes=1)
            ]

            if len(recent_messages) > self.rate_limits["messages_per_minute"]:
                return (
                    False,
                    f"Rate limit exceeded: Max {self.rate_limits['messages_per_minute']} messages per minute",
                )

        elif limit_type == "queries":
            # Check queries per hour
            activity["queries"].append(now)
            recent_queries = [
                q for q in activity["queries"] if now - q < timedelta(hours=1)
            ]

            if len(recent_queries) > self.rate_limits["queries_per_hour"]:
                return (
                    False,
                    f"Rate limit exceeded: Max {self.rate_limits['queries_per_hour']} queries per hour",
                )

        elif limit_type == "complex_queries":
            # Check complex queries per day
            activity["complex_queries"].append(now)
            recent_complex = [
                q for q in activity["complex_queries"] if now - q < timedelta(days=1)
            ]

            if len(recent_complex) > self.rate_limits["complex_queries_per_day"]:
                return (
                    False,
                    f"Rate limit exceeded: Max {self.rate_limits['complex_queries_per_day']} complex queries per day",
                )

        return True, None

    def sanitize_input(self, text: str) -> str:
        """
        Sanitize user input to remove potentially harmful content.

        Args:
            text: Input text to sanitize

        Returns:
            Sanitized text
        """
        # Remove HTML tags
        text = re.sub(r"<[^>]+>", "", text)

        # Remove multiple spaces
        text = re.sub(r"\s+", " ", text)

        # Remove control characters
        text = "".join(char for char in text if ord(char) >= 32 or char in "\n\r\t")

        # Trim whitespace
        text = text.strip()

        return text

    def calculate_query_complexity(self, query: AnalyticsQuery) -> float:
        """
        Calculate complexity score for a query.

        Args:
            query: Analytics query to score

        Returns:
            Complexity score (0.0 to 10.0)

        Scoring factors:
            - Time range: 0.01 per day
            - Entities: 0.1 per entity
            - Metrics: 0.2 per metric
            - Grouping: 0.3 per group field
            - Forecast queries: +2.0
            - Comparison queries: +1.5

        Example:
            Query for 30 days with 3 metrics and 2 groupings = 1.5 complexity
        """
        score = 0.0

        # Time range complexity
        if query.time_range:
            start_date = datetime.fromisoformat(query.time_range.get("start_date", ""))
            end_date = datetime.fromisoformat(query.time_range.get("end_date", ""))
            days = (end_date - start_date).days
            score += days * self.complexity_factors["time_range_days"]

        # Entity complexity
        if query.entities:
            entity_count = sum(
                len(v) if isinstance(v, list) else 1 for v in query.entities.values()
            )
            score += entity_count * self.complexity_factors["entities_count"]

        # Metrics complexity
        score += len(query.metrics) * self.complexity_factors["metrics_count"]

        # Grouping complexity
        if query.group_by:
            score += len(query.group_by) * self.complexity_factors["grouping_count"]

        # Intent-based complexity
        if query.intent.value == "forecast":
            score += self.complexity_factors["forecast"]
        elif query.intent.value == "comparison":
            score += self.complexity_factors["comparison"]

        return min(score, 10.0)  # Cap at 10.0

    def is_query_allowed(
        self, query: AnalyticsQuery, user_id: int
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if query is allowed based on complexity and rate limits.

        Args:
            query: Analytics query to check
            user_id: User making the query

        Returns:
            Tuple of (is_allowed, error_message)
        """
        # Calculate complexity
        complexity = self.calculate_query_complexity(query)

        # Check if it's a complex query
        if complexity > 3.0:
            is_allowed, message = self.check_rate_limit(user_id, "complex_queries")
            if not is_allowed:
                return False, message
        else:
            is_allowed, message = self.check_rate_limit(user_id, "queries")
            if not is_allowed:
                return False, message

        # Check for resource-intensive operations
        if query.limit and query.limit > 10000:
            return False, "Query limit too high (max 10000 records)"

        return True, None

    def redact_sensitive_data(self, text: str) -> str:
        """
        Redact sensitive information from text.

        Args:
            text: Text to redact

        Returns:
            Text with sensitive data redacted
        """
        redacted = text

        # Redact patterns
        redaction_patterns = [
            (
                r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b",
                "****-****-****-****",
            ),  # Credit cards
            (r"\b\d{3}-\d{2}-\d{4}\b", "***-**-****"),  # SSN
            (
                r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
                "***@***.***",
            ),  # Email
            (r"\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b", "***-***-****"),  # Phone
        ]

        for pattern, replacement in redaction_patterns:
            redacted = re.sub(pattern, replacement, redacted)

        return redacted

    def log_security_event(
        self, user_id: int, event_type: str, details: Dict[str, any]
    ):
        """
        Log security-related events for audit trail.

        Args:
            user_id: User involved in the event
            event_type: Type of security event
            details: Additional event details
        """
        logger.warning(
            f"Security event - User: {user_id}, Type: {event_type}, Details: {json.dumps(details)}"
        )

    def get_user_risk_score(self, user_id: int) -> float:
        """
        Calculate risk score for a user based on their activity.

        Args:
            user_id: User to score

        Returns:
            Risk score (0.0 to 1.0)
        """
        activity = self.user_activity[user_id]
        now = datetime.now()

        # Factors that increase risk
        risk_factors = {
            "high_message_rate": 0.2,
            "high_query_rate": 0.3,
            "complex_queries": 0.2,
            "blocked_attempts": 0.3,
        }

        score = 0.0

        # Check message rate
        recent_messages = [
            msg for msg in activity["messages"] if now - msg < timedelta(minutes=5)
        ]
        if len(recent_messages) > 50:
            score += risk_factors["high_message_rate"]

        # Check query rate
        recent_queries = [
            q for q in activity["queries"] if now - q < timedelta(hours=1)
        ]
        if len(recent_queries) > 80:
            score += risk_factors["high_query_rate"]

        # Check complex query usage
        complex_queries = [
            q for q in activity["complex_queries"] if now - q < timedelta(days=1)
        ]
        if len(complex_queries) > 30:
            score += risk_factors["complex_queries"]

        return min(score, 1.0)

    def reset_user_limits(self, user_id: int):
        """Reset rate limits for a specific user"""
        if user_id in self.user_activity:
            self.user_activity[user_id] = {
                "messages": deque(maxlen=100),
                "queries": deque(maxlen=500),
                "complex_queries": deque(maxlen=100),
            }

    def get_rate_limit_status(self, user_id: int) -> Dict[str, any]:
        """Get current rate limit status for a user"""
        now = datetime.now()
        activity = self.user_activity[user_id]

        # Calculate remaining allowances
        recent_messages = len(
            [msg for msg in activity["messages"] if now - msg < timedelta(minutes=1)]
        )

        recent_queries = len(
            [q for q in activity["queries"] if now - q < timedelta(hours=1)]
        )

        recent_complex = len(
            [q for q in activity["complex_queries"] if now - q < timedelta(days=1)]
        )

        return {
            "messages": {
                "used": recent_messages,
                "limit": self.rate_limits["messages_per_minute"],
                "remaining": max(
                    0, self.rate_limits["messages_per_minute"] - recent_messages
                ),
                "reset_in_seconds": 60,
            },
            "queries": {
                "used": recent_queries,
                "limit": self.rate_limits["queries_per_hour"],
                "remaining": max(
                    0, self.rate_limits["queries_per_hour"] - recent_queries
                ),
                "reset_in_seconds": 3600,
            },
            "complex_queries": {
                "used": recent_complex,
                "limit": self.rate_limits["complex_queries_per_day"],
                "remaining": max(
                    0, self.rate_limits["complex_queries_per_day"] - recent_complex
                ),
                "reset_in_seconds": 86400,
            },
        }
