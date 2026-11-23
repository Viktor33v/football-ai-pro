"""Russian names are display-only and must not guess unknown clubs."""
import unittest
from team_ru import display

class RussianClubNamesTests(unittest.TestCase):
    def test_known_clubs(self):
        cases={
            "Eintracht Frankfurt":"Айнтрахт Франкфурт",
            "Borussia Mönchengladbach":"Боруссия Мёнхенгладбах",
            "Athletic Club":"Атлетик Бильбао",
            "Málaga CF":"Малага",
            "1. FC Union Berlin":"Унион Берлин",
        }
        for source,expected in cases.items():
            with self.subTest(source=source):
                self.assertEqual(display(source),expected)

    def test_unknown_names_are_not_guessed(self):
        self.assertEqual(display("Unknown Town FC"),"Unknown Town FC")

    def test_case_insensitive_exact_match(self):
        self.assertEqual(display("eintracht frankfurt"),"Айнтрахт Франкфурт")

if __name__=="__main__":
    unittest.main()
