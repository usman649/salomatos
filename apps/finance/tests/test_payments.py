from datetime import date, timedelta

from django.test import TestCase

from apps.clinic.models import Treatment
from apps.core.reporting import clinic_today
from apps.finance.models import Payment
from apps.finance.tests.factories import (
    client_for,
    make_admin,
    make_clinic,
    make_doctor,
    make_patient,
    make_treatment,
)

URL = "/api/v1/finance/payments/"


class PaymentTests(TestCase):
    def setUp(self):
        self.clinic = make_clinic()
        self.doctor = make_doctor(self.clinic)
        self.patient = make_patient(self.clinic, doctor=self.doctor)
        self.treatment = make_treatment(self.clinic, self.patient, self.doctor, cost=1_000_000, paid=200_000)
        self.owner = client_for(self.clinic)

    def pay(self, client=None, **overrides):
        body = {
            "treatment": self.treatment.id,
            "amount": 300_000,
            "method": "card",
            "date": "2026-02-01",
            **overrides,
        }
        return (client or self.owner).post(URL, body, format="json")

    def test_payment_raises_total_paid_and_keeps_who_and_for_whom(self):
        response = self.pay()

        self.assertEqual(response.status_code, 201, response.data)
        self.treatment.refresh_from_db()
        self.assertEqual(self.treatment.total_paid, 500_000)
        payment = Payment.objects.get()
        self.assertEqual(payment.patient, self.patient)
        self.assertEqual(payment.doctor, self.doctor)
        self.assertEqual(payment.created_by, self.clinic)
        self.assertEqual(response.data["patient"], self.patient.full_name)
        self.assertFalse(response.data["is_void"])

    def test_payment_cannot_exceed_what_is_owed(self):
        response = self.pay(amount=800_001)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["message_key"], "payment_exceeds_debt")
        self.treatment.refresh_from_db()
        self.assertEqual(self.treatment.total_paid, 200_000)
        self.assertFalse(Payment.objects.exists())

    def test_payment_in_the_future_is_refused(self):
        response = self.pay(date=(clinic_today() + timedelta(days=1)).isoformat())

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["errors"]["date"], "future_date")

    def test_zero_and_unknown_method_are_refused(self):
        self.assertEqual(self.pay(amount=0).status_code, 400)
        self.assertEqual(self.pay(method="bitcoin").status_code, 400)

    def test_another_clinics_treatment_does_not_exist(self):
        other_clinic = make_clinic()
        other_doctor = make_doctor(other_clinic)
        other = make_treatment(other_clinic, make_patient(other_clinic), other_doctor, cost=500_000)

        response = self.pay(treatment=other.id)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["errors"]["treatment"], "does_not_exist")
        other.refresh_from_db()
        self.assertEqual(other.total_paid, 0)

    def test_void_lowers_total_paid_once(self):
        payment_id = self.pay().data["id"]
        url = f"{URL}{payment_id}/void/"

        response = self.owner.post(url, {"reason": "Wrong amount"}, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertTrue(response.data["is_void"])
        self.assertEqual(response.data["void_reason"], "Wrong amount")
        self.treatment.refresh_from_db()
        self.assertEqual(self.treatment.total_paid, 200_000)

        again = self.owner.post(url, {"reason": "Wrong amount"}, format="json")
        self.assertEqual(again.status_code, 400)
        self.assertEqual(again.data["message_key"], "already_voided")
        self.treatment.refresh_from_db()
        self.assertEqual(self.treatment.total_paid, 200_000)

    def test_void_needs_a_reason(self):
        payment_id = self.pay().data["id"]
        response = self.owner.post(f"{URL}{payment_id}/void/", {"reason": " "}, format="json")
        self.assertEqual(response.status_code, 400)

    def test_void_refuses_when_total_paid_was_lowered_by_hand(self):
        payment_id = self.pay().data["id"]
        Treatment.objects.filter(pk=self.treatment.pk).update(total_paid=100_000)

        response = self.owner.post(f"{URL}{payment_id}/void/", {"reason": "Mistake"}, format="json")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["message_key"], "paid_total_mismatch")
        self.assertFalse(Payment.objects.get().is_void)

    def test_deleting_a_treatment_keeps_its_payments(self):
        self.pay()
        self.treatment.delete()

        payment = Payment.objects.get()
        self.assertIsNone(payment.treatment)
        self.assertEqual(payment.patient, self.patient)

    def test_journal_lists_newest_first_and_filters(self):
        self.pay(amount=100_000, date="2026-02-01")
        self.pay(amount=100_000, date="2026-03-01", method="cash")

        response = self.owner.get(URL, {"from": "2026-02-15", "to": "2026-03-31"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["date"], "2026-03-01")
        by_method = self.owner.get(URL, {"method": "card"})
        self.assertEqual(by_method.data["count"], 1)
        self.assertEqual(self.owner.get(URL, {"patient_id": "x"}).status_code, 400)

    def test_journal_is_per_clinic(self):
        self.pay()
        other_owner = client_for(make_clinic())
        self.assertEqual(other_owner.get(URL).data["count"], 0)

    def test_only_the_owner_records_and_reads_payments(self):
        for user in (make_admin(self.clinic), self.doctor, self.patient):
            client = client_for(user)
            self.assertEqual(self.pay(client=client).status_code, 403, user.role)
            self.assertEqual(client.get(URL).status_code, 403, user.role)
        self.assertEqual(Payment.objects.count(), 0)
        self.treatment.refresh_from_db()
        self.assertEqual(self.treatment.total_paid, 200_000)

    def test_unauthenticated_is_refused(self):
        from rest_framework.test import APIClient

        self.assertEqual(APIClient().get(URL).status_code, 401)


class PaymentDateTests(TestCase):
    def test_today_is_allowed(self):
        clinic = make_clinic()
        doctor = make_doctor(clinic)
        treatment = make_treatment(clinic, make_patient(clinic), doctor, cost=10_000, start_date=date(2026, 1, 1))
        response = client_for(clinic).post(
            URL,
            {"treatment": treatment.id, "amount": 10_000, "method": "cash", "date": clinic_today().isoformat()},
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
