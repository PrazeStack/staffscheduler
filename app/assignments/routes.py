from datetime import datetime
from flask import render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from datetime import timedelta

from . import assignments_bp
from ..extensions import db
from ..models import Assignment, Staff, Unit, Request



STATUS_OPTIONS = ["Scheduled", "Confirmed", "Canceled"]


def parse_dt(date_str: str, time_str: str) -> datetime:
    # date: YYYY-MM-DD, time: HH:MM
    return datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")


def has_overlap(staff_id: int, start_dt: datetime, end_dt: datetime, exclude_assignment_id: int | None = None) -> bool:
    q = Assignment.query.filter(
        Assignment.staff_id == staff_id,
        Assignment.status != "Canceled",
        Assignment.start_datetime < end_dt,
        start_dt < Assignment.end_datetime,
    )
    if exclude_assignment_id:
        q = q.filter(Assignment.id != exclude_assignment_id)
    return db.session.query(q.exists()).scalar()


@assignments_bp.get("/")
@login_required
def list_assignments():
    # Filters
    staff_id = request.args.get("staff_id", type=int)
    unit_id = request.args.get("unit_id", type=int)
    date_from = request.args.get("from")  # YYYY-MM-DD
    date_to = request.args.get("to")      # YYYY-MM-DD
    show_canceled = request.args.get("canceled") == "1"

    q = Assignment.query

    if not show_canceled:
        q = q.filter(Assignment.status != "Canceled")

    if staff_id:
        q = q.filter(Assignment.staff_id == staff_id)
    if unit_id:
        q = q.filter(Assignment.unit_id == unit_id)

    if date_from:
        start_dt = datetime.strptime(date_from, "%Y-%m-%d")
        q = q.filter(Assignment.start_datetime >= start_dt)
    if date_to:
        # include entire date_to day by going to 23:59
        end_dt = datetime.strptime(date_to, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
        q = q.filter(Assignment.start_datetime <= end_dt)

    assignments = q.order_by(Assignment.start_datetime.asc()).all()

    staff_list = Staff.query.order_by(Staff.full_name.asc()).all()
    unit_list = Unit.query.order_by(Unit.unit_name.asc()).all()

    return render_template(
        "assignments/list.html",
        assignments=assignments,
        staff_list=staff_list,
        unit_list=unit_list,
        staff_id=staff_id,
        unit_id=unit_id,
        date_from=date_from or "",
        date_to=date_to or "",
        show_canceled=show_canceled,
    )


@assignments_bp.get("/new")
@login_required
def new_assignment():
    staff_list = Staff.query.filter_by(is_active=True).order_by(Staff.full_name.asc()).all()
    unit_list = Unit.query.filter_by(is_active=True).order_by(Unit.unit_name.asc()).all()
    requests = Request.query.order_by(Request.created_at.desc()).all()

    request_id = request.args.get("request_id", type=int)
    req = Request.query.get(request_id) if request_id else None

    return render_template(
        "assignments/form.html",
        assignment=None,
        staff_list=staff_list,
        unit_list=unit_list,
        requests=requests,
        req=req,  # <-- this is what drives the prefill
        status_options=STATUS_OPTIONS,
    )

@assignments_bp.post("/new")
@login_required
def create_assignment():
    staff_id = request.form.get("staff_id", type=int)
    unit_id = request.form.get("unit_id", type=int)
    request_id = request.form.get("request_id", type=int) or None

    date_str = (request.form.get("date") or "").strip()
    start_time = (request.form.get("start_time") or "").strip()
    end_time = (request.form.get("end_time") or "").strip()
    status = (request.form.get("status") or "Scheduled").strip()
    notes = (request.form.get("notes") or "").strip() or None

    if status not in STATUS_OPTIONS:
        flash("Invalid status.", "danger")
        return redirect(url_for("assignments.new_assignment"))

    try:
        start_dt = parse_dt(date_str, start_time)
        end_dt = parse_dt(date_str, end_time)
    except ValueError:
        flash("Invalid date/time format.", "danger")
        return redirect(url_for("assignments.new_assignment"))

    if end_dt <= start_dt:
        end_dt = end_dt + timedelta(days=1)

    if has_overlap(staff_id, start_dt, end_dt):
        flash("This staff already has an overlapping shift.", "danger")
        return redirect(url_for("assignments.new_assignment"))

    a = Assignment(
        staff_id=staff_id,
        unit_id=unit_id,
        request_id=request_id,
        start_datetime=start_dt,
        end_datetime=end_dt,
        status=status,
        notes=notes,
        created_by_admin_id=current_user.id,
    )
    db.session.add(a)
    db.session.commit()

    flash("Assignment created.", "success")
    return redirect(url_for("assignments.list_assignments"))


@assignments_bp.get("/<int:assignment_id>/edit")
@login_required
def edit_assignment(assignment_id):
    a = Assignment.query.get_or_404(assignment_id)

    # Allow selecting inactive staff/unit for existing records (history)
    staff_list = Staff.query.order_by(Staff.full_name.asc()).all()
    unit_list = Unit.query.order_by(Unit.unit_name.asc()).all()
    requests = Request.query.order_by(Request.created_at.desc()).all()

    return render_template(
        "assignments/form.html",
        assignment=a,
        staff_list=staff_list,
        unit_list=unit_list,
        requests=requests,
        req=None,
        status_options=STATUS_OPTIONS,
    )


@assignments_bp.post("/<int:assignment_id>/edit")
@login_required
def update_assignment(assignment_id):
    a = Assignment.query.get_or_404(assignment_id)

    staff_id = request.form.get("staff_id", type=int)
    unit_id = request.form.get("unit_id", type=int)
    request_id = request.form.get("request_id", type=int) or None

    date_str = (request.form.get("date") or "").strip()
    start_time = (request.form.get("start_time") or "").strip()
    end_time = (request.form.get("end_time") or "").strip()
    status = (request.form.get("status") or "Scheduled").strip()
    notes = (request.form.get("notes") or "").strip() or None

    if status not in STATUS_OPTIONS:
        flash("Invalid status.", "danger")
        return redirect(url_for("assignments.edit_assignment", assignment_id=assignment_id))

    try:
        start_dt = parse_dt(date_str, start_time)
        end_dt = parse_dt(date_str, end_time)
    except ValueError:
        flash("Invalid date/time format.", "danger")
        return redirect(url_for("assignments.edit_assignment", assignment_id=assignment_id))

    if end_dt <= start_dt:
        end_dt = end_dt + timedelta(days=1)

    if status != "Canceled" and has_overlap(staff_id, start_dt, end_dt, exclude_assignment_id=a.id):
        flash("This staff already has an overlapping shift.", "danger")
        return redirect(url_for("assignments.edit_assignment", assignment_id=assignment_id))

    a.staff_id = staff_id
    a.unit_id = unit_id
    a.request_id = request_id
    a.start_datetime = start_dt
    a.end_datetime = end_dt
    a.status = status
    a.notes = notes

    db.session.commit()
    flash("Assignment updated.", "success")
    return redirect(url_for("assignments.list_assignments"))


@assignments_bp.post("/<int:assignment_id>/cancel")
@login_required
def cancel_assignment(assignment_id):
    a = Assignment.query.get_or_404(assignment_id)
    a.status = "Canceled"
    db.session.commit()
    flash("Assignment canceled.", "success")
    return redirect(url_for("assignments.list_assignments"))