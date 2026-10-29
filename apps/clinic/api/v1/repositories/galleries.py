from apps.core.exceptions import ObjectNotFoundException
from apps.authentication.models import Gallery, User
from apps.clinic.api.v1.repositories.patients import doctor_patients

class GalleryRepository:
    def get_galleries(self,clinic_id,doctor=None):
        gallery = Gallery.objects.filter(clinic=clinic_id)
        if doctor is not None:
            patients = doctor_patients(User.objects.filter(clinic=clinic_id), doctor)
            gallery = gallery.filter(user__in=patients)
        return gallery

    def get_gallery(self,gallery_id,clinic_id,doctor=None):
        gallery = self.get_galleries(clinic_id, doctor).filter(id=gallery_id).first()
        if not gallery:
            raise ObjectNotFoundException(
                message="Gallery not found",
                message_key="gallery_not_found",
            )
        return gallery
