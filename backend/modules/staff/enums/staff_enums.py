from enum import Enum


class StaffStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    ON_LEAVE = "on_leave"
    TERMINATED = "terminated"
    SUSPENDED = "suspended"


class StaffRole(str, Enum):
    MANAGER = "manager"
    SUPERVISOR = "supervisor"
    SERVER = "server"
    COOK = "cook"
    PREP_COOK = "prep_cook"
    DISHWASHER = "dishwasher"
    CASHIER = "cashier"
    HOST = "host"
    BARTENDER = "bartender"
    DELIVERY = "delivery"
    ADMIN = "admin"
