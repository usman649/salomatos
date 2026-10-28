from datetime import timedelta

from django.test import TestCase

from apps.core.reporting import clinic_today, format_month, shift_month
from apps.finance.models import Expense
from apps.finance.tests.factories import (
    client_for,
    make_admin,
    make_clinic,
    make_doctor,
    make_patient,
)

URL = "/api/v1/finance/expenses/"
RECURRING_URL = "/api/v1/finance/recurring-expenses/"


class ExpenseJournalTests(TestCase):
    def setUp(self):
        self.clinic = make_clinic()
        self.doctor = make_doctor(self.clinic)
        self.owner = client_for(self.clinic)

    def create(self, **overrides):
        body = {
            "date": "2026-03-05",
            "category": "rent",
            "amount": 12_000_000,
            "method": "transfer",
            "payee": "Landlord",
            "note": "",
            "doctor": None,
            **overrides,
        }
        return self.owner.post(URL, body, format="json")

    def test_create_records_who_entered_it(self):
        response = self.create()

        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["created_by"], self.clinic.full_name)
        self.assertIsNone(response.data["note"])
        self.assertIsNone(response.data["recurring_id"])
        self.assertFalse(response.data["is_void"])

    def test_doctor_share_needs_a_doctor_of_this_clinic(self):
        missing = self.create(category="doctor_share")
        self.assertEqual(missing.status_code, 400)
        self.assertEqual(missing.data["errors"]["doctor"], "required")

        foreign = self.create(category="doctor_share", doctor=make_doctor(make_clinic()).id)
        self.assertEqual(foreign.status_code, 400)
        self.assertEqual(foreign.data["errors"]["doctor"], "does_not_exist")

        ok = self.create(category="doctor_share", doctor=self.doctor.id)
        self.assertEqual(ok.status_code, 201, ok.data)
        self.assertEqual(ok.data["doctor"], self.doctor.full_name)

    def test_a_doctor_is_dropped_from_categories_that_have_none(self):
        response = self.create(category="rent", doctor=self.doctor.id)
        self.assertEqual(response.status_code, 201)
        self.assertIsNone(response.data["doctor_id"])

    def test_a_lab_bill_may_name_the_doctor(self):
        response = self.create(category="lab", doctor=self.doctor.id)
        self.assertEqual(response.data["doctor_id"], self.doctor.id)

    def test_amount_and_date_limits(self):
        self.assertEqual(self.create(amount=0).status_code, 400)
        self.assertEqual(self.create(amount=10_000_000_001).status_code, 400)
        self.assertEqual(self.create(amount=10_000_000_000).status_code, 201)
        tomorrow = (clinic_today() + timedelta(days=1)).isoformat()
        self.assertEqual(self.create(date=tomorrow).status_code, 400)

    def test_list_filters_by_period_and_category_newest_first(self):
        self.create(date="2026-03-01")
        self.create(date="2026-03-20", category="utilities")
        self.create(date="2026-04-02")

        response = self.owner.get(URL, {"from": "2026-03-01", "to": "2026-03-31"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual([row["date"] for row in response.data["results"]], ["2026-03-20", "2026-03-01"])

        rent = self.owner.get(URL, {"from": "2026-03-01", "to": "2026-03-31", "category": "rent"})
        self.assertEqual(rent.data["count"], 1)

        self.assertEqual(self.owner.get(URL).status_code, 400)
        self.assertEqual(
            self.owner.get(URL, {"from": "2026-03-01", "to": "2026-03-31", "category": "x"}).status_code,
            400,
        )

    def test_update_and_void(self):
        expense_id = self.create().data["id"]

        updated = self.owner.patch(f"{URL}{expense_id}/", {"amount": 11_000_000}, format="json")
        self.assertEqual(updated.status_code, 200, updated.data)
        self.assertEqual(updated.data["amount"], 11_000_000)

        voided = self.owner.post(f"{URL}{expense_id}/void/", {"reason": "Entered twice"}, format="json")
        self.assertEqual(voided.status_code, 200)
        self.assertTrue(voided.data["is_void"])

        self.assertEqual(
            self.owner.patch(f"{URL}{expense_id}/", {"amount": 1}, format="json").data["message_key"],
            "already_voided",
        )
        self.assertEqual(
            self.owner.post(f"{URL}{expense_id}/void/", {"reason": "Again"}, format="json").status_code,
            400,
        )
        # Voided, never deleted: it stays in the journal.
        listed = self.owner.get(URL, {"from": "2026-03-01", "to": "2026-03-31"})
        self.assertEqual(listed.data["count"], 1)

    def test_another_clinic_cannot_touch_the_expense(self):
        expense_id = self.create().data["id"]
        other = client_for(make_clinic())

        self.assertEqual(other.patch(f"{URL}{expense_id}/", {"amount": 1}, format="json").status_code, 404)
        self.assertEqual(
            other.post(f"{URL}{expense_id}/void/", {"reason": "Not mine"}, format="json").status_code, 404
        )
        self.assertEqual(Expense.objects.get().amount, 12_000_000)

    def test_summary_excludes_voided_and_groups_by_kind(self):
        self.create(date="2026-03-01", category="rent", amount=10_000_000)
        self.create(date="2026-03-02", category="lab", amount=2_000_000)
        self.create(date="2026-03-02", category="doctor_share", amount=3_000_000, doctor=self.doctor.id)
        voided = self.create(date="2026-03-03", category="marketing", amount=999_000).data["id"]
        self.owner.post(f"{URL}{voided}/void/", {"reason": "Mistake"}, format="json")

        response = self.owner.get(f"{URL}summary/", {"from": "2026-03-01", "to": "2026-03-07"})

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["bucket"], "day")
        self.assertEqual(
            response.data["totals"],
            {"total": 15_000_000, "count": 3, "payroll": 3_000_000, "fixed": 10_000_000, "variable": 2_000_000},
        )
        self.assertIsNone(response.data["previous_totals"])
        self.assertEqual(
            response.data["by_category"],
            [
                {"category": "doctor_share", "amount": 3_000_000},
                {"category": "rent", "amount": 10_000_000},
                {"category": "lab", "amount": 2_000_000},
            ],
        )
        self.assertEqual(len(response.data["series"]), 7)
        self.assertEqual(response.data["series"][1], {"start": "2026-03-02", "amount": 5_000_000})
        self.assertEqual(response.data["from"], "2026-03-01")

    def test_summary_compares_with_the_window_before(self):
        self.create(date="2026-02-25", amount=1_000_000)
        response = self.owner.get(f"{URL}summary/", {"from": "2026-03-01", "to": "2026-03-07"})
        self.assertEqual(response.data["previous_totals"]["total"], 1_000_000)

    def test_only_the_owner_sees_expenses(self):
        for user in (make_admin(self.clinic), self.doctor, make_patient(self.clinic)):
            client = client_for(user)
            self.assertEqual(client.get(URL, {"from": "2026-03-01", "to": "2026-03-31"}).status_code, 403)
            self.assertEqual(client.post(URL, {}, format="json").status_code, 403)
            self.assertEqual(client.get(RECURRING_URL).status_code, 403)


class RecurringExpenseTests(TestCase):
    def setUp(self):
        self.clinic = make_clinic()
        self.owner = client_for(self.clinic)
        self.this_month = clinic_today().replace(day=1)

    def create(self, **overrides):
        body = {
            "name": "Rent",
            "category": "rent",
            "amount": 8_000_000,
            "method": "transfer",
            "payee": "Landlord",
            "day_of_month": 5,
            **overrides,
        }
        return self.owner.post(RECURRING_URL, body, format="json")

    def due(self, month):
        return self.owner.get(f"{RECURRING_URL}due/", {"month": format_month(month)})

    def pay(self, recurring_id, month, amount=8_100_000):
        return self.owner.post(
            f"{RECURRING_URL}{recurring_id}/pay/",
            {"month": format_month(month), "date": clinic_today().isoformat(), "amount": amount, "method": "cash"},
            format="json",
        )

    def test_templates_validate_day_and_category(self):
        self.assertEqual(self.create(day_of_month=29).status_code, 400)
        self.assertEqual(self.create(category="doctor_share").status_code, 400)
        created = self.create()
        self.assertEqual(created.status_code, 201, created.data)
        self.assertTrue(created.data["is_active"])

    def test_a_new_bill_is_due_from_this_month_on(self):
        self.create()
        self.assertEqual(self.due(shift_month(self.this_month, -1)).data["items"], [])
        self.assertEqual(len(self.due(self.this_month).data["items"]), 1)
        self.assertEqual(len(self.due(shift_month(self.this_month, 1)).data["items"]), 1)

    def test_paying_a_month_posts_an_expense_and_cannot_repeat(self):
        recurring_id = self.create().data["id"]

        paid = self.pay(recurring_id, self.this_month)
        self.assertEqual(paid.status_code, 201, paid.data)
        self.assertEqual(paid.data["recurring_id"], recurring_id)
        self.assertEqual(paid.data["category"], "rent")
        self.assertEqual(paid.data["payee"], "Landlord")

        item = self.due(self.this_month).data["items"][0]
        self.assertEqual(item["status"], "paid")
        self.assertEqual(item["paid_amount"], 8_100_000)
        self.assertEqual(item["expense_id"], paid.data["id"])

        again = self.pay(recurring_id, self.this_month)
        self.assertEqual(again.status_code, 400)
        self.assertEqual(again.data["message_key"], "already_paid")

    def test_voiding_the_payment_frees_the_month(self):
        recurring_id = self.create().data["id"]
        expense_id = self.pay(recurring_id, self.this_month).data["id"]
        self.owner.post(f"{URL}{expense_id}/void/", {"reason": "Wrong month"}, format="json")

        self.assertNotEqual(self.due(self.this_month).data["items"][0]["status"], "paid")
        self.assertEqual(self.pay(recurring_id, self.this_month).status_code, 201)

    def test_skip_and_totals(self):
        rent = self.create().data["id"]
        internet = self.create(name="Internet", category="communication", amount=500_000, day_of_month=28).data["id"]

        skipped = self.owner.post(
            f"{RECURRING_URL}{internet}/skip/", {"month": format_month(self.this_month)}, format="json"
        )
        self.assertEqual(skipped.status_code, 204)
        self.pay(rent, self.this_month, amount=8_000_000)

        month = self.due(self.this_month).data
        self.assertEqual([item["status"] for item in month["items"]], ["paid", "skipped"])
        self.assertEqual(month["totals"], {"expected": 8_000_000, "paid": 8_000_000, "remaining": 0})

        paid_skip = self.owner.post(
            f"{RECURRING_URL}{rent}/skip/", {"month": format_month(self.this_month)}, format="json"
        )
        self.assertEqual(paid_skip.status_code, 400)

    def test_paying_a_skipped_month_clears_the_skip(self):
        rent = self.create().data["id"]
        self.owner.post(f"{RECURRING_URL}{rent}/skip/", {"month": format_month(self.this_month)}, format="json")
        self.pay(rent, self.this_month)
        self.assertEqual(self.due(self.this_month).data["items"][0]["status"], "paid")

    def test_overdue_and_due(self):
        self.create(day_of_month=1)
        self.create(day_of_month=28)
        next_month = shift_month(self.this_month, 1)
        statuses = [item["status"] for item in self.due(next_month).data["items"]]
        self.assertEqual(statuses, ["due", "due"])
        # A bill whose day has passed this month is overdue, unless today is that day.
        first = self.due(self.this_month).data["items"][0]
        expected = "overdue" if clinic_today() > self.this_month else "due"
        self.assertEqual(first["status"], expected)

    def test_a_paused_bill_only_stays_where_it_was_paid(self):
        rent = self.create().data["id"]
        self.pay(rent, self.this_month)
        paused = self.owner.patch(f"{RECURRING_URL}{rent}/", {"is_active": False}, format="json")
        self.assertEqual(paused.status_code, 200)
        self.assertFalse(paused.data["is_active"])

        self.assertEqual(len(self.due(self.this_month).data["items"]), 1)
        self.assertEqual(self.due(shift_month(self.this_month, 1)).data["items"], [])

    def test_month_is_required_and_validated(self):
        self.assertEqual(self.owner.get(f"{RECURRING_URL}due/").status_code, 400)
        self.assertEqual(self.owner.get(f"{RECURRING_URL}due/", {"month": "2026-13"}).status_code, 400)

    def test_another_clinics_bill_is_not_found(self):
        rent = self.create().data["id"]
        other = client_for(make_clinic())
        self.assertEqual(other.patch(f"{RECURRING_URL}{rent}/", {"amount": 1}, format="json").status_code, 404)
        self.assertEqual(
            other.post(
                f"{RECURRING_URL}{rent}/pay/",
                {"month": "2026-01", "date": "2026-01-05", "amount": 1, "method": "cash"},
                format="json",
            ).status_code,
            404,
        )
        self.assertEqual(other.get(RECURRING_URL).data, [])
