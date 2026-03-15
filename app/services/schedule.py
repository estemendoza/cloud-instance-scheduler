from datetime import datetime, time, timezone
from typing import Dict, List, Optional
import pytz
from croniter import croniter


class ScheduleEvaluator:
    """Evaluates weekly and cron schedules to determine if a resource should be running."""

    DAYS_OF_WEEK = [
        "monday", "tuesday", "wednesday",
        "thursday", "friday", "saturday", "sunday",
    ]

    VALID_SCHEDULE_TYPES = ("weekly", "cron")

    @staticmethod
    def is_running_time(
        schedule: Dict,
        timezone_str: str,
        current_time: Optional[datetime] = None,
        schedule_type: str = "weekly",
    ) -> bool:
        """
        Determine if the current time falls within a running window.

        Args:
            schedule: Schedule dict. Shape depends on schedule_type:
                weekly: {"monday": [{"start": "09:00", "end": "18:00"}], ...}
                cron:   {"start": "0 9 * * 1-5", "stop": "0 18 * * 1-5"}
            timezone_str: IANA timezone (e.g., "America/New_York")
            current_time: Optional datetime (defaults to now UTC)
            schedule_type: "weekly" or "cron"

        Returns:
            True if current time is within a running window, False otherwise
        """
        if schedule_type == "cron":
            return ScheduleEvaluator._is_running_time_cron(
                schedule, timezone_str, current_time)
        return ScheduleEvaluator._is_running_time_weekly(
            schedule, timezone_str, current_time)

    @staticmethod
    def _is_running_time_weekly(
        schedule: Dict,
        timezone_str: str,
        current_time: Optional[datetime] = None,
    ) -> bool:
        """Evaluate a weekly time-window schedule."""
        if current_time is None:
            current_time = datetime.now(timezone.utc)

        try:
            tz = pytz.timezone(timezone_str)
        except pytz.UnknownTimeZoneError:
            return False

        if current_time.tzinfo is None:
            current_time = pytz.utc.localize(current_time)

        local_time = current_time.astimezone(tz)

        day_index = local_time.weekday()
        day_name = ScheduleEvaluator.DAYS_OF_WEEK[day_index]

        day_schedule = schedule.get(day_name, [])
        if not day_schedule:
            return False

        current_time_only = local_time.time()

        for window in day_schedule:
            start_str = window.get("start")
            end_str = window.get("end")

            if not start_str or not end_str:
                continue

            try:
                start_time = ScheduleEvaluator._parse_time(start_str)
                end_time = ScheduleEvaluator._parse_time(end_str)

                if start_time <= current_time_only <= end_time:
                    return True
            except ValueError:
                continue

        return False

    @staticmethod
    def _is_running_time_cron(
        schedule: Dict,
        timezone_str: str,
        current_time: Optional[datetime] = None,
    ) -> bool:
        """
        Evaluate a cron-based schedule.

        Uses two cron expressions (start and stop) to determine if the
        current time falls within a running window. Compares the most
        recent start trigger against the most recent stop trigger —
        if start fired more recently, the instance should be running.
        """
        if current_time is None:
            current_time = datetime.now(timezone.utc)

        try:
            tz = pytz.timezone(timezone_str)
        except pytz.UnknownTimeZoneError:
            return False

        if current_time.tzinfo is None:
            current_time = pytz.utc.localize(current_time)

        # Evaluate cron in the policy's timezone
        local_time = current_time.astimezone(tz)
        # croniter works with naive datetimes
        local_naive = local_time.replace(tzinfo=None)

        start_expr = schedule.get("start", "")
        stop_expr = schedule.get("stop", "")

        if not start_expr or not stop_expr:
            return False

        try:
            start_iter = croniter(start_expr, local_naive)
            stop_iter = croniter(stop_expr, local_naive)

            last_start = start_iter.get_prev(datetime)
            last_stop = stop_iter.get_prev(datetime)

            return last_start > last_stop
        except (ValueError, KeyError):
            return False

    @staticmethod
    def _parse_time(time_str: str) -> time:
        """Parse time string in HH:MM format."""
        parts = time_str.split(":")
        if len(parts) != 2:
            raise ValueError(f"Invalid time format: {time_str}")

        hour = int(parts[0])
        minute = int(parts[1])

        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            raise ValueError(f"Invalid time values: {time_str}")

        return time(hour=hour, minute=minute)

    @staticmethod
    def validate_schedule(
        schedule: Dict,
        schedule_type: str = "weekly",
    ) -> List[str]:
        """
        Validate a schedule dictionary.

        Returns:
            List of error messages (empty if valid)
        """
        if schedule_type == "cron":
            return ScheduleEvaluator._validate_cron_schedule(schedule)
        return ScheduleEvaluator._validate_weekly_schedule(schedule)

    @staticmethod
    def _validate_weekly_schedule(schedule: Dict) -> List[str]:
        """Validate a weekly time-window schedule."""
        errors = []

        if not isinstance(schedule, dict):
            return ["Schedule must be a dictionary"]

        for day, windows in schedule.items():
            if day not in ScheduleEvaluator.DAYS_OF_WEEK:
                errors.append(f"Invalid day: {day}")
                continue

            if not isinstance(windows, list):
                errors.append(f"Windows for {day} must be a list")
                continue

            for i, window in enumerate(windows):
                if not isinstance(window, dict):
                    errors.append(f"Window {i} for {day} must be a dictionary")
                    continue

                if "start" not in window or "end" not in window:
                    errors.append(f"Window {i} for {day} missing 'start' or 'end'")
                    continue

                try:
                    start_time = ScheduleEvaluator._parse_time(window["start"])
                    end_time = ScheduleEvaluator._parse_time(window["end"])

                    if start_time >= end_time:
                        errors.append(
                            f"Window {i} for {day}: start time must be before end time")
                except ValueError as e:
                    errors.append(f"Window {i} for {day}: {str(e)}")

        return errors

    @staticmethod
    def _validate_cron_schedule(schedule: Dict) -> List[str]:
        """Validate a cron schedule with start and stop expressions."""
        errors = []

        if not isinstance(schedule, dict):
            return ["Schedule must be a dictionary"]

        if "start" not in schedule:
            errors.append("Cron schedule missing 'start' expression")
        if "stop" not in schedule:
            errors.append("Cron schedule missing 'stop' expression")

        if errors:
            return errors

        for field in ("start", "stop"):
            expr = schedule[field]
            if not isinstance(expr, str) or not expr.strip():
                errors.append(f"Cron '{field}' must be a non-empty string")
                continue
            if not croniter.is_valid(expr):
                errors.append(f"Invalid cron expression for '{field}': {expr}")

        return errors

    @staticmethod
    def calculate_cron_running_hours_per_week(schedule: Dict) -> float:
        """
        Estimate running hours per week from a cron schedule.

        Simulates a full week of cron triggers starting from a fixed
        reference point to compute total running hours.
        """
        from datetime import timedelta

        start_expr = schedule.get("start", "")
        stop_expr = schedule.get("stop", "")
        if not start_expr or not stop_expr:
            return 0.0

        try:
            # Use a fixed reference Monday at midnight for consistency
            ref = datetime(2026, 1, 5, 0, 0)  # A Monday
            week_end = ref + timedelta(weeks=1)

            start_iter = croniter(start_expr, ref)
            stop_iter = croniter(stop_expr, ref)

            # Collect all start and stop events in the week
            events: List[tuple] = []
            while True:
                nxt = start_iter.get_next(datetime)
                if nxt >= week_end:
                    break
                events.append((nxt, "start"))
            while True:
                nxt = stop_iter.get_next(datetime)
                if nxt >= week_end:
                    break
                events.append((nxt, "stop"))

            events.sort(key=lambda e: e[0])

            running_seconds = 0.0
            run_start = None

            for evt_time, evt_type in events:
                if evt_type == "start" and run_start is None:
                    run_start = evt_time
                elif evt_type == "stop" and run_start is not None:
                    running_seconds += (evt_time - run_start).total_seconds()
                    run_start = None

            # If still running at week end, count up to week_end
            if run_start is not None:
                running_seconds += (week_end - run_start).total_seconds()

            return running_seconds / 3600.0
        except (ValueError, KeyError):
            return 0.0
