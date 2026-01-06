from flask import render_template, request, redirect, url_for, flash
from flask_login import login_required
from ..extensions import db
from ..models import Staff
from . import staff_bp

GENDER_OPTIONS = ["Male", "Female", "Other"]

@staff_bp.get("/")
@login_required
def list_staff():
    q = (request.args.get("q") or "").strip()
    show_inactive = request.args.get("inactive") == "1"

    query = Staff.query
    if q:
        query = query.filter(Staff.full_name.ilike(f"%{q}%"))
    if not show_inactive:
        query = query.filter_by(is_active=True)

    staff = query.order_by(Staff.full_name.asc()).all()

    return render_template(
        "staff/list.html",
        staff=staff,
        q=q,
        show_inactive=show_inactive
    )

@staff_bp.get("/new")
@login_required
def new_staff():
    return render_template("staff/form.html", staff=None, genders=GENDER_OPTIONS)

@staff_bp.post("/new")
@login_required
def create_staff():
    full_name = (request.form.get("full_name") or "").strip()
    gender = (request.form.get("gender") or "").strip()
    phone = (request.form.get("phone") or "").strip() or None

    if not full_name:
        flash("Full name is required.", "danger")
        return redirect(url_for("staff.new_staff"))

    if gender not in GENDER_OPTIONS:
        flash("Please select a valid gender.", "danger")
        return redirect(url_for("staff.new_staff"))

    s = Staff(full_name=full_name, gender=gender, phone=phone, is_active=True)
    db.session.add(s)
    db.session.commit()

    flash("Staff created.", "success")
    return redirect(url_for("staff.list_staff"))

@staff_bp.get("/<int:staff_id>/edit")
@login_required
def edit_staff(staff_id):
    s = Staff.query.get_or_404(staff_id)
    return render_template("staff/form.html", staff=s, genders=GENDER_OPTIONS)

@staff_bp.post("/<int:staff_id>/edit")
@login_required
def update_staff(staff_id):
    s = Staff.query.get_or_404(staff_id)

    full_name = (request.form.get("full_name") or "").strip()
    gender = (request.form.get("gender") or "").strip()
    phone = (request.form.get("phone") or "").strip() or None
    is_active = request.form.get("is_active") == "on"

    if not full_name:
        flash("Full name is required.", "danger")
        return redirect(url_for("staff.edit_staff", staff_id=staff_id))

    if gender not in GENDER_OPTIONS:
        flash("Please select a valid gender.", "danger")
        return redirect(url_for("staff.edit_staff", staff_id=staff_id))

    s.full_name = full_name
    s.gender = gender
    s.phone = phone
    s.is_active = is_active

    db.session.commit()
    flash("Staff updated.", "success")
    return redirect(url_for("staff.list_staff"))

@staff_bp.post("/<int:staff_id>/toggle")
@login_required
def toggle_staff(staff_id):
    s = Staff.query.get_or_404(staff_id)
    s.is_active = not s.is_active
    db.session.commit()
    flash(f"Staff {'activated' if s.is_active else 'deactivated'}.", "success")
    return redirect(url_for("staff.list_staff"))