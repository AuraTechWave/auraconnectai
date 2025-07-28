# backend/modules/customers/auth/customer_auth.py

from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import jwt
from passlib.context import CryptContext
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
import secrets
import logging

from backend.core.database import get_db
from backend.core.config import settings
from ..models.customer_models import Customer
from ..services.customer_service import CustomerService


logger = logging.getLogger(__name__)

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT settings
CUSTOMER_JWT_SECRET = getattr(settings, 'CUSTOMER_JWT_SECRET', secrets.token_urlsafe(32))
CUSTOMER_JWT_ALGORITHM = "HS256"
CUSTOMER_ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 days

# HTTP Bearer token scheme
security = HTTPBearer()


class CustomerTokenData:
    """Customer token data structure"""
    def __init__(self, customer_id: int, email: str, tier: str, tenant_id: Optional[int] = None):
        self.customer_id = customer_id
        self.email = email
        self.tier = tier
        self.tenant_id = tenant_id


def verify_customer_password(plain_password: str, hashed_password: str) -> bool:
    """Verify customer password"""
    return pwd_context.verify(plain_password, hashed_password)


def get_customer_password_hash(password: str) -> str:
    """Hash customer password"""
    return pwd_context.hash(password)


def create_customer_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Create JWT access token for customer"""
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=CUSTOMER_ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({
        "exp": expire,
        "iat": datetime.utcnow(),
        "type": "customer_access"
    })
    
    encoded_jwt = jwt.encode(to_encode, CUSTOMER_JWT_SECRET, algorithm=CUSTOMER_JWT_ALGORITHM)
    return encoded_jwt


def verify_customer_token(token: str) -> Optional[CustomerTokenData]:
    """Verify and decode customer JWT token"""
    try:
        payload = jwt.decode(token, CUSTOMER_JWT_SECRET, algorithms=[CUSTOMER_JWT_ALGORITHM])
        
        # Verify token type
        if payload.get("type") != "customer_access":
            return None
        
        customer_id: int = payload.get("customer_id")
        email: str = payload.get("email")
        tier: str = payload.get("tier")
        tenant_id: Optional[int] = payload.get("tenant_id")
        
        if customer_id is None or email is None:
            return None
        
        return CustomerTokenData(
            customer_id=customer_id,
            email=email,
            tier=tier,
            tenant_id=tenant_id
        )
    except jwt.PyJWTError as e:
        logger.warning(f"JWT token verification failed: {str(e)}")
        return None


async def get_current_customer(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> Customer:
    """Get current authenticated customer"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate customer credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        token = credentials.credentials
        token_data = verify_customer_token(token)
        
        if token_data is None:
            raise credentials_exception
        
        customer_service = CustomerService(db)
        customer = customer_service.get_customer(token_data.customer_id)
        
        if customer is None:
            raise credentials_exception
        
        # Check if customer is active
        if customer.status != "active":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Customer account is not active"
            )
        
        return customer
        
    except Exception as e:
        logger.error(f"Customer authentication error: {str(e)}")
        raise credentials_exception


async def get_current_active_customer(
    current_customer: Customer = Depends(get_current_customer)
) -> Customer:
    """Get current active customer (additional check)"""
    if current_customer.status != "active":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Customer account is not active"
        )
    return current_customer


