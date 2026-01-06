from datetime import date, datetime, timedelta
from flask import render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user

from . import recurring_requests_bp
from ..extensions import db
from ..models import RecurringRequest, Unit, Request as StaffRequest

DAY_BITS = {
    "MO": 1,
    "TU": 2,
    "WE": 4,
    "TH": 8,
    "FR": 16,
    "SA": 32,
    "SU": 64,
}

WEEKDAY_TO_CODE = {0: "MO", 1: "TU", 2: "WE", 3: "TH", 4: "FR", 5: "SA", 6: "SU"}

def mask_from_list(codes: list[str]) -> int:
    m = 0
    for c in codes:
        if c in DAY_BITS:
            m |= DAY_BITS[c]
    return m

def codes_from_mask(mask: int) -> list[str]:
    return [c for c, bit in DAY_BITS.items() if (mask & bit)]

def parse_date(s: str) -> date:
    return datetime.strptime(s, "%Y-%m-%d").date()

def combine(dt: date, hhmm: str) -> datetime:
    return datetime.strptime(f"{dt.isoformat()} {hhmm}", "%Y-%m-%d %H:%M")

def should_run_on(rr: RecurringRequest, d: date) -> bool:
    code = WEEKDAY_TO_CODE[d.weekday()]
    return (rr.days_mask & DAY_BITS[code]) != 0

@recurring_requests_bp.route("/", methods=["GET"])
@login_required
def list_rr():
    rrs = RecurringRequest.query.order_by(RecurringRequest.created_at.desc()).all()
    unit_list = Unit.query.order_by(Unit.unit_name.asc()).all()
    return render_template("recurring_requests/list.html", rrs=rrs, unit_list=unit_list, codes_from_mask=codes_from_mask)

@recurring_requests_bp.route("/new", methods=["GET"])
@login_required
def new_rr():
    unit_list = Unit.query.filter_by(is_active=True).order_by(Unit.unit_name.asc()).all()
    return render_template("recurring_requests/form.html", rr=None, unit_list=unit_list, selected_days=[])

@recurring_requests_bp.route("/new", methods=["POST"])
@login_required
def create_rr():
    unit_id = request.form.get("unit_id", type=int)
    coordinator_name = (request.form.get("coordinator_name") or "").strip()
    staff_needed = request.form.get("staff_needed", type=int)
    start_time = (request.form.get("start_time") or "").strip()
    end_time = (request.form.get("end_time") or "").strip()

    start_date_str = (request.form.get("start_date") or "").strip()
    end_date_str = (request.form.get("end_date") or "").strip()  # optional => until changed

    days = request.form.getlist("days")  # ["MO","WE",...]
    notes = (request.form.get("notes") or "").strip() or None

    if not unit_id:
        flash("Unit is required.", "danger")
        return redirect("/recurring-requests/new")

    if not coordinator_name:
        flash("Coordinator name is required.", "danger")
        return redirect("/recurring-requests/new")

    if not staff_needed or staff_needed <= 0:
        flash("Staff needed must be a positive number.", "danger")
        return redirect("/recurring-requests/new")

    if not start_time or not end_time:
        flash("Start and end time are required.", "danger")
        return redirect("/recurring-requests/new")

    if not days:
        flash("Select at least one day of the week.", "danger")
        return redirect("/recurring-requests/new")

    try:
        sd = parse_date(start_date_str)
        ed = parse_date(end_date_str) if end_date_str else None
    except ValueError:
        flash("Invalid date format.", "danger")
        return redirect("/recurring-requests/new")

    rr = RecurringRequest(
        unit_id=unit_id,
        coordinator_name=coordinator_name,
        staff_needed=staff_needed,
        start_time=start_time,
        end_time=end_time,
        days_mask=mask_from_list(days),
        start_date=sd,
        end_date=ed,          # None => until changed
        is_active=True,
        notes=notes,
        created_by_admin_id=current_user.id,
    )
    db.session.add(rr)
    db.session.commit()

    flash("Recurring request created.", "success")
    return redirect("/recurring-requests/")

@recurring_requests_bp.route("/<int:rr_id>/edit", methods=["GET"])
@login_required
def edit_rr(rr_id):
    rr = RecurringRequest.query.get_or_404(rr_id)
    unit_list = Unit.query.order_by(Unit.unit_name.asc()).all()
    return render_template(
        "recurring_requests/form.html",
        rr=rr,
        unit_list=unit_list,
        selected_days=codes_from_mask(rr.days_mask),
    )

@recurring_requests_bp.route("/<int:rr_id>/edit", methods=["POST"])
@login_required
def update_rr(rr_id):
    rr = RecurringRequest.query.get_or_404(rr_id)

    unit_id = request.form.get("unit_id", type=int)
    coordinator_name = (request.form.get("coordinator_name") or "").strip()
    staff_needed = request.form.get("staff_needed", type=int)
    start_time = (request.form.get("start_time") or "").strip()
    end_time = (request.form.get("end_time") or "").strip()

    start_date_str = (request.form.get("start_date") or "").strip()
    end_date_str = (request.form.get("end_date") or "").strip()

    days = request.form.getlist("days")
    notes = (request.form.get("notes") or "").strip() or None

    if not unit_id or not coordinator_name or not start_time or not end_time or not days or not staff_needed or staff_needed <= 0:
        flash("Please fill all required fields (and select days).", "danger")
        return redirect(f"/recurring-requests/{rr_id}/edit")

    try:
        rr.start_date = parse_date(start_date_str)
        rr.end_date = parse_date(end_date_str) if end_date_str else None
    except ValueError:
        flash("Invalid date format.", "danger")
        return redirect(f"/recurring-requests/{rr_id}/edit")

    rr.unit_id = unit_id
    rr.coordinator_name = coordinator_name
    rr.staff_needed = staff_needed
    rr.start_time = start_time
    rr.end_time = end_time
    rr.days_mask = mask_from_list(days)
    rr.notes = notes

    rr.is_active = request.form.get("is_active") == "on"

    db.session.commit()
    flash("Recurring request updated.", "success")
    return redirect("/recurring-requests/")

@recurring_requests_bp.route("/generate", methods=["POST"])
@login_required
def generate():
    # generate occurrences for next N days (default 28)
    horizon_days = request.form.get("horizon_days", type=int) or 28
    today = date.today()
    end = today + timedelta(days=horizon_days)

    rrs = RecurringRequest.query.filter_by(is_active=True).all()
    created = 0
    skipped = 0

    for rr in rrs:
        d = max(today, rr.start_date)
        while d <= end:
            if rr.end_date and d > rr.end_date:
                break

            if should_run_on(rr, d):
                # build datetimes (handle end past midnight)
                start_dt = combine(d, rr.start_time)
                end_dt = combine(d, rr.end_time)
                if end_dt <= start_dt:
                    end_dt = end_dt + timedelta(days=1)

                # duplicate protection by unique constraint
                exists = StaffRequest.query.filter_by(recurring_id=rr.id, occurrence_date=d).first()
                if exists:
                    skipped += 1
                else:
                    occ = StaffRequest(
                        unit_id=rr.unit_id,
                        coordinator_name=rr.coordinator_name,
                        staff_needed=rr.staff_needed,
                        start_datetime=start_dt,
                        end_datetime=end_dt,
                        status="Open",
                        notes=rr.notes,
                        created_by_admin_id=current_user.id,
                        recurring_id=rr.id,
                        occurrence_date=d,
                    )
                    db.session.add(occ)
                    created += 1
            d += timedelta(days=1)

    db.session.commit()
    flash(f"Generated {created} request(s). Skipped {skipped} existing.", "success")
    return redirect("/recurring-requests/")