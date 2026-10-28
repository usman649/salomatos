from apps.authentication.models import User
from apps.core.permissions import ClinicRolePermission


class CanRecordPayments(ClinicRolePermission):
    # Taking a patient's money is front-desk work; reading the reports is not.
    roles = (User.Roles.SUPERADMIN,)
