"""
Period helpers shared by the finance and statistics reports.

Every report takes a closed date range (`from`, `to`) in the clinic's own
calendar and answers with figures grouped into buckets. The bucket size is
chosen here, from the length of the range, so every report agrees on it.
"""
import re
from bisect import bisect_right
from dataclasses import dataclass
from datetime import date, timedelta

from django.utils import timezone

from apps.core.exceptions import ValidationError

# A year view compares against the year before it; longer ranges are not a report.
MAX_RANGE_DAYS = 366

DAY = "day"
WEEK = "week"
MONTH = "month"

_MONTH_RE = re.compile(r"^(\d{4})-(0[1-9]|1[0-2])$")


def clinic_today():
    # TIME_ZONE is the clinic's zone (Asia/Tashkent), so this is the clinic's day.
    return timezone.localdate()


def parse_date(value, field):
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        raise ValidationError(
            message=f"`{field}` must be a date in YYYY-MM-DD format.",
            message_key="invalid_date",
            errors={field: "invalid"},
        ) from None


def parse_month(value, field="month"):
    """`YYYY-MM` to the first day of that month."""
    match = _MONTH_RE.match(value or "")
    if not match:
        raise ValidationError(
            message=f"`{field}` must be a month in YYYY-MM format.",
            message_key="invalid_month",
            errors={field: "invalid"},
        )
    return date(int(match.group(1)), int(match.group(2)), 1)


def format_month(first_day):
    return first_day.strftime("%Y-%m")


def shift_month(first_day, months):
    index = first_day.year * 12 + first_day.month - 1 + months
    return date(index // 12, index % 12 + 1, 1)


def month_end(first_day):
    return shift_month(first_day, 1) - timedelta(days=1)


@dataclass(frozen=True)
class ReportRange:
    start: date
    end: date

    @property
    def days(self):
        return (self.end - self.start).days + 1

    @property
    def bucket(self):
        # Matches the periods the frontend offers: week and month by day,
        # a quarter by week, a year by month.
        if self.days <= 31:
            return DAY
        if self.days <= 92:
            return WEEK
        return MONTH

    def previous(self):
        """The same-length window right before this one, for period-over-period deltas."""
        end = self.start - timedelta(days=1)
        return ReportRange(start=end - timedelta(days=self.days - 1), end=end)

    def bucket_starts(self):
        starts = []
        if self.bucket == DAY:
            starts = [self.start + timedelta(days=i) for i in range(self.days)]
        elif self.bucket == WEEK:
            starts = [self.start + timedelta(days=i) for i in range(0, self.days, 7)]
        else:
            # The first bucket starts on `from`, every later one on the 1st of a month.
            starts = [self.start]
            cursor = shift_month(self.start.replace(day=1), 1)
            while cursor <= self.end:
                starts.append(cursor)
                cursor = shift_month(cursor, 1)
        return starts

    def series(self, amounts_by_date, fields):
        """
        Folds `{date: {field: amount}}` into one point per bucket, every bucket
        present and every field defaulting to 0.
        """
        starts = self.bucket_starts()
        points = [{"start": start, **{field: 0 for field in fields}} for start in starts]
        for day, amounts in amounts_by_date.items():
            if not self.start <= day <= self.end:
                continue
            point = points[bisect_right(starts, day) - 1]
            for field in fields:
                point[field] += amounts.get(field, 0)
        return points


def parse_range(query_params):
    """`?from=YYYY-MM-DD&to=YYYY-MM-DD`, both required and inclusive."""
    missing = {
        field: "required" for field in ("from", "to") if not query_params.get(field)
    }
    if missing:
        raise ValidationError(
            message="`from` and `to` are required.",
            message_key="missing_params",
            errors=missing,
        )
    start = parse_date(query_params.get("from"), "from")
    end = parse_date(query_params.get("to"), "to")
    if start > end:
        raise ValidationError(
            message="`from` must not be after `to`.",
            message_key="invalid_range",
            errors={"from": "invalid"},
        )
    report_range = ReportRange(start=start, end=end)
    if report_range.days > MAX_RANGE_DAYS:
        raise ValidationError(
            message=f"A report covers at most {MAX_RANGE_DAYS} days.",
            message_key="range_too_long",
            errors={"to": "invalid"},
        )
    return report_range


def require_month(query_params, field="month"):
    value = query_params.get(field)
    if not value:
        raise ValidationError(
            message=f"`{field}` is required.",
            message_key="missing_params",
            errors={field: "required"},
        )
    return parse_month(value, field)
