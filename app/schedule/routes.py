from datetime import datetime, date, time, timedelta
from collections import defaultdict

from flask import render_template, request
from flask_login import login_required

from . import schedule_bp
from ..models import Assignment, Unit, Staff

# Week: Friday-first (Fri=4 in Python weekday: Mon=0 ... Sun=6)
FRIDAY = 4

# Display order for a Fri→Thu week:
# Fri, Sat, Sun, Mon, Tue, Wed, Thu
DAY_LABELS = ["Fri", "Sat", "Sun", "Mon", "Tue", "Wed", "Thu"]

# Bi-week anchor start (given by you): 12/26/2025
BIWEEK_ANCHOR = date(2025, 12, 26)


def parse_ymd(s: str | None) -> date:
    if not s:
        return date.today()
    return datetime.strptime(s, "%Y-%m-%d").date()


def week_start_friday(d: date) -> date:
    """Snap any date to the Friday that starts its Fri→Thu week."""
    delta = (d.weekday() - FRIDAY) % 7
    return d - timedelta(days=delta)


def biweek_start_from_anchor(d: date) -> date:
    """
    Snap any date to the START of its bi-week period,
    where periods are 14 days starting from BIWEEK_ANCHOR.
    """
    # Ensure we're aligned to a Friday week start first (optional but makes behavior predictable)
    d0 = week_start_friday(d)

    days_since = (d0 - BIWEEK_ANCHOR).days
    # floor-div by 14 to find which biweek block
    block = days_since // 14
    return BIWEEK_ANCHOR + timedelta(days=block * 14)


def dt_start(d: date) -> datetime:
    return datetime.combine(d, time.min)


def group_assignments_by_day(assignments, period_start: date):
    """
    period_start is the start date of whichever week block you're grouping.
    returns {0..6 -> [assignments]} based on assignment.start_datetime.date()
    """
    buckets = defaultdict(list)
    for a in assignments:
        idx = (a.start_datetime.date() - period_start).days
        if 0 <= idx <= 6:
            buckets[idx].append(a)
    for k in buckets:
        buckets[k].sort(key=lambda x: x.start_datetime)
    return buckets


def total_hours(assignments) -> float:
    seconds = sum((a.end_datetime - a.start_datetime).total_seconds() for a in assignments)
    return round(seconds / 3600, 2)


@schedule_bp.route("/", methods=["GET"])
@login_required
def biweekly_home():
    qdate = parse_ymd(request.args.get("date"))

    # biweek period start (Fri)
    bw_start = biweek_start_from_anchor(qdate)
    bw_end = bw_start + timedelta(days=14)  # exclusive

    week1_start = bw_start
    week1_end = week1_start + timedelta(days=7)  # exclusive
    week2_start = week1_end
    week2_end = bw_end  # exclusive

    units = Unit.query.filter_by(is_active=True).order_by(Unit.unit_name.asc()).all()
    staff = Staff.query.filter_by(is_active=True).order_by(Staff.full_name.asc()).all()

    return render_template(
        "schedule/home.html",
        qdate=qdate,
        bw_start=bw_start,
        bw_end_display=bw_end - timedelta(days=1),
        week1_start=week1_start,
        week1_end_display=week1_end - timedelta(days=1),
        week2_start=week2_start,
        week2_end_display=week2_end - timedelta(days=1),
        units=units,
        staff=staff,
    )


@schedule_bp.route("/unit/<int:unit_id>", methods=["GET"])
@login_required
def biweekly_by_unit(unit_id):
    qdate = parse_ymd(request.args.get("date"))

    bw_start = biweek_start_from_anchor(qdate)
    bw_end = bw_start + timedelta(days=14)  # exclusive

    week1_start = bw_start
    week1_end = week1_start + timedelta(days=7)  # exclusive
    week2_start = week1_end
    week2_end = bw_end  # exclusive

    unit = Unit.query.get_or_404(unit_id)

    start_dt = dt_start(bw_start)
    end_dt = dt_start(bw_end)

    assignments = (
        Assignment.query
        .filter(
            Assignment.unit_id == unit_id,
            Assignment.status != "Canceled",
            Assignment.start_datetime < end_dt,
            Assignment.end_datetime > start_dt,
        )
        .order_by(Assignment.start_datetime.asc())
        .all()
    )

    # split into week1/week2 by start_datetime
    a_w1 = [a for a in assignments if a.start_datetime < dt_start(week1_end)]
    a_w2 = [a for a in assignments if a.start_datetime >= dt_start(week2_start)]

    w1_by_day = group_assignments_by_day(a_w1, week1_start)
    w2_by_day = group_assignments_by_day(a_w2, week2_start)

    week1_days = [
        {"idx": i, "label": DAY_LABELS[i], "date": week1_start + timedelta(days=i), "assignments": w1_by_day.get(i, [])}
        for i in range(7)
    ]
    week2_days = [
        {"idx": i, "label": DAY_LABELS[i], "date": week2_start + timedelta(days=i), "assignments": w2_by_day.get(i, [])}
        for i in range(7)
    ]

    return render_template(
        "schedule/biweek.html",
        mode="unit",
        title=f"Unit: {unit.unit_name}",
        unit=unit,
        staff=None,
        qdate=qdate,
        bw_start=bw_start,
        bw_end_display=bw_end - timedelta(days=1),
        week1_start=week1_start,
        week1_end_display=week1_end - timedelta(days=1),
        week2_start=week2_start,
        week2_end_display=week2_end - timedelta(days=1),
        week1_days=week1_days,
        week2_days=week2_days,
        # unit totals optional (usually not needed, but included)
        week1_total_hours=None,
        week2_total_hours=None,
        biweek_total_hours=None,
    )


@schedule_bp.route("/staff/<int:staff_id>", methods=["GET"])
@login_required
def biweekly_by_staff(staff_id):
    qdate = parse_ymd(request.args.get("date"))

    bw_start = biweek_start_from_anchor(qdate)
    bw_end = bw_start + timedelta(days=14)  # exclusive

    week1_start = bw_start
    week1_end = week1_start + timedelta(days=7)  # exclusive
    week2_start = week1_end
    week2_end = bw_end  # exclusive

    staff = Staff.query.get_or_404(staff_id)

    start_dt = dt_start(bw_start)
    end_dt = dt_start(bw_end)

    assignments = (
        Assignment.query
        .filter(
            Assignment.staff_id == staff_id,
            Assignment.status != "Canceled",
            Assignment.start_datetime < end_dt,
            Assignment.end_datetime > start_dt,
        )
        .order_by(Assignment.start_datetime.asc())
        .all()
    )

    # split into week1/week2
    a_w1 = [a for a in assignments if a.start_datetime < dt_start(week1_end)]
    a_w2 = [a for a in assignments if a.start_datetime >= dt_start(week2_start)]

    week1_total = total_hours(a_w1)
    week2_total = total_hours(a_w2)
    biweek_total = round(week1_total + week2_total, 2)

    w1_by_day = group_assignments_by_day(a_w1, week1_start)
    w2_by_day = group_assignments_by_day(a_w2, week2_start)

    week1_days = [
        {"idx": i, "label": DAY_LABELS[i], "date": week1_start + timedelta(days=i), "assignments": w1_by_day.get(i, [])}
        for i in range(7)
    ]
    week2_days = [
        {"idx": i, "label": DAY_LABELS[i], "date": week2_start + timedelta(days=i), "assignments": w2_by_day.get(i, [])}
        for i in range(7)
    ]

    return render_template(
        "schedule/biweek.html",
        mode="staff",
        title=f"Staff: {staff.full_name}",
        unit=None,
        staff=staff,
        qdate=qdate,
        bw_start=bw_start,
        bw_end_display=bw_end - timedelta(days=1),
        week1_start=week1_start,
        week1_end_display=week1_end - timedelta(days=1),
        week2_start=week2_start,
        week2_end_display=week2_end - timedelta(days=1),
        week1_days=week1_days,
        week2_days=week2_days,
        week1_total_hours=week1_total,
        week2_total_hours=week2_total,
        biweek_total_hours=biweek_total,
    )