from rest_framework.permissions import BasePermission

from apps.authentication.models import User


def get_clinic(user):
    """
    The tenant a user acts for. The clinic owner (superadmin) is the clinic
    itself; admins and doctors belong to one through `User.clinic`.
    """
    if user.role == User.Roles.SUPERADMIN:
        return user
    return user.clinic


class ClinicRolePermission(BasePermission):
    """Allows only the listed roles, and only users that belong to a clinic."""

    roles = ()
    message = "You do not have permission to perform this action."

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated and user.is_active):
            return False
        return user.role in self.roles and get_clinic(user) is not None


class IsClinicOwner(ClinicRolePermission):
    roles = (User.Roles.SUPERADMIN,)


class IsClinicDoctor(ClinicRolePermission):
    roles = (User.Roles.DOCTOR,)
