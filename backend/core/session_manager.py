"""
Session Management for JWT Authentication with Refresh Tokens

Provides secure session management including refresh token storage,
blacklisting, and cleanup for the AuraConnect authentication system.
"""

import os
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, Set
from dataclasses import dataclass, field
import redis
from redis import Redis
import json
import logging
from .config_validation import config, get_redis_url

logger = logging.getLogger(__name__)

# Redis Configuration
REDIS_URL = get_redis_url()
SESSION_CLEANUP_INTERVAL = int(os.getenv("SESSION_CLEANUP_INTERVAL", "3600"))  # 1 hour


@dataclass
class Session:
    """User session data structure."""

    user_id: int
    username: str
    refresh_token: str
    created_at: datetime
    last_accessed: datetime
    expires_at: datetime
    user_agent: Optional[str] = None
    ip_address: Optional[str] = None
    is_active: bool = True

    def to_dict(self) -> dict:
        """Convert session to dictionary for Redis storage."""
        return {
            "user_id": self.user_id,
            "username": self.username,
            "refresh_token": self.refresh_token,
            "created_at": self.created_at.isoformat(),
            "last_accessed": self.last_accessed.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "user_agent": self.user_agent,
            "ip_address": self.ip_address,
            "is_active": self.is_active,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Session":
        """Create session from dictionary."""
        return cls(
            user_id=data["user_id"],
            username=data["username"],
            refresh_token=data["refresh_token"],
            created_at=datetime.fromisoformat(data["created_at"]),
            last_accessed=datetime.fromisoformat(data["last_accessed"]),
            expires_at=datetime.fromisoformat(data["expires_at"]),
            user_agent=data.get("user_agent"),
            ip_address=data.get("ip_address"),
            is_active=data.get("is_active", True),
        )


class SessionManager:
    """
    Manages user sessions with Redis backend for refresh token storage,
    blacklisting, and session cleanup.
    """

    def __init__(self, redis_url: str = REDIS_URL):
        """Initialize session manager with Redis connection."""
        try:
            self.redis = Redis.from_url(redis_url, decode_responses=True)
            # Test connection
            self.redis.ping()
            logger.info("Connected to Redis for session management")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            # Fallback to in-memory storage (not recommended for production)
            self.redis = None
            self._memory_sessions: Dict[str, Session] = {}
            self._blacklisted_tokens: Set[str] = set()
            logger.warning(
                "Using in-memory session storage - not suitable for production"
            )

    def _get_session_key(self, session_id: str) -> str:
        """Generate Redis key for session storage."""
        return f"session:{session_id}"

    def _get_user_sessions_key(self, user_id: int) -> str:
        """Generate Redis key for user sessions list."""
        return f"user_sessions:{user_id}"

    def _get_blacklist_key(self, token: str) -> str:
        """Generate Redis key for blacklisted tokens."""
        return f"blacklist:{token}"

    def create_session(
        self,
        user_id: int,
        username: str,
        refresh_token: str,
        expires_at: datetime,
        user_agent: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> str:
        """
        Create a new user session.

        Args:
            user_id: User ID
            username: Username
            refresh_token: Refresh token
            expires_at: Session expiration time
            user_agent: User agent string
            ip_address: Client IP address

        Returns:
            Session ID
        """
        session_id = f"{user_id}:{int(time.time() * 1000)}"
        session = Session(
            user_id=user_id,
            username=username,
            refresh_token=refresh_token,
            created_at=datetime.utcnow(),
            last_accessed=datetime.utcnow(),
            expires_at=expires_at,
            user_agent=user_agent,
            ip_address=ip_address,
        )

        try:
            if self.redis:
                # Store session in Redis
                session_key = self._get_session_key(session_id)
                user_sessions_key = self._get_user_sessions_key(user_id)

                # Store session data
                self.redis.hset(session_key, mapping=session.to_dict())

                # Set expiration
                ttl = int((expires_at - datetime.utcnow()).total_seconds())
                self.redis.expire(session_key, ttl)

                # Add to user sessions list
                self.redis.sadd(user_sessions_key, session_id)
                self.redis.expire(user_sessions_key, ttl)

            else:
                # Fallback to memory storage
                self._memory_sessions[session_id] = session

            logger.info(f"Created session {session_id} for user {username}")
            return session_id

        except Exception as e:
            logger.error(f"Failed to create session: {e}")
            raise

    def get_session(self, session_id: str) -> Optional[Session]:
        """
        Retrieve session by ID.

        Args:
            session_id: Session ID

        Returns:
            Session object or None if not found/expired
        """
        try:
            if self.redis:
                session_key = self._get_session_key(session_id)
                session_data = self.redis.hgetall(session_key)

                if not session_data:
                    return None

                session = Session.from_dict(session_data)

                # Check if session is expired
                if session.expires_at < datetime.utcnow():
                    self.revoke_session(session_id)
                    return None

                # Update last accessed time
                session.last_accessed = datetime.utcnow()
                self.redis.hset(
                    session_key, "last_accessed", session.last_accessed.isoformat()
                )

                return session

            else:
                # Fallback to memory storage
                session = self._memory_sessions.get(session_id)
                if session and session.expires_at > datetime.utcnow():
                    session.last_accessed = datetime.utcnow()
                    return session
                elif session:
                    # Remove expired session
                    del self._memory_sessions[session_id]

                return None

        except Exception as e:
            logger.error(f"Failed to get session {session_id}: {e}")
            return None

    def get_session_by_refresh_token(self, refresh_token: str) -> Optional[Session]:
        """
        Find session by refresh token.

        Args:
            refresh_token: Refresh token

        Returns:
            Session object or None if not found
        """
        try:
            if self.redis:
                # This is inefficient for large numbers of sessions
                # In production, consider using a separate token->session mapping
                cursor = 0
                while True:
                    cursor, keys = self.redis.scan(cursor, match="session:*", count=100)
                    for key in keys:
                        session_data = self.redis.hgetall(key)
                        if session_data.get("refresh_token") == refresh_token:
                            return Session.from_dict(session_data)
                    if cursor == 0:
                        break
                return None

            else:
                # Memory storage search
                for session in self._memory_sessions.values():
                    if session.refresh_token == refresh_token:
                        return session
                return None

        except Exception as e:
            logger.error(f"Failed to find session by refresh token: {e}")
            return None

    def revoke_session(self, session_id: str) -> bool:
        """
        Revoke a specific session.

        Args:
            session_id: Session ID to revoke

        Returns:
            True if session was revoked, False otherwise
        """
        try:
            session = self.get_session(session_id)
            if not session:
                return False

            if self.redis:
                session_key = self._get_session_key(session_id)
                user_sessions_key = self._get_user_sessions_key(session.user_id)

                # Remove session
                self.redis.delete(session_key)

                # Remove from user sessions list
                self.redis.srem(user_sessions_key, session_id)

                # Blacklist the refresh token
                self.blacklist_token(session.refresh_token)

            else:
                # Memory storage
                if session_id in self._memory_sessions:
                    session = self._memory_sessions[session_id]
                    del self._memory_sessions[session_id]
                    self._blacklisted_tokens.add(session.refresh_token)

            logger.info(f"Revoked session {session_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to revoke session {session_id}: {e}")
            return False

    def revoke_all_user_sessions(self, user_id: int) -> int:
        """
        Revoke all sessions for a specific user.

        Args:
            user_id: User ID

        Returns:
            Number of sessions revoked
        """
        try:
            revoked_count = 0

            if self.redis:
                user_sessions_key = self._get_user_sessions_key(user_id)
                session_ids = self.redis.smembers(user_sessions_key)

                for session_id in session_ids:
                    if self.revoke_session(session_id):
                        revoked_count += 1

                # Clean up user sessions list
                self.redis.delete(user_sessions_key)

            else:
                # Memory storage
                sessions_to_revoke = [
                    sid
                    for sid, session in self._memory_sessions.items()
                    if session.user_id == user_id
                ]

                for session_id in sessions_to_revoke:
                    if self.revoke_session(session_id):
                        revoked_count += 1

            logger.info(f"Revoked {revoked_count} sessions for user {user_id}")
            return revoked_count

        except Exception as e:
            logger.error(f"Failed to revoke user sessions for user {user_id}: {e}")
            return 0

    def blacklist_token(
        self, token: str, expires_at: Optional[datetime] = None
    ) -> bool:
        """
        Add token to blacklist.

        Args:
            token: Token to blacklist
            expires_at: When the blacklist entry should expire

        Returns:
            True if token was blacklisted, False otherwise
        """
        try:
            if self.redis:
                blacklist_key = self._get_blacklist_key(token)
                self.redis.set(blacklist_key, "1")

                if expires_at:
                    ttl = int((expires_at - datetime.utcnow()).total_seconds())
                    if ttl > 0:
                        self.redis.expire(blacklist_key, ttl)

            else:
                self._blacklisted_tokens.add(token)

            return True

        except Exception as e:
            logger.error(f"Failed to blacklist token: {e}")
            return False

    def is_token_blacklisted(self, token: str) -> bool:
        """
        Check if token is blacklisted.

        Args:
            token: Token to check

        Returns:
            True if token is blacklisted, False otherwise
        """
        try:
            if self.redis:
                blacklist_key = self._get_blacklist_key(token)
                return self.redis.exists(blacklist_key) > 0
            else:
                return token in self._blacklisted_tokens

        except Exception as e:
            logger.error(f"Failed to check token blacklist: {e}")
            return False

    def cleanup_expired_sessions(self) -> int:
        """
        Clean up expired sessions and blacklisted tokens.

        Returns:
            Number of sessions cleaned up
        """
        try:
            cleaned_count = 0
            current_time = datetime.utcnow()

            if self.redis:
                # Redis handles expiration automatically, but we can clean up orphaned data
                cursor = 0
                while True:
                    cursor, keys = self.redis.scan(cursor, match="session:*", count=100)
                    for key in keys:
                        session_data = self.redis.hgetall(key)
                        if session_data:
                            expires_at = datetime.fromisoformat(
                                session_data["expires_at"]
                            )
                            if expires_at < current_time:
                                self.redis.delete(key)
                                cleaned_count += 1
                    if cursor == 0:
                        break

            else:
                # Memory storage cleanup
                expired_sessions = [
                    sid
                    for sid, session in self._memory_sessions.items()
                    if session.expires_at < current_time
                ]

                for session_id in expired_sessions:
                    del self._memory_sessions[session_id]
                    cleaned_count += 1

            if cleaned_count > 0:
                logger.info(f"Cleaned up {cleaned_count} expired sessions")

            return cleaned_count

        except Exception as e:
            logger.error(f"Failed to cleanup expired sessions: {e}")
            return 0

    def get_user_session_count(self, user_id: int) -> int:
        """
        Get number of active sessions for a user.

        Args:
            user_id: User ID

        Returns:
            Number of active sessions
        """
        try:
            if self.redis:
                user_sessions_key = self._get_user_sessions_key(user_id)
                return self.redis.scard(user_sessions_key)
            else:
                return sum(
                    1
                    for session in self._memory_sessions.values()
                    if session.user_id == user_id
                    and session.expires_at > datetime.utcnow()
                )

        except Exception as e:
            logger.error(f"Failed to get session count for user {user_id}: {e}")
            return 0


# Global session manager instance
session_manager = SessionManager()
