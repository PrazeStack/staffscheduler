from flask import Blueprint

recurring_assignments_bp = Blueprint(
    "recurring_assignments",
    __name__,
    url_prefix="/recurring-assignments"
)

from . import routes  # noqa