
from datetime import datetime, date, timedelta

WEEK_START_WEEKDAY = 5  # Saturday (Python weekday: Mon=0 ... Sun=6)

def to_date(d) -> date:
    if isinstance(d, datetime):
        return d.date()
    return d

def week_start_saturday(d: date) -> date:
    d = to_date(d)
    delta = (d.weekday() - WEEK_START_WEEKDAY) % 7
    return d - timedelta(days=delta)

def week_range_saturday(d: date):
    start = week_start_saturday(d)
    days = [start + timedelta(days=i) for i in range(7)]  # Sat..Fri
    end_exclusive = start + timedelta(days=7)
    return start, end_exclusive, days