"""Telegram must not present CSV-only fixtures as actionable predictions."""
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
import commands

class FixtureSafetyTests(unittest.TestCase):
    def setUp(self):
        now=datetime.now(timezone.utc)
        self.snapshot={
            "created":now.isoformat(),
            "rows":[
                {"home":"Unverified FC","away":"Other FC","date":(now+timedelta(days=3)).date().isoformat(),
                 "kickoff":None,"market":"ТБ 0.5 2Т","p":.99,"selected":True,"group":"goals"},
                {"home":"SV Werder Bremen","away":"Hamburger SV","date":now.date().isoformat(),
                 "kickoff":(now+timedelta(hours=2)).isoformat(),"market":"ТБ 0.5 2Т",
                 "p":.75,"selected":True,"group":"goals"},
            ]
        }

    def test_top_omits_unverified_future_csv_rows(self):
        with patch.object(commands,"load",return_value=self.snapshot):
            output=commands.answer("/top")
        self.assertNotIn("Unverified FC",output)
        self.assertIn("Вердер — Гамбург",output)

    def test_stale_snapshot_is_rejected(self):
        self.snapshot["created"]=(datetime.now(timezone.utc)-timedelta(hours=32)).isoformat()
        with patch.object(commands,"load",return_value=self.snapshot):
            output=commands.answer("/top")
        self.assertIn("устарела",output)

    def test_naive_kickoff_is_ignored(self):
        self.snapshot["rows"][1]["kickoff"]=(datetime.now()+timedelta(hours=3)).isoformat()
        with patch.object(commands,"load",return_value=self.snapshot):
            output=commands.answer("/top")
        self.assertNotIn("Вердер — Гамбург",output)

if __name__=="__main__":
    unittest.main()
