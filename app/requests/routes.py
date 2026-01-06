from datetime import datetime
from flask import render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from datetime import timedelta

from . import requests_bp
from ..extensions import db
from ..models import Request as StaffRequest, Unit, Assignment

STATUS_OPTIONS = ["Open", "Satisfied", "Canceled"]


def parse_dt(date_str: str, time_str: str) -> datetime:
    """Build a datetime from HTML date + time inputs."""
    return datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")


def filled_count(req: StaffRequest) -> int:
    """
    How many assignments are currently covering this request.

    Primary method: count assignments explicitly linked to this request via request_id.
    (This is the safest, avoids counting unrelated overlapping assignments.)
    """
    return (
        Assignment.query.filter(
            Assignment.request_id == req.id,
            Assignment.status != "Canceled",
        ).count()
    )


def is_satisfied(req: StaffRequest, filled: int) -> bool:
    return filled >= (req.staff_needed or 0)


@requests_bp.route("/", methods=["GET"])
@login_required
def list_requests():
    unit_id = request.args.get("unit_id", type=int)
    status = request.args.get("status", type=str)

    q = StaffRequest.query
    if unit_id:
        q = q.filter(StaffRequest.unit_id == unit_id)
    if status:
        q = q.filter(StaffRequest.status == status)

    reqs = q.order_by(StaffRequest.start_datetime.desc()).all()
    units = Unit.query.filter_by(is_active=True).order_by(Unit.unit_name.asc()).all()

    # list.html expects `rows` with: row.r, row.filled, row.sat
    rows = []
    for r in reqs:
        filled = filled_count(r)
        sat = is_satisfied(r, filled)
        rows.append({"r": r, "filled": filled, "sat": sat})

    return render_template(
        "requests/list.html",
        rows=rows,                 # ✅ FIX: template loops over rows【turn18file0†list.html†L28-L63】
        units=units,
        unit_id=unit_id,
        status=status,
        status_options=STATUS_OPTIONS,
    )


@requests_bp.route("/new", methods=["GET"])
@login_required
def new_request():
    unit_list = Unit.query.filter_by(is_active=True).order_by(Unit.unit_name.asc()).all()
    return render_template(
        "requests/form.html",
        req=None,
        unit_list=unit_list,
        status_options=STATUS_OPTIONS,
    )


@requests_bp.route("/new", methods=["POST"])
@login_required
def create_request():
    unit_id = request.form.get("unit_id", type=int)
    coordinator_name = (request.form.get("coordinator_name") or "").strip()
    staff_needed = request.form.get("staff_needed", type=int) or 1

    date_str = request.form.get("date") or ""
    start_time = request.form.get("start_time") or ""
    end_time = request.form.get("end_time") or ""
    status = request.form.get("status") or "Open"
    notes = (request.form.get("notes") or "").strip()

    if not unit_id:
        flash("Unit is required.", "danger")
        return redirect(url_for("requests.new_request"))
    if not coordinator_name:
        flash("Coordinator name is required.", "danger")
        return redirect(url_for("requests.new_request"))

    try:
        start_dt = parse_dt(date_str, start_time)
        end_dt = parse_dt(date_str, end_time)
    except ValueError:
        flash("Invalid date/time.", "danger")
        return redirect(url_for("requests.new_request"))

    if end_dt <= start_dt:
        end_dt = end_dt + timedelta(days=1)

    req = StaffRequest(
        unit_id=unit_id,
        coordinator_name=coordinator_name,
        staff_needed=staff_needed,
        start_datetime=start_dt,
        end_datetime=end_dt,
        status=status if status in STATUS_OPTIONS else "Open",
        notes=notes,
        created_by_admin_id=current_user.id,
    )
    db.session.add(req)
    db.session.commit()

    flash("Request created.", "success")
    return redirect(url_for("requests.list_requests"))


@requests_bp.route("/<int:request_id>/edit", methods=["GET"])
@login_required
def edit_request(request_id):
    req = StaffRequest.query.get_or_404(request_id)
    unit_list = Unit.query.filter_by(is_active=True).order_by(Unit.unit_name.asc()).all()
    return render_template(
        "requests/form.html",
        req=req,
        unit_list=unit_list,
        status_options=STATUS_OPTIONS,
    )


@requests_bp.route("/<int:request_id>/edit", methods=["POST"])
@login_required
def update_request(request_id):
    req = StaffRequest.query.get_or_404(request_id)

    unit_id = request.form.get("unit_id", type=int)
    coordinator_name = (request.form.get("coordinator_name") or "").strip()
    staff_needed = request.form.get("staff_needed", type=int) or 1

    date_str = request.form.get("date") or ""
    start_time = request.form.get("start_time") or ""
    end_time = request.form.get("end_time") or ""
    status = request.form.get("status") or req.status
    notes = (request.form.get("notes") or "").strip()

    if not unit_id:
        flash("Unit is required.", "danger")
        return redirect(url_for("requests.edit_request", request_id=req.id))
    if not coordinator_name:
        flash("Coordinator name is required.", "danger")
        return redirect(url_for("requests.edit_request", request_id=req.id))

    try:
        start_dt = parse_dt(date_str, start_time)
        end_dt = parse_dt(date_str, end_time)
    except ValueError:
        flash("Invalid date/time.", "danger")
        return redirect(url_for("requests.edit_request", request_id=req.id))

    if end_dt <= start_dt:
        end_dt = end_dt + timedelta(days=1)

    req.unit_id = unit_id
    req.coordinator_name = coordinator_name
    req.staff_needed = staff_needed
    req.start_datetime = start_dt
    req.end_datetime = end_dt
    req.status = status if status in STATUS_OPTIONS else req.status
    req.notes = notes

    db.session.commit()
    flash("Request updated.", "success")
    return redirect(url_for("requests.request_detail", request_id=req.id))


@requests_bp.route("/<int:request_id>/cancel", methods=["POST"])
@login_required
def cancel_request(request_id):
    req = StaffRequest.query.get_or_404(request_id)
    req.status = "Canceled"
    db.session.commit()
    flash("Request canceled.", "warning")
    return redirect(url_for("requests.list_requests"))


@requests_bp.route("/<int:request_id>", methods=["GET"])
@login_required
def request_detail(request_id):
    """
    Request detail page:
    - shows request
    - counts assigned staff (via assignments linked to request_id)
    - marks satisfied automatically if filled >= staff_needed
    """
    r = StaffRequest.query.get_or_404(request_id)

    filled = filled_count(r)
    sat = is_satisfied(r, filled)

    # Auto-update status unless canceled
    if r.status != "Canceled":
        new_status = "Satisfied" if sat else "Open"
        if r.status != new_status:
            r.status = new_status
            db.session.commit()

    overlaps = (
        Assignment.query.filter(
            Assignment.status != "Canceled",
            Assignment.start_datetime < r.end_datetime,
            r.start_datetime < Assignment.end_datetime,
        )
        .order_by(Assignment.start_datetime.asc())
        .all()
    )

    return render_template(
        "requests/detail.html",
        r=r,
        filled=filled,
        sat=sat,
        overlaps=overlaps,
    )