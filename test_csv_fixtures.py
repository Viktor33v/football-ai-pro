"""Safety tests for date-only open-matchday fixture feeds."""
import unittest
from datetime import date, timedelta
from corners import valid_future_fixture, unique_fixture_rows, unique_result_rows

class FixtureDateTests(unittest.TestCase):
    def setUp(self):
        self.today=date(2026,11,23)
        self.row={"date":"2026-11-24","home":"Home FC","away":"Away FC"}

    def test_accepts_future_week_fixture(self):
        self.assertTrue(valid_future_fixture(self.row,self.today,set()))

    def test_rejects_today_and_past(self):
        for d in ("2026-11-23","2026-11-22"):
            self.assertFalse(valid_future_fixture({**self.row,"date":d},self.today,set()))

    def test_rejects_outside_seven_days(self):
        self.assertFalse(valid_future_fixture({**self.row,"date":"2026-12-01"},self.today,set()))

    def test_rejects_bad_date_or_teams(self):
        for row in ({**self.row,"date":"2026-11-99"},
                    {**self.row,"date":"not-a-date"},
                    {**self.row,"home":""},
                    {**self.row,"away":"Home FC"},
                    {"date":"2026-11-24","home":"Home FC"}):
            self.assertFalse(valid_future_fixture(row,self.today,set()))

    def test_duplicate_fixtures_are_all_excluded(self):
        duplicate={**self.row}
        other={**self.row,"away":"Different FC"}
        self.assertEqual(unique_fixture_rows([self.row,duplicate,other]),[other])

    def test_duplicate_history_is_not_used_for_training(self):
        first={**self.row,"home_corners":"5","away_corners":"3"}
        conflicting={**first,"home_corners":"9"}
        clean={**first,"date":"2026-11-22"}
        self.assertEqual(unique_result_rows([first,conflicting,clean]),[clean])

    def test_single_fixture_is_preserved(self):
        self.assertEqual(unique_fixture_rows([self.row]),[self.row])

    def test_rejects_already_played_fixture(self):
        seen={("2026-11-24","Home FC","Away FC")}
        self.assertFalse(valid_future_fixture(self.row,self.today,seen))

if __name__=="__main__":
    unittest.main()
