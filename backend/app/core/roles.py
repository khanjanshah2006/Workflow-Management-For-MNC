"""Role names and role groups shared across features.

Each constant is the plain string value of the matching ``UserType`` member,
so the groups can be passed straight to ``require_role`` and the other RBAC helpers, which
compare role names as strings.
"""
from app.models.enums import UserType

EMPLOYEE = UserType.EMPLOYEE.value
TEAM_LEAD = UserType.TEAM_LEAD.value
PM = UserType.PM.value
HR = UserType.HR.value
CLIENT = UserType.CLIENT.value
ADMIN = UserType.ADMIN.value
IT_SUPPORT = UserType.IT_SUPPORT.value
SYSTEM_ADMIN = UserType.SYSTEM_ADMIN.value
MNC_EXECUTIVE = UserType.MNC_EXECUTIVE.value

# Every role that belongs to the company (everyone except external clients).
INTERNAL = (EMPLOYEE, TEAM_LEAD, PM, HR, ADMIN, IT_SUPPORT, SYSTEM_ADMIN, MNC_EXECUTIVE)

# Roles that administer the platform itself.
PLATFORM_ADMINS = (ADMIN, SYSTEM_ADMIN)

# Roles that work the IT support queue.
IT_STAFF = (IT_SUPPORT, SYSTEM_ADMIN)
