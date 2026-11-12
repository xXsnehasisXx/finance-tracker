"""Single source of 'today'. Production uses the real date; tests freeze _real_today (see root conftest.py)."""
import datetime


def _real_today() -> datetime.date:
    return datetime.date.today()


def get_today() -> datetime.date:
    return _real_today()
