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


# Role groups for `RoleByMethodPermission.allowed_roles`.
OWNER = (User.Roles.SUPERADMIN,)
OFFICE = (User.Roles.SUPERADMIN, User.Roles.ADMIN)
CLINICAL = (User.Roles.SUPERADMIN, User.Roles.DOCTOR)
STAFF = (User.Roles.SUPERADMIN, User.Roles.ADMIN, User.Roles.DOCTOR)


class RoleByMethodPermission(BasePermission):
    """
    Roles allowed per HTTP method, read from the view's `allowed_roles`
    (`{"GET": STAFF, "POST": OFFICE}`). A method that is not listed is refused.
    """

    message = ClinicRolePermission.message

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated and user.is_active):
            return False
        roles = getattr(view, "allowed_roles", {}).get(request.method, ())
        return user.role in roles and get_clinic(user) is not None


def own_doctor(user):
    """The doctor a user's view is narrowed to: themselves if a doctor, else nobody."""
    return user if user.role == User.Roles.DOCTOR else None


def limit_to_clinic(serializer):
    """
    Narrows a serializer's related-object fields to the requesting user's
    clinic, so an id from another clinic reads as "does not exist". A doctor
    may name only themselves as the doctor. `clinic` itself is left alone:
    services always save the clinic from the user, never from the request.
    """
    request = serializer.context.get("request")
    if request is None:
        return
    clinic = get_clinic(request.user)
    doctor = own_doctor(request.user)
    for name, field in serializer.fields.items():
        queryset = getattr(field, "queryset", None)
        if queryset is None or name == "clinic":
            continue
        if queryset.model is User:
            queryset = queryset.filter(clinic=clinic)
            if name == "doctor" and doctor is not None:
                queryset = queryset.filter(id=doctor.id)
        elif any(model_field.name == "clinic" for model_field in queryset.model._meta.fields):
            queryset = queryset.filter(clinic=clinic)
        field.queryset = queryset
