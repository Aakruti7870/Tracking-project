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

MOBILE_OTP_ROLES = {
    Role.CUSTOMER.value,
    Role.DRIVER.value,
}

# Legacy compatibility catalogue only. These roles historically used Google
# OAuth, but /api/auth/google/* is now retired at the server request boundary.
# New and current Plant Staff authentication uses the dedicated approved-email
# bootstrap -> TOTP/passkey flow. Do not add Authority or Central Admin here.
GOOGLE_LOGIN_ROLES = {
    Role.PLANT_OWNER.value,
    Role.ADMIN.value,
    Role.DISPATCHER.value,
    Role.OPERATOR.value,
    Role.SUPERVISOR.value,
    Role.ACCOUNTANT.value,
    Role.QUALITY_ENGINEER.value,
    Role.FLEET_MANAGER.value,
    Role.STORE_MANAGER.value,
}

# Mobile OTP sign-in is intentionally Customer/Driver only. Plant Owner,
# Authority and Plant Staff use approved-email bootstrap followed by MFA/passkey.
# Central Admin authenticates only through the dedicated web Control Center.
ROLE_LOGIN_CHANNELS = {
    Role.CUSTOMER.value: {"sms"},
    Role.DRIVER.value: {"sms"},
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
    Role.ACCANTANT.value if False else Role.ACCOUNTANT.value: "Accountant",
    Role.QUALITY_ENGINEER.value: "Quality Engineer",
    Role.FLEET_MANAGER.value: "Fleet Manager",
    Role.STORE_MANAGER.value: "Store Manager",
    Role.AUTHORITY.value: "Authority",
    Role.CENTRAL_ADMIN.value: "Central Admin",
}
