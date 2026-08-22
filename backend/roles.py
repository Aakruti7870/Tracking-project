"""RBAC role catalogue for TrackMyRMC."""
from enum import Enum


class Role(str, Enum):
    CUSTOMER = "customer"
    DRIVER = "driver"
    PLANT_OWNER = "plant_owner"
    ADMIN = "admin"
    DISPATCHER = "dispatcher"
    OPERATOR = "operator"          # Plant Operator / Batcher
    SUPERVISOR = "supervisor"
    ACCOUNTANT = "accountant"
    QUALITY_ENGINEER = "quality_engineer"
    FLEET_MANAGER = "fleet_manager"
    STORE_MANAGER = "store_manager"
    AUTHORITY = "authority"
    CENTRAL_ADMIN = "central_admin"


ALL_ROLES = [r.value for r in Role]

# Which identifier channel is allowed to authenticate a given role.
# Customers & drivers -> mobile OTP; staff/authority/admin -> email OTP.
# Plant owner -> either.
ROLE_LOGIN_CHANNELS = {
    Role.CUSTOMER.value: {"sms"},
    Role.DRIVER.value: {"sms"},
    Role.PLANT_OWNER.value: {"sms", "email"},
    Role.ADMIN.value: {"email"},
    Role.DISPATCHER.value: {"email"},
    Role.OPERATOR.value: {"email"},
    Role.SUPERVISOR.value: {"email"},
    Role.ACCOUNTANT.value: {"email"},
    Role.QUALITY_ENGINEER.value: {"email"},
    Role.FLEET_MANAGER.value: {"email"},
    Role.STORE_MANAGER.value: {"email"},
    Role.AUTHORITY.value: {"email"},
    Role.CENTRAL_ADMIN.value: {"email"},
}

# Human-readable labels used by clients.
ROLE_LABELS = {
    Role.CUSTOMER.value: "Customer",
    Role.DRIVER.value: "Driver",
    Role.PLANT_OWNER.value: "Plant Owner",
    Role.ADMIN.value: "Admin",
    Role.DISPATCHER.value: "Dispatcher",
    Role.OPERATOR.value: "Plant Operator",
    Role.SUPERVISOR.value: "Supervisor",
    Role.ACCOUNTANT.value: "Accountant",
    Role.QUALITY_ENGINEER.value: "Quality Engineer",
    Role.FLEET_MANAGER.value: "Fleet Manager",
    Role.STORE_MANAGER.value: "Store Manager",
    Role.AUTHORITY.value: "Authority",
    Role.CENTRAL_ADMIN.value: "Central Admin",
}
