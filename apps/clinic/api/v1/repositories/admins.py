from apps.core.exceptions import ObjectNotFoundException
from apps.authentication.models import User

class AdminRepository:
    def get_admins(self,clinic_id):
        admins = User.objects.filter(role=User.Roles.ADMIN,clinic=clinic_id)
        return admins

    def get_admin(self,user_id,clinic_id):
        admin = User.objects.filter(id=user_id,role=User.Roles.ADMIN,clinic=clinic_id).first()
        if not admin:
            raise ObjectNotFoundException(
                message="Admin not found",
                message_key="admin_not_found",
            )
        return admin



