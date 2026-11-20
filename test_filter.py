import unittest
from unittest.mock import patch
from datetime import datetime,timezone,timedelta
import commands

class FilterTests(unittest.TestCase):
    def setUp(self):
        now=datetime.now(timezone.utc)
        self.k=(now+timedelta(hours=1)).isoformat()
        # Test only when the next hour is still the same Bishkek calendar day.
        self.same_day=(now+timedelta(hours=1)).astimezone(timezone(timedelta(hours=6))).date()==now.astimezone(timezone(timedelta(hours=6))).date()
        self.snap={"created":now.isoformat(),"diagnostics":{"Обе забьют":{"n":425,"model":.23,"baseline":.24},"ТБ 2.5":{"n":425,"model":.24,"baseline":.25}},
                   "rows":[{"home":"A","away":"B","kickoff":self.k,"date":now.date().isoformat(),"group":"goals","market":"Обе забьют","p":.72,"selected":True,"sample":[20,20]},
                           {"home":"A","away":"B","kickoff":self.k,"date":now.date().isoformat(),"group":"goals","market":"ТБ 2.5","p":.68,"selected":True,"sample":[20,20]}]}
    def test_parse(self):
        with patch.object(commands,"load",return_value=self.snap):
            self.assertIn("Неверный диапазон",commands.filter_predictions("оз 90-60"))
            self.assertIn("Рынок не распознан",commands.filter_predictions("неизвестно 70"))
            out=commands.filter_predictions("оз 60-80")
            self.assertIn("Обе забьют",out)
            if self.same_day:
                self.assertIn("72.0%",out)
                self.assertIn("🟢 Прошёл фильтр",out)
                self.assertIn("425",out)
                self.assertIn("Brier",out)
            out=commands.filter_predictions("тм 2.5 30-40")
            if self.same_day:
                self.assertIn("32.0%",out)
                self.assertIn("⚪ Недостаточно данных",out)
    def test_quality(self):
        self.snap["rows"][0]["sample"]=[3,20]
        with patch.object(commands,"load",return_value=self.snap):
            out=commands.filter_predictions("обе забьют до 80")
            if self.same_day: self.assertIn("⚪ Недостаточно данных",out)
        self.snap["rows"][0]["sample"]=[20,20]
        self.snap["diagnostics"]["Обе забьют"]["model"]=.26
        with patch.object(commands,"load",return_value=self.snap):
            out=commands.filter_predictions("обе забьют от 60")
            if self.same_day: self.assertIn("🟡 Не прошёл фильтр",out)

if __name__=="__main__":
    unittest.main()
