# backend/tests/factories/auth.py

import factory
from factory import Faker, Sequence, LazyFunction, LazyAttribute
from .base import BaseFactory
from core.models import User, Role


class RoleFactory(BaseFactory):
    """Factory for creating roles."""
    
    class Meta:
        model = Role
    
    id = Sequence(lambda n: n + 1)
    name = factory.Iterator(["staff", "manager", "admin", "kitchen", "cashier"])
    description = LazyAttribute(lambda obj: f"{obj.name.title()} role for testing")


class UserFactory(BaseFactory):
    """Factory for creating users."""
    
    class Meta:
        model = User
    
    id = Sequence(lambda n: n + 1)
    username = Faker("user_name")
    email = Faker("email")
    is_active = True
    
    @factory.post_generation
    def roles(self, create, extracted, **kwargs):
        if not create:
            return
        
        if extracted:
            # Use provided roles
            for role in extracted:
                self.roles.append(role)
        else:
            # Default to staff role
            default_role = RoleFactory(name="staff")
            self.roles.append(default_role)