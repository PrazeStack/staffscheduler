from datetime import date, datetime, timedelta
from flask import render_template, request, redirect, flash
from flask_login import login_required, current_user

from . import recurring_assignments_bp
from ..extensions import db
from ..models import RecurringAssignment, Staff, Unit, Assignment

DAY_BITS = {"MO": 1, "TU": 2, "WE": 4, "TH": 8, "FR": 16, "SA": 32, "SU": 64}
WEEKDAY_TO_CODE = {0: "MO", 1: "TU", 2: "WE", 3: "TH", 4: "FR", 5: "SA", 6: "SU"}


def mask_from_list(codes):
    m = 0
    for c in codes:
        if c in DAY_BITS:
            m |= DAY_BITS[c]
    return m


def codes_from_mask(mask: int):
    return [c for c, bit in DAY_BITS.items() if (mask & bit)]


def parse_date(s: str) -> date:
    return datetime.strptime(s, "%Y-%m-%d").date()


def combine(d: date, hhmm: str) -> datetime:
    return datetime.strptime(f"{d.isoformat()} {hhmm}", "%Y-%m-%d %H:%M")


def should_run_on(ra: RecurringAssignment, d: date) -> bool:
    code = WEEKDAY_TO_CODE[d.weekday()]
    return (ra.days_mask & DAY_BITS[code]) != 0


def staff_overlaps(staff_id: int, start_dt: datetime, end_dt: datetime) -> bool:
    q = Assignment.query.filter(
        Assignment.staff_id == staff_id,
        Assignment.status != "Canceled",
        Assignment.start_datetime < end_dt,
        start_dt < Assignment.end_datetime,
    )
    return db.session.query(q.exists()).scalar()


@recurring_assignments_bp.route("/", methods=["GET"])
@login_required
def list_ra():
    ras = RecurringAssignment.query.order_by(RecurringAssignment.created_at.desc()).all()
    return render_template(
        "recurring_assignments/list.html",
        ras=ras,
        codes_from_mask=codes_from_mask,
    )


@recurring_assignments_bp.route("/new", methods=["GET"])
@login_required
def new_ra():
    staff_list = Staff.query.filter_by(is_active=True).order_by(Staff.full_name.asc()).all()
    unit_list = Unit.query.filter_by(is_active=True).order_by(Unit.unit_name.asc()).all()
    return render_template(
        "recurring_assignments/form.html",
        ra=None,
        staff_list=staff_list,
        unit_list=unit_list,
        selected_days=[],
    )


@recurring_assignments_bp.route("/new", methods=["POST"])
@login_required
def create_ra():
    staff_id = request.form.get("staff_id", type=int)
    unit_id = request.form.get("unit_id", type=int)
    start_time = (request.form.get("start_time") or "").strip()
    end_time = (request.form.get("end_time") or "").strip()
    start_date_str = (request.form.get("start_date") or "").strip()
    end_date_str = (request.form.get("end_date") or "").strip()
    days = request.form.getlist("days")
    notes = (request.form.get("notes") or "").strip() or None

    if not staff_id or not unit_id or not start_time or not end_time or not days or not start_date_str:
        flash("Fill all required fields and select days.", "danger")
        return redirect("/recurring-assignments/new")

    sd = parse_date(start_date_str)
    ed = parse_date(end_date_str) if end_date_str else None

    ra = RecurringAssignment(
        staff_id=staff_id,
        unit_id=unit_id,
        start_time=start_time,
        end_time=end_time,
        days_mask=mask_from_list(days),
        start_date=sd,
        end_date=ed,
        is_active=True,
        notes=notes,
        created_by_admin_id=current_user.id,
    )
    db.session.add(ra)
    db.session.commit()

    flash("Recurring assignment created.", "success")
    return redirect("/recurring-assignments/")


@recurring_assignments_bp.route("/<int:ra_id>/edit", methods=["GET"])
@login_required
def edit_ra(ra_id):
    ra = RecurringAssignment.query.get_or_404(ra_id)
    staff_list = Staff.query.order_by(Staff.full_name.asc()).all()
    unit_list = Unit.query.order_by(Unit.unit_name.asc()).all()
    return render_template(
        "recurring_assignments/form.html",
        ra=ra,
        staff_list=staff_list,
        unit_list=unit_list,
        selected_days=codes_from_mask(ra.days_mask),
    )


@recurring_assignments_bp.route("/<int:ra_id>/edit", methods=["POST"])
@login_required
def update_ra(ra_id):
    ra = RecurringAssignment.query.get_or_404(ra_id)

    ra.staff_id = request.form.get("staff_id", type=int)
    ra.unit_id = request.form.get("unit_id", type=int)
    ra.start_time = (request.form.get("start_time") or "").strip()
    ra.end_time = (request.form.get("end_time") or "").strip()
    ra.start_date = parse_date(request.form.get("start_date"))
    end_date_str = (request.form.get("end_date") or "").strip()
    ra.end_date = parse_date(end_date_str) if end_date_str else None
    ra.days_mask = mask_from_list(request.form.getlist("days"))
    ra.notes = (request.form.get("notes") or "").strip() or None
    ra.is_active = request.form.get("is_active") == "on"

    db.session.commit()
    flash("Recurring assignment updated.", "success")
    return redirect("/recurring-assignments/")


@recurring_assignments_bp.route("/generate", methods=["POST"])
@login_required
def generate():
    horizon_days = request.form.get("horizon_days", type=int) or 28
    today = date.today()
    end = today + timedelta(days=horizon_days)

    ras = RecurringAssignment.query.filter_by(is_active=True).all()
    created = 0
    skipped = 0
    conflicts = 0

    for ra in ras:
        d = max(today, ra.start_date)
        while d <= end:
            if ra.end_date and d > ra.end_date:
                break

            if should_run_on(ra, d):
                exists = Assignment.query.filter_by(recurring_id=ra.id, occurrence_date=d).first()
                if exists:
                    skipped += 1
                else:
                    start_dt = combine(d, ra.start_time)
                    end_dt = combine(d, ra.end_time)
                    if end_dt <= start_dt:
                        end_dt = end_dt + timedelta(days=1)

                    if staff_overlaps(ra.staff_id, start_dt, end_dt):
                        conflicts += 1
                    else:
                        a = Assignment(
                            staff_id=ra.staff_id,
                            unit_id=ra.unit_id,
                            start_datetime=start_dt,
                            end_datetime=end_dt,
                            status="Scheduled",
                            notes=ra.notes,
                            created_by_admin_id=current_user.id,
                            recurring_id=ra.id,
                            occurrence_date=d,
                        )
                        db.session.add(a)
                        created += 1

            d += timedelta(days=1)

    db.session.commit()
    flash(f"Generated {created}. Skipped {skipped}. Conflicts {conflicts} (overlaps).", "success")
    return redirect("/recurring-assignments/")