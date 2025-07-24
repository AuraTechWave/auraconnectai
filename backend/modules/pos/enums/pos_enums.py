from enum import Enum


class POSVendor(str, Enum):
    SQUARE = "square"
    TOAST = "toast"
    CLOVER = "clover"


class POSIntegrationStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class POSSyncStatus(str, Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    RETRY = "retry"


class POSSyncType(str, Enum):
    ORDER_PUSH = "order_push"
    ORDER_PULL = "order_pull"
    MENU_PUSH = "menu_push"
