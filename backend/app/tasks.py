from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from app.models import Task


def local_date(zone_name: str, instant: datetime | None = None) -> date:
    instant = instant or datetime.now(timezone.utc)
    if instant.tzinfo is None:
        instant = instant.replace(tzinfo=timezone.utc)
    return instant.astimezone(ZoneInfo(zone_name)).date()


def occurs_on(task: Task, day: date) -> bool:
    start = task.due_date
    if start is None or day < start:
        return False
    if task.recurrence == "none":
        return day == start
    if task.recurrence == "daily":
        return True
    if task.recurrence == "weekly":
        return (day - start).days % 7 == 0
    if task.recurrence == "weekdays":
        return day.weekday() in (task.weekdays or [])
    return False


def days_between(start: date, end: date):
    day = start
    while day <= end:
        yield day
        day += timedelta(days=1)
