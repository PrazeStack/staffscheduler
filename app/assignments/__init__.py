from flask import Blueprint

assignments_bp = Blueprint("assignments", __name__, url_prefix="/assignments")

from . import routes  # noqa: F401