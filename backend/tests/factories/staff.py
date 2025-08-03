# backend/tests/factories/staff.py

import factory
from factory import Faker, Sequence, LazyFunction, LazyAttribute, SubFactory
import random
from datetime import date, timedelta
from .base import BaseFactory
from .auth import UserFactory
from modules.staff.models.staff_models import StaffMember, Department


class DepartmentFactory(BaseFactory):
    """Factory for creating departments."""
    
    class Meta:
        model = Department
    
    id = Sequence(lambda n: n + 1)
    name = factory.Iterator(["Kitchen", "Service", "Management", "Bar", "Cleaning"])
    description = LazyAttribute(lambda obj: f"{obj.name} department")
    is_active = True


class StaffMemberFactory(BaseFactory):
    """Factory for creating staff members."""
    
    class Meta:
        model = StaffMember
    
    id = Sequence(lambda n: n + 1)
    
    # User relationship
    user = SubFactory(UserFactory)
    user_id = LazyAttribute(lambda obj: obj.user.id)
    
    # Personal info
    employee_id = LazyFunction(lambda: f"EMP{random.randint(1000, 9999)}")
    first_name = Faker("first_name")
    last_name = Faker("last_name")
    email = LazyAttribute(lambda obj: obj.user.email if obj.user else Faker("email").generate())
    phone = Faker("phone_number")
    
    # Employment details
    department = SubFactory(DepartmentFactory)
    department_id = LazyAttribute(lambda obj: obj.department.id)
    position = factory.Iterator(["Chef", "Server", "Manager", "Bartender", "Host"])
    
    # Dates
    hire_date = LazyFunction(lambda: date.today() - timedelta(days=random.randint(30, 365)))
    birth_date = LazyFunction(lambda: date.today() - timedelta(days=random.randint(7300, 18250)))  # 20-50 years old
    
    # Compensation
    hourly_rate = LazyFunction(lambda: round(random.uniform(15.0, 35.0), 2))
    salary = None  # Use hourly by default
    
    # Status
    is_active = True
    
    # Emergency contact
    emergency_contact_name = Faker("name")
    emergency_contact_phone = Faker("phone_number")
    
    # Address
    address = Faker("street_address")
    city = Faker("city")
    state = Faker("state_abbr")
    zip_code = Faker("zipcode")