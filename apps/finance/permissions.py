from apps.authentication.models import User
from apps.core.permissions import ClinicRolePermission


class CanRecordPayments(ClinicRolePermission):
    # Taking a patient's money is front-desk work too; reading the reports is
    # not. A doctor may only take payment for their own treatments, which the
    # payment serializer enforces.
    roles = (User.Roles.SUPERADMIN, User.Roles.ADMIN, User.Roles.DOCTOR)
