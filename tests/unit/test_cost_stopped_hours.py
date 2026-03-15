import pytest

from app.services.cost_calculator import CostCalculator


@pytest.fixture
def calculator():
    # calculate_stopped_hours_per_week is sync and never touches db
    return CostCalculator(db=None)


class TestCalculateStoppedHoursPerWeek:
    def test_mon_fri_9_to_17(self, calculator):
        schedule = {
            day: [{"start": "09:00", "end": "17:00"}]
            for day in ["monday", "tuesday", "wednesday", "thursday", "friday"]
        }
        # 5 days × 8 h = 40 running → 168 − 40 = 128 stopped
        assert calculator.calculate_stopped_hours_per_week(schedule) == 128.0

    def test_empty_schedule(self, calculator):
        assert calculator.calculate_stopped_hours_per_week({}) == 168.0

    def test_single_2h_window(self, calculator):
        schedule = {"monday": [{"start": "10:00", "end": "12:00"}]}
        assert calculator.calculate_stopped_hours_per_week(schedule) == 166.0

    def test_multiple_windows_one_day(self, calculator):
        schedule = {"monday": [
            {"start": "08:00", "end": "10:00"},
            {"start": "14:00", "end": "16:00"},
        ]}
        # 2 + 2 = 4 running → 164 stopped
        assert calculator.calculate_stopped_hours_per_week(schedule) == 164.0

    def test_full_week_max_windows(self, calculator):
        # 00:00-23:59 = 23 + 59/60 hours per day × 7 days
        schedule = {
            day: [{"start": "00:00", "end": "23:59"}]
            for day in ["monday", "tuesday", "wednesday", "thursday", "friday",
                        "saturday", "sunday"]
        }
        expected_stopped = 168.0 - 7 * (23 + 59 / 60.0)
        assert calculator.calculate_stopped_hours_per_week(schedule) == pytest.approx(expected_stopped, abs=0.01)