class CustomerAuthService:
    """Enhanced customer authentication service with JWT support"""
    
    def __init__(self, db: Session):
        self.db = db
        self.customer_service = CustomerService(db)
    
    def authenticate_customer(self, email: str, password: str) -> Optional[Customer]:
        """Authenticate customer with email and password"""
        customer = self.customer_service.get_customer_by_email(email)
        
        if not customer or not customer.password_hash:
            return None
        
        if not verify_customer_password(password, customer.password_hash):
            return None
        
        # Update login info
        customer.last_login = datetime.utcnow()
        customer.login_count += 1
        self.db.commit()
        
        return customer
    
    def register_customer(self, customer_data) -> Customer:
        """Register new customer with password hashing"""
        if not customer_data.password:
            raise ValueError("Password is required for registration")
        
        # Hash the password before creating customer
        hashed_password = get_customer_password_hash(customer_data.password)
        customer_data_dict = customer_data.model_dump()
        customer_data_dict['password'] = hashed_password
        
        # Create customer through service
        return self.customer_service.create_customer(customer_data)
    
    def create_access_token(self, customer: Customer) -> Dict[str, Any]:
        """Create access token for customer"""
        token_data = {
            "customer_id": customer.id,
            "email": customer.email,
            "tier": customer.tier.value,
            "full_name": customer.full_name
        }
        
        access_token = create_customer_access_token(token_data)
        
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "expires_in": CUSTOMER_ACCESS_TOKEN_EXPIRE_MINUTES * 60,  # in seconds
            "customer": {
                "id": customer.id,
                "email": customer.email,
                "full_name": customer.full_name,
                "tier": customer.tier.value,
                "loyalty_points": customer.loyalty_points
            }
        }
    
    def refresh_token(self, customer: Customer) -> Dict[str, Any]:
        """Refresh access token for customer"""
        return self.create_access_token(customer)
    
    def revoke_token(self, customer_id: int):
        """Revoke customer tokens (implement token blacklist if needed)"""
        # In a production system, you might want to implement a token blacklist
        # For now, we'll just log the revocation
        logger.info(f"Token revoked for customer {customer_id}")
        
        # You could implement token blacklist in Redis:
        # redis_client.sadd(f"revoked_tokens:customer:{customer_id}", token_jti)
        pass
    
    def change_password(self, customer_id: int, old_password: str, new_password: str) -> bool:
        """Change customer password"""
        customer = self.customer_service.get_customer(customer_id)
        if not customer:
            raise ValueError("Customer not found")
        
        # Verify old password
        if not customer.password_hash or not verify_customer_password(old_password, customer.password_hash):
            raise ValueError("Invalid current password")
        
        # Hash new password
        customer.password_hash = get_customer_password_hash(new_password)
        self.db.commit()
        
        logger.info(f"Password changed for customer {customer_id}")
        return True
    
    def reset_password_request(self, email: str) -> Optional[str]:
        """Request password reset (generate reset token)"""
        customer = self.customer_service.get_customer_by_email(email)
        if not customer:
            # Don't reveal if email exists
            return None
        
        # Generate reset token
        reset_token_data = {
            "customer_id": customer.id,
            "email": customer.email,
            "type": "password_reset"
        }
        
        reset_token = create_customer_access_token(
            reset_token_data,
            expires_delta=timedelta(hours=1)  # Reset token expires in 1 hour
        )
        
        # In production, you would:
        # 1. Store the reset token in database with expiration
        # 2. Send email with reset link
        
        logger.info(f"Password reset requested for customer {customer.id}")
        return reset_token
    
    def reset_password(self, reset_token: str, new_password: str) -> bool:
        """Reset customer password using reset token"""
        try:
            payload = jwt.decode(reset_token, CUSTOMER_JWT_SECRET, algorithms=[CUSTOMER_JWT_ALGORITHM])
            
            if payload.get("type") != "password_reset":
                raise ValueError("Invalid reset token type")
            
            customer_id = payload.get("customer_id")
            if not customer_id:
                raise ValueError("Invalid reset token")
            
            customer = self.customer_service.get_customer(customer_id)
            if not customer:
                raise ValueError("Customer not found")
            
            # Set new password
            customer.password_hash = get_customer_password_hash(new_password)
            self.db.commit()
            
            logger.info(f"Password reset completed for customer {customer_id}")
            return True
            
        except jwt.PyJWTError:
            raise ValueError("Invalid or expired reset token")


# Optional: Customer role-based access control
def require_customer_tier(required_tier: str):
    """Decorator to require specific customer tier"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            current_customer = kwargs.get('current_customer')
            if not current_customer:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required"
                )
            
            tier_hierarchy = {
                "bronze": 1,
                "silver": 2,
                "gold": 3,
                "platinum": 4,
                "vip": 5
            }
            
            customer_tier_level = tier_hierarchy.get(current_customer.tier.value.lower(), 0)
            required_tier_level = tier_hierarchy.get(required_tier.lower(), 999)
            
            if customer_tier_level < required_tier_level:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Customer tier '{required_tier}' or higher required"
                )
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator