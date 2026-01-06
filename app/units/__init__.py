from flask import Blueprint

units_bp = Blueprint("units", __name__, url_prefix="/units")

from . import routes  # noqa: F401