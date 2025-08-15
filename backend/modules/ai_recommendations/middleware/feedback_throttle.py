# backend/modules/ai_recommendations/middleware/feedback_throttle.py

from typing import Dict, Optional, Tuple
from datetime import datetime, timedelta
from collections import defaultdict
import hashlib
from fastapi import Request, HTTPException
import logging

from ..metrics.model_metrics import ai_model_metrics

logger = logging.getLogger(__name__)


class FeedbackThrottler:
    """
    Rate limiter for feedback submissions to prevent spam.

    Implements token bucket algorithm with configurable limits per:
    - User ID
    - Session ID
    - IP address
    """

    def __init__(
        self,
        max_requests_per_minute: int = 5,
        max_requests_per_hour: int = 60,
        max_requests_per_day: int = 500,
        burst_size: int = 10,
    ):
        self.max_per_minute = max_requests_per_minute
        self.max_per_hour = max_requests_per_hour
        self.max_per_day = max_requests_per_day
        self.burst_size = burst_size

        # Storage for rate limit tracking
        self.request_counts: Dict[str, Dict[str, list]] = defaultdict(
            lambda: defaultdict(list)
        )

        # Blacklist for severe violations
        self.blacklist: Dict[str, datetime] = {}
        self.blacklist_duration = timedelta(hours=24)

    def _get_client_identifiers(
        self, request: Request, user_id: Optional[int] = None
    ) -> Dict[str, str]:
        """Extract client identifiers from request"""
        identifiers = {}

        # User ID if authenticated
        if user_id:
            identifiers["user"] = f"user:{user_id}"

        # Session ID from headers or cookies
        session_id = request.headers.get("X-Session-ID") or request.cookies.get(
            "session_id"
        )
        if session_id:
            identifiers["session"] = f"session:{session_id}"

        # IP address
        client_ip = request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
        if not client_ip:
            client_ip = request.client.host if request.client else "unknown"
        identifiers["ip"] = f"ip:{client_ip}"

        # Create composite key for stricter limiting
        composite_key = hashlib.sha256(
            f"{user_id}:{session_id}:{client_ip}".encode()
        ).hexdigest()[:16]
        identifiers["composite"] = f"composite:{composite_key}"

        return identifiers

    def _clean_old_requests(self, requests: list, cutoff_time: datetime) -> list:
        """Remove requests older than cutoff time"""
        return [req_time for req_time in requests if req_time > cutoff_time]

    def _check_rate_limit(
        self, identifier: str, identifier_type: str
    ) -> Tuple[bool, Optional[str]]:
        """Check if identifier has exceeded rate limits"""
        now = datetime.utcnow()

        # Check blacklist first
        if identifier in self.blacklist:
            if self.blacklist[identifier] > now:
                return False, "blacklisted"
            else:
                # Remove from blacklist if expired
                del self.blacklist[identifier]

        # Get request history
        requests = self.request_counts[identifier_type].get(identifier, [])

        # Clean old requests and check limits
        minute_ago = now - timedelta(minutes=1)
        hour_ago = now - timedelta(hours=1)
        day_ago = now - timedelta(days=1)

        # Check per-minute limit
        recent_minute = self._clean_old_requests(requests, minute_ago)
        if len(recent_minute) >= self.max_per_minute:
            # Check for burst allowance
            if len(recent_minute) >= self.burst_size:
                return False, f"exceeded_per_minute_limit_{len(recent_minute)}"

        # Check per-hour limit
        recent_hour = self._clean_old_requests(requests, hour_ago)
        if len(recent_hour) >= self.max_per_hour:
            return False, f"exceeded_per_hour_limit_{len(recent_hour)}"

        # Check per-day limit
        recent_day = self._clean_old_requests(requests, day_ago)
        if len(recent_day) >= self.max_per_day:
            # Add to blacklist for severe violations
            self.blacklist[identifier] = now + self.blacklist_duration
            return False, f"exceeded_per_day_limit_{len(recent_day)}_blacklisted"

        return True, None

    async def check_feedback_rate_limit(
        self, request: Request, user_id: Optional[int] = None
    ) -> bool:
        """
        Check if feedback request should be allowed

        Returns:
            bool: True if request is allowed, raises HTTPException if not
        """
        identifiers = self._get_client_identifiers(request, user_id)
        now = datetime.utcnow()

        # Check each identifier type
        for id_type, identifier in identifiers.items():
            allowed, reason = self._check_rate_limit(identifier, id_type)

            if not allowed:
                # Track throttled attempt
                ai_model_metrics.track_feedback_throttled(reason)

                # Log the violation
                logger.warning(f"Feedback throttled for {identifier}: {reason}")

                # Determine retry time
                retry_after = 60  # Default 1 minute
                if "hour" in reason:
                    retry_after = 3600
                elif "day" in reason or "blacklisted" in reason:
                    retry_after = 86400

                raise HTTPException(
                    status_code=429,
                    detail={
                        "error": "Too many feedback submissions",
                        "reason": reason,
                        "retry_after": retry_after,
                    },
                    headers={"Retry-After": str(retry_after)},
                )

        # Record successful request
        for id_type, identifier in identifiers.items():
            if identifier not in self.request_counts[id_type]:
                self.request_counts[id_type][identifier] = []
            self.request_counts[id_type][identifier].append(now)

        # Periodic cleanup of old data
        if len(self.request_counts) > 10000:  # Prevent memory bloat
            self._cleanup_old_data()

        return True

    def _cleanup_old_data(self):
        """Clean up old request data to prevent memory bloat"""
        now = datetime.utcnow()
        day_ago = now - timedelta(days=1)

        for id_type in list(self.request_counts.keys()):
            for identifier in list(self.request_counts[id_type].keys()):
                # Clean old requests
                requests = self.request_counts[id_type][identifier]
                cleaned = self._clean_old_requests(requests, day_ago)

                if cleaned:
                    self.request_counts[id_type][identifier] = cleaned
                else:
                    # Remove empty entries
                    del self.request_counts[id_type][identifier]

        # Clean expired blacklist entries
        for identifier in list(self.blacklist.keys()):
            if self.blacklist[identifier] <= now:
                del self.blacklist[identifier]

    def get_rate_limit_status(
        self, request: Request, user_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Get current rate limit status for a client"""
        identifiers = self._get_client_identifiers(request, user_id)
        now = datetime.utcnow()
        status = {}

        for id_type, identifier in identifiers.items():
            requests = self.request_counts[id_type].get(identifier, [])

            minute_ago = now - timedelta(minutes=1)
            hour_ago = now - timedelta(hours=1)
            day_ago = now - timedelta(days=1)

            recent_minute = len(self._clean_old_requests(requests, minute_ago))
            recent_hour = len(self._clean_old_requests(requests, hour_ago))
            recent_day = len(self._clean_old_requests(requests, day_ago))

            status[id_type] = {
                "requests_last_minute": recent_minute,
                "requests_last_hour": recent_hour,
                "requests_last_day": recent_day,
                "limits": {
                    "per_minute": self.max_per_minute,
                    "per_hour": self.max_per_hour,
                    "per_day": self.max_per_day,
                },
                "blacklisted": identifier in self.blacklist,
            }

        return status


# Create singleton throttler
feedback_throttler = FeedbackThrottler()


# Dependency for FastAPI routes
async def require_feedback_rate_limit(request: Request, user_id: Optional[int] = None):
    """FastAPI dependency to enforce feedback rate limits"""
    await feedback_throttler.check_feedback_rate_limit(request, user_id)
    return True
