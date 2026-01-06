from flask import render_template, request, redirect, url_for, flash
from flask_login import login_required
from ..extensions import db
from ..models import Unit
from . import units_bp

@units_bp.get("/")
@login_required
def list_units():
    q = (request.args.get("q") or "").strip()
    show_inactive = request.args.get("inactive") == "1"

    query = Unit.query
    if q:
        query = query.filter(Unit.unit_name.ilike(f"%{q}%"))
    if not show_inactive:
        query = query.filter_by(is_active=True)

    units = query.order_by(Unit.unit_name.asc()).all()

    return render_template(
        "units/list.html",
        units=units,
        q=q,
        show_inactive=show_inactive
    )

@units_bp.get("/new")
@login_required
def new_unit():
    return render_template("units/form.html", unit=None)

@units_bp.post("/new")
@login_required
def create_unit():
    unit_name = (request.form.get("unit_name") or "").strip()
    address = (request.form.get("address") or "").strip() or None

    if not unit_name:
        flash("Unit name is required.", "danger")
        return redirect(url_for("units.new_unit"))

    u = Unit(unit_name=unit_name, address=address, is_active=True)
    db.session.add(u)
    db.session.commit()

    flash("Unit created.", "success")
    return redirect(url_for("units.list_units"))

@units_bp.get("/<int:unit_id>/edit")
@login_required
def edit_unit(unit_id):
    u = Unit.query.get_or_404(unit_id)
    return render_template("units/form.html", unit=u)

@units_bp.post("/<int:unit_id>/edit")
@login_required
def update_unit(unit_id):
    u = Unit.query.get_or_404(unit_id)

    unit_name = (request.form.get("unit_name") or "").strip()
    address = (request.form.get("address") or "").strip() or None
    is_active = request.form.get("is_active") == "on"

    if not unit_name:
        flash("Unit name is required.", "danger")
        return redirect(url_for("units.edit_unit", unit_id=unit_id))

    u.unit_name = unit_name
    u.address = address
    u.is_active = is_active

    db.session.commit()
    flash("Unit updated.", "success")
    return redirect(url_for("units.list_units"))

@units_bp.post("/<int:unit_id>/toggle")
@login_required
def toggle_unit(unit_id):
    u = Unit.query.get_or_404(unit_id)
    u.is_active = not u.is_active
    db.session.commit()
    flash(f"Unit {'activated' if u.is_active else 'deactivated'}.", "success")
    return redirect(url_for("units.list_units"))