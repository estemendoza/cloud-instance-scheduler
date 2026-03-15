from datetime import datetime, time, timezone

import pytest

from app.services.schedule import ScheduleEvaluator

MON_SCHEDULE = {"monday": [{"start": "09:00", "end": "18:00"}]}

# Cron: weekdays 9am start, 6pm stop
CRON_WEEKDAY = {"start": "0 9 * * 1-5", "stop": "0 18 * * 1-5"}


def _monday_utc(hour, minute=0):
    """2026-02-02 is a Monday."""
    return datetime(2026, 2, 2, hour, minute, tzinfo=timezone.utc)


class TestIsRunningTime:
    def test_within_window(self):
        assert ScheduleEvaluator.is_running_time(MON_SCHEDULE, "UTC", _monday_utc(12)) is True

    def test_outside_window(self):
        assert ScheduleEvaluator.is_running_time(MON_SCHEDULE, "UTC", _monday_utc(20)) is False

    def test_no_schedule_for_day(self):
        # 2026-02-07 is a Saturday
        saturday = datetime(2026, 2, 7, 12, 0, tzinfo=timezone.utc)
        assert ScheduleEvaluator.is_running_time(MON_SCHEDULE, "UTC", saturday) is False

    def test_invalid_timezone(self):
        assert ScheduleEvaluator.is_running_time(MON_SCHEDULE, "Not/A/Real/Zone", _monday_utc(12)) is False

    def test_boundary_at_start(self):
        assert ScheduleEvaluator.is_running_time(MON_SCHEDULE, "UTC", _monday_utc(9, 0)) is True

    def test_boundary_at_end(self):
        assert ScheduleEvaluator.is_running_time(MON_SCHEDULE, "UTC", _monday_utc(18, 0)) is True

    def test_one_minute_before_start(self):
        assert ScheduleEvaluator.is_running_time(MON_SCHEDULE, "UTC", _monday_utc(8, 59)) is False

    def test_one_minute_after_end(self):
        assert ScheduleEvaluator.is_running_time(MON_SCHEDULE, "UTC", _monday_utc(18, 1)) is False

    def test_multiple_windows_same_day(self):
        schedule = {"monday": [
            {"start": "08:00", "end": "10:00"},
            {"start": "14:00", "end": "16:00"},
        ]}
        assert ScheduleEvaluator.is_running_time(schedule, "UTC", _monday_utc(9)) is True
        assert ScheduleEvaluator.is_running_time(schedule, "UTC", _monday_utc(15)) is True
        assert ScheduleEvaluator.is_running_time(schedule, "UTC", _monday_utc(12)) is False

    def test_timezone_conversion(self):
        # America/New_York is UTC-5 in February.  Mon 14:00 UTC = Mon 09:00 EST.
        schedule = {"monday": [{"start": "09:00", "end": "18:00"}]}
        assert ScheduleEvaluator.is_running_time(schedule, "America/New_York", _monday_utc(14, 0)) is True


class TestValidateSchedule:
    def test_valid_schedule(self):
        schedule = {
            day: [{"start": "09:00", "end": "17:00"}]
            for day in ["monday", "tuesday", "wednesday", "thursday", "friday"]
        }
        assert ScheduleEvaluator.validate_schedule(schedule) == []

    def test_invalid_day_name(self):
        errors = ScheduleEvaluator.validate_schedule({"mondy": [{"start": "09:00", "end": "17:00"}]})
        assert any("Invalid day" in e for e in errors)

    def test_windows_not_list(self):
        errors = ScheduleEvaluator.validate_schedule({"monday": "bad"})
        assert any("must be a list" in e for e in errors)

    def test_missing_start(self):
        errors = ScheduleEvaluator.validate_schedule({"monday": [{"end": "18:00"}]})
        assert any("missing" in e for e in errors)

    def test_missing_end(self):
        errors = ScheduleEvaluator.validate_schedule({"monday": [{"start": "09:00"}]})
        assert any("missing" in e for e in errors)

    def test_start_equals_end(self):
        errors = ScheduleEvaluator.validate_schedule({"monday": [{"start": "09:00", "end": "09:00"}]})
        assert any("before end" in e for e in errors)

    def test_start_after_end(self):
        errors = ScheduleEvaluator.validate_schedule({"monday": [{"start": "18:00", "end": "09:00"}]})
        assert any("before end" in e for e in errors)

    def test_malformed_time_string(self):
        errors = ScheduleEvaluator.validate_schedule({"monday": [{"start": "abc", "end": "18:00"}]})
        assert len(errors) > 0


class TestParseTime:
    def test_valid(self):
        assert ScheduleEvaluator._parse_time("09:00") == time(9, 0)

    def test_midnight(self):
        assert ScheduleEvaluator._parse_time("00:00") == time(0, 0)

    def test_end_of_day(self):
        assert ScheduleEvaluator._parse_time("23:59") == time(23, 59)

    def test_invalid_hour_25(self):
        with pytest.raises(ValueError):
            ScheduleEvaluator._parse_time("25:00")

    def test_invalid_minute_60(self):
        with pytest.raises(ValueError):
            ScheduleEvaluator._parse_time("12:60")

    def test_no_colon(self):
        with pytest.raises(ValueError):
            ScheduleEvaluator._parse_time("0900")

    def test_single_digit_hour(self):
        # int("9") succeeds; documents the edge-case behaviour
        assert ScheduleEvaluator._parse_time("9:00") == time(9, 0)


class TestCronIsRunningTime:
    """Tests for cron-based schedule evaluation."""

    def test_within_cron_window(self):
        # Monday 12:00 UTC — between 9am start and 6pm stop
        assert ScheduleEvaluator.is_running_time(
            CRON_WEEKDAY, "UTC", _monday_utc(12), schedule_type="cron") is True

    def test_outside_cron_window(self):
        # Monday 20:00 UTC — after 6pm stop
        assert ScheduleEvaluator.is_running_time(
            CRON_WEEKDAY, "UTC", _monday_utc(20), schedule_type="cron") is False

    def test_before_first_start(self):
        # Monday 7:00 UTC — before 9am start
        assert ScheduleEvaluator.is_running_time(
            CRON_WEEKDAY, "UTC", _monday_utc(7), schedule_type="cron") is False

    def test_at_start_time(self):
        # Monday exactly 9:00 — start just fired
        assert ScheduleEvaluator.is_running_time(
            CRON_WEEKDAY, "UTC", _monday_utc(9, 1), schedule_type="cron") is True

    def test_at_stop_time(self):
        # Monday 18:01 — stop just fired
        assert ScheduleEvaluator.is_running_time(
            CRON_WEEKDAY, "UTC", _monday_utc(18, 1), schedule_type="cron") is False

    def test_weekend_not_running(self):
        # Saturday 12:00 UTC — cron is 1-5 (Mon-Fri only)
        saturday = datetime(2026, 2, 7, 12, 0, tzinfo=timezone.utc)
        assert ScheduleEvaluator.is_running_time(
            CRON_WEEKDAY, "UTC", saturday, schedule_type="cron") is False

    def test_cron_with_timezone(self):
        # America/New_York is UTC-5 in Feb.
        # Mon 14:00 UTC = Mon 09:00 EST (start just fired) → running
        assert ScheduleEvaluator.is_running_time(
            CRON_WEEKDAY, "America/New_York", _monday_utc(14, 1),
            schedule_type="cron") is True

    def test_cron_invalid_timezone(self):
        assert ScheduleEvaluator.is_running_time(
            CRON_WEEKDAY, "Not/Real", _monday_utc(12),
            schedule_type="cron") is False

    def test_daily_schedule(self):
        # Every day 6am-10pm
        daily = {"start": "0 6 * * *", "stop": "0 22 * * *"}
        saturday = datetime(2026, 2, 7, 12, 0, tzinfo=timezone.utc)
        assert ScheduleEvaluator.is_running_time(
            daily, "UTC", saturday, schedule_type="cron") is True

    def test_missing_start_expression(self):
        assert ScheduleEvaluator.is_running_time(
            {"stop": "0 18 * * 1-5"}, "UTC", _monday_utc(12),
            schedule_type="cron") is False

    def test_missing_stop_expression(self):
        assert ScheduleEvaluator.is_running_time(
            {"start": "0 9 * * 1-5"}, "UTC", _monday_utc(12),
            schedule_type="cron") is False


class TestValidateCronSchedule:
    """Tests for cron schedule validation."""

    def test_valid_cron(self):
        errors = ScheduleEvaluator.validate_schedule(CRON_WEEKDAY, schedule_type="cron")
        assert errors == []

    def test_missing_start(self):
        errors = ScheduleEvaluator.validate_schedule(
            {"stop": "0 18 * * 1-5"}, schedule_type="cron")
        assert any("start" in e for e in errors)

    def test_missing_stop(self):
        errors = ScheduleEvaluator.validate_schedule(
            {"start": "0 9 * * 1-5"}, schedule_type="cron")
        assert any("stop" in e for e in errors)

    def test_invalid_cron_syntax(self):
        errors = ScheduleEvaluator.validate_schedule(
            {"start": "not a cron", "stop": "0 18 * * 1-5"}, schedule_type="cron")
        assert any("Invalid cron" in e for e in errors)

    def test_empty_expression(self):
        errors = ScheduleEvaluator.validate_schedule(
            {"start": "", "stop": "0 18 * * 1-5"}, schedule_type="cron")
        assert len(errors) > 0

    def test_not_dict(self):
        errors = ScheduleEvaluator.validate_schedule("bad", schedule_type="cron")
        assert any("dictionary" in e for e in errors)


class TestCronRunningHoursPerWeek:
    """Tests for cron running hours calculation."""

    def test_weekday_9_to_18(self):
        hours = ScheduleEvaluator.calculate_cron_running_hours_per_week(CRON_WEEKDAY)
        # 9 hours * 5 days = 45
        assert hours == pytest.approx(45.0, abs=0.1)

    def test_daily_6_to_22(self):
        daily = {"start": "0 6 * * *", "stop": "0 22 * * *"}
        hours = ScheduleEvaluator.calculate_cron_running_hours_per_week(daily)
        # 16 hours * 7 days = 112
        assert hours == pytest.approx(112.0, abs=0.1)

    def test_empty_schedule(self):
        hours = ScheduleEvaluator.calculate_cron_running_hours_per_week({})
        assert hours == 0.0
