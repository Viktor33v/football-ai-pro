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
    def test_v26_filter_integration(self):
        self.snap["calibration"]={"markets":{"Обе забьют":[[.65,1]]*195+[[.65,0]]*105}}
        with patch.object(commands,"load",return_value=self.snap):
            out=commands.filter_predictions("оз 60-80")
            self.assertIn("195/300 (65.0%)",out)
            self.assertIn("95% интервал",out)
            if self.same_day:
                self.assertNotIn("🟢 Прошёл фильтр",out)
                self.assertIn("Предварительный отбор:",out)
                self.assertIn("Индекс V26.1:",out)
                self.assertIn("Калибровка согласуется",out)

    def test_parse(self):
        with patch.object(commands,"load",return_value=self.snap):
            self.assertIn("Неверный диапазон",commands.filter_predictions("оз 90-60"))
            self.assertIn("Рынок не распознан",commands.filter_predictions("неизвестно 70"))
            out=commands.filter_predictions("оз 60-80")
            self.assertIn("Обе забьют",out)
            if self.same_day:
                self.assertIn("72.0%",out)
                self.assertIn("Предварительный отбор: ✓ Базовые условия выполнены",out)
                self.assertIn("425",out)
                self.assertIn("Brier модель/база: 0.2300/0.2400",out)
            out=commands.filter_predictions("тм 2.5 30-40")
            if self.same_day:
                self.assertIn("32.0%",out)
                self.assertIn("⚪ Недостаточно данных",out)
    def test_odds_break_even(self):
        self.assertIn("⛔ Пропустить",commands.odds("90 1.07"))
        self.assertIn("93.5%",commands.odds("90 1.07"))
        self.assertIn("преимущество не подтверждено",commands.odds("95 1.07"))
    def test_forward_command_dispatch(self):
        with patch.object(commands,"load",return_value={}):
            self.assertIn("V28",commands.answer("/forward"))
    def test_russian_team_display(self):
        from team_ru import display
        self.assertEqual(display('Feyenoord Rotterdam'),'Фейеноорд')
        self.assertEqual(display('SBV Excelsior'),'Эксельсиор')
        self.assertEqual(display('Unknown FC'),'Unknown FC')
    def test_btts_seven_day_window(self):
        future=(datetime.now(timezone.utc)+timedelta(days=3)).isoformat()
        self.snap["rows"][0]["kickoff"]=future
        self.snap["rows"][1]["kickoff"]=future
        with patch.object(commands,"load",return_value=self.snap):
            result=commands.filter_predictions("обе забьют 0-100",days=7)
            self.assertIn("ближайшие 7 дней",result)
            self.assertIn("Обе забьют: 72.0%",result)
            self.assertNotIn("ТБ 0.5 2Т = минимум",result)
            compact=commands.filter_predictions("обе забьют 0-100",days=7,compact=True)
            self.assertIn("Краткий обзор: топ-10",compact)
            self.assertIn("A — B | 72.0%",compact)
            daily=commands.filter_predictions("обе забьют 0-100")
            self.assertNotIn("Обе забьют: 72.0%",daily)
    def test_reliable_button_and_strict_rejection(self):
        labels=[button["text"] for row in commands.keyboard()["keyboard"] for button in row]
        self.assertIn("Надёжные прогнозы",labels)
        self.assertEqual(commands.MENU["Надёжные прогнозы"],"/reliable")
        self.snap["diagnostics"]["Обе забьют"]={"n":1015,"model":0.2429,"baseline":0.2439}
        with patch.object(commands,"load",return_value=self.snap):
            out=commands.answer("Надёжные прогнозы")
        self.assertIn("строгий отбор",out)
        self.assertIn("нет прогнозов, прошедших строгий отбор",out)

    def test_btts_keyboard_button(self):
        labels=[button["text"] for row in commands.keyboard()["keyboard"] for button in row]
        self.assertIn("Обе забьют",labels)
        self.assertEqual(commands.MENU["Обе забьют"],"/btts")
        with patch.object(commands,"filter_predictions",return_value="BTTS report") as report:
            self.assertEqual(commands.answer("Обе забьют"),"BTTS report")
            report.assert_called_once_with("обе забьют 0-100",days=7,compact=True)
    def test_btts_requires_meaningful_brier_gain(self):
        row=dict(self.snap["rows"][0]); row["sample"]=[20,20]; row["selected"]=True
        self.snap["diagnostics"]["Обе забьют"]={"n":814,"model":0.2447,"baseline":0.2448}
        self.assertFalse(commands.eligible(row,self.snap))
        self.assertIn("преимущество не подтверждено"," ".join(commands.reasons(row,self.snap)))
        self.snap["diagnostics"]["Обе забьют"]["model"]=0.2400
        self.assertTrue(commands.eligible(row,self.snap))
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
