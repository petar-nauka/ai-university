"""Weekly schedule allocation: spread module and capstone hours over weeks."""
import math
from datetime import date, timedelta

_EPS = 1e-9


def allocate_weeks(module_hours, capstone_hours, hours_per_week):
    if hours_per_week <= 0:
        raise ValueError("hours_per_week must be positive")
    state = {"week": 1, "left": float(hours_per_week), "used": False}

    def place(hours):
        # A unit starts in the current week if it has spare capacity, else in the next.
        if state["used"] and state["left"] <= _EPS:
            state["week"] += 1
            state["left"] = float(hours_per_week)
        start = state["week"]
        remaining = float(hours)
        state["used"] = True
        while remaining > _EPS:
            if state["left"] <= _EPS:
                state["week"] += 1
                state["left"] = float(hours_per_week)
            take = min(remaining, state["left"])
            state["left"] -= take
            remaining -= take
        return (start, state["week"])

    modules = [place(h) for h in module_hours]
    capstone = place(capstone_hours) if capstone_hours > 0 else None
    last = capstone[1] if capstone else (modules[-1][1] if modules else 0)
    return {"modules": modules, "capstone": capstone, "total_weeks": last}


def week_dates(start_date, week):
    first = date.fromisoformat(start_date) + timedelta(weeks=week - 1)
    return first.isoformat(), (first + timedelta(days=6)).isoformat()


def format_weeks(span):
    start, end = span
    return str(start) if start == end else f"{start}–{end}"


def day_week(day, days_per_week):
    """The week a study day falls in: with 5 days a week, days 1-5 are week 1, day 6 is week 2."""
    return (day - 1) // days_per_week + 1


def day_date(start_date, day, days_per_week):
    """The calendar date of a study day: the week's first day plus its place in the week."""
    offset = 7 * (day_week(day, days_per_week) - 1) + (day - 1) % days_per_week
    return (date.fromisoformat(start_date) + timedelta(days=offset)).isoformat()


def plan_days(plan, hours, day_minutes):
    """How many study days a unit takes: its plan's days, or its hours over the day length."""
    if isinstance(plan, list) and plan:
        return len(plan)
    return max(1, math.ceil(float(hours) * 60 / day_minutes - _EPS))
