"""
Distributed session management using Redis.

Provides:
- Session storage across multiple app instances
- Session expiration and renewal
- Concurrent access handling
- Session data encryption
"""

import json
import secrets
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from cryptography.fernet import Fernet
import redis.asyncio as redis

from .config import get_settings
from .redis_cache import redis_cache

logger = logging.getLogger(__name__)
settings = get_settings()


class DistributedSessionManager:
    """
    Manages user sessions in a distributed environment using Redis.
    """
    
    def __init__(
        self,
        redis_client: Optional[redis.Redis] = None,
        session_prefix: str = "session",
        default_ttl: int = 1800,  # 30 minutes
        encryption_key: Optional[bytes] = None
    ):
        self.redis_client = redis_client or redis_cache.redis_client
        self.session_prefix = session_prefix
        self.default_ttl = default_ttl
        
        # Initialize encryption
        if encryption_key:
            self.cipher = Fernet(encryption_key)
        else:
            # Generate a key from settings or use a default (NOT for production)
            key = settings.session_encryption_key if hasattr(settings, 'session_encryption_key') else None
            if key:
                self.cipher = Fernet(key.encode() if isinstance(key, str) else key)
            else:
                # WARNING: This generates a random key - sessions won't survive restarts
                logger.warning("No session encryption key provided - generating random key")
                self.cipher = Fernet(Fernet.generate_key())
                
    def _make_session_key(self, session_id: str) -> str:
        """Generate Redis key for session."""
        return f"{self.session_prefix}:{session_id}"
        
    def _encrypt_data(self, data: Dict[str, Any]) -> str:
        """Encrypt session data."""
        json_data = json.dumps(data)
        encrypted = self.cipher.encrypt(json_data.encode())
        return encrypted.decode()
        
    def _decrypt_data(self, encrypted_data: str) -> Dict[str, Any]:
        """Decrypt session data."""
        try:
            decrypted = self.cipher.decrypt(encrypted_data.encode())
            return json.loads(decrypted.decode())
        except Exception as e:
            logger.error(f"Failed to decrypt session data: {e}")
            return {}
            
    async def create_session(
        self,
        user_id: int,
        data: Optional[Dict[str, Any]] = None,
        ttl: Optional[int] = None
    ) -> str:
        """Create a new session."""
        # Generate secure session ID
        session_id = secrets.token_urlsafe(32)
        
        # Prepare session data
        session_data = {
            "user_id": user_id,
            "created_at": datetime.utcnow().isoformat(),
            "last_accessed": datetime.utcnow().isoformat(),
            "data": data or {}
        }
        
        # Encrypt and store
        encrypted_data = self._encrypt_data(session_data)
        key = self._make_session_key(session_id)
        
        ttl = ttl or self.default_ttl
        
        try:
            if self.redis_client:
                await self.redis_client.setex(key, ttl, encrypted_data)
                
                # Also maintain a user's session index
                user_sessions_key = f"{self.session_prefix}:user:{user_id}"
                await self.redis_client.sadd(user_sessions_key, session_id)
                await self.redis_client.expire(user_sessions_key, ttl)
                
                logger.debug(f"Created session {session_id} for user {user_id}")
                return session_id
            else:
                logger.error("Redis client not available for session creation")
                return session_id  # Return ID anyway for fallback handling
                
        except Exception as e:
            logger.error(f"Failed to create session: {e}")
            raise
            
    async def get_session(
        self,
        session_id: str,
        extend_ttl: bool = True
    ) -> Optional[Dict[str, Any]]:
        """Get session data."""
        if not self.redis_client:
            return None
            
        key = self._make_session_key(session_id)
        
        try:
            encrypted_data = await self.redis_client.get(key)
            if not encrypted_data:
                return None
                
            # Decrypt session data
            session_data = self._decrypt_data(encrypted_data)
            
            if extend_ttl and session_data:
                # Update last accessed time
                session_data["last_accessed"] = datetime.utcnow().isoformat()
                
                # Re-encrypt and update with extended TTL
                encrypted_data = self._encrypt_data(session_data)
                await self.redis_client.setex(
                    key,
                    self.default_ttl,
                    encrypted_data
                )
                
            return session_data
            
        except Exception as e:
            logger.error(f"Failed to get session {session_id}: {e}")
            return None
            
    async def update_session(
        self,
        session_id: str,
        data: Dict[str, Any],
        merge: bool = True
    ) -> bool:
        """Update session data."""
        if not self.redis_client:
            return False
            
        try:
            # Get existing session
            session_data = await self.get_session(session_id, extend_ttl=False)
            if not session_data:
                return False
                
            # Update data
            if merge:
                session_data["data"].update(data)
            else:
                session_data["data"] = data
                
            session_data["last_accessed"] = datetime.utcnow().isoformat()
            
            # Re-encrypt and save
            encrypted_data = self._encrypt_data(session_data)
            key = self._make_session_key(session_id)
            
            # Get remaining TTL
            ttl = await self.redis_client.ttl(key)
            if ttl <= 0:
                ttl = self.default_ttl
                
            await self.redis_client.setex(key, ttl, encrypted_data)
            return True
            
        except Exception as e:
            logger.error(f"Failed to update session {session_id}: {e}")
            return False
            
    async def delete_session(self, session_id: str) -> bool:
        """Delete a session."""
        if not self.redis_client:
            return False
            
        try:
            # Get session data first to find user ID
            session_data = await self.get_session(session_id, extend_ttl=False)
            
            # Delete the session
            key = self._make_session_key(session_id)
            result = await self.redis_client.delete(key)
            
            # Remove from user's session index
            if session_data and "user_id" in session_data:
                user_sessions_key = f"{self.session_prefix}:user:{session_data['user_id']}"
                await self.redis_client.srem(user_sessions_key, session_id)
                
            return bool(result)
            
        except Exception as e:
            logger.error(f"Failed to delete session {session_id}: {e}")
            return False
            
    async def get_user_sessions(self, user_id: int) -> List[str]:
        """Get all active sessions for a user."""
        if not self.redis_client:
            return []
            
        try:
            user_sessions_key = f"{self.session_prefix}:user:{user_id}"
            session_ids = await self.redis_client.smembers(user_sessions_key)
            
            # Verify sessions still exist
            valid_sessions = []
            for session_id in session_ids:
                if await self.redis_client.exists(self._make_session_key(session_id)):
                    valid_sessions.append(session_id)
                else:
                    # Clean up invalid reference
                    await self.redis_client.srem(user_sessions_key, session_id)
                    
            return valid_sessions
            
        except Exception as e:
            logger.error(f"Failed to get user sessions for {user_id}: {e}")
            return []
            
    async def delete_user_sessions(self, user_id: int) -> int:
        """Delete all sessions for a user."""
        deleted_count = 0
        
        try:
            session_ids = await self.get_user_sessions(user_id)
            
            for session_id in session_ids:
                if await self.delete_session(session_id):
                    deleted_count += 1
                    
            # Clean up user session index
            user_sessions_key = f"{self.session_prefix}:user:{user_id}"
            await self.redis_client.delete(user_sessions_key)
            
            logger.info(f"Deleted {deleted_count} sessions for user {user_id}")
            return deleted_count
            
        except Exception as e:
            logger.error(f"Failed to delete user sessions for {user_id}: {e}")
            return deleted_count
            
    async def cleanup_expired_sessions(self) -> int:
        """Clean up expired sessions (called by background task)."""
        if not self.redis_client:
            return 0
            
        cleaned_count = 0
        
        try:
            # Get all session keys
            cursor = 0
            pattern = f"{self.session_prefix}:*"
            
            while True:
                cursor, keys = await self.redis_client.scan(
                    cursor,
                    match=pattern,
                    count=100
                )
                
                for key in keys:
                    # Skip user index keys
                    if ":user:" in key:
                        continue
                        
                    # Check if key has TTL (non-expired keys have TTL > 0)
                    ttl = await self.redis_client.ttl(key)
                    if ttl == -2:  # Key doesn't exist
                        cleaned_count += 1
                    elif ttl == -1:  # Key exists but has no TTL (shouldn't happen)
                        # Set a TTL to clean it up later
                        await self.redis_client.expire(key, 3600)
                        
                if cursor == 0:
                    break
                    
            return cleaned_count
            
        except Exception as e:
            logger.error(f"Failed to cleanup expired sessions: {e}")
            return cleaned_count
            
    async def get_session_count(self) -> Dict[str, int]:
        """Get session statistics."""
        if not self.redis_client:
            return {"total": 0, "users": 0}
            
        try:
            # Count total sessions
            cursor = 0
            session_count = 0
            user_count = 0
            pattern = f"{self.session_prefix}:*"
            
            while True:
                cursor, keys = await self.redis_client.scan(
                    cursor,
                    match=pattern,
                    count=100
                )
                
                for key in keys:
                    if ":user:" in key:
                        user_count += 1
                    else:
                        session_count += 1
                        
                if cursor == 0:
                    break
                    
            return {
                "total": session_count,
                "users": user_count,
                "average_per_user": session_count / user_count if user_count > 0 else 0
            }
            
        except Exception as e:
            logger.error(f"Failed to get session count: {e}")
            return {"total": 0, "users": 0}


# Global session manager instance
session_manager = DistributedSessionManager()


# FastAPI dependency for session handling
async def get_session_data(
    session_id: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """FastAPI dependency to get session data."""
    if not session_id:
        return None
        
    return await session_manager.get_session(session_id)


# Export public interface
__all__ = ["session_manager", "get_session_data", "DistributedSessionManager"]