"""Russian display names for football clubs; keep original names for matching and IDs."""
import re

NAMES={
"Feyenoord Rotterdam":"Фейеноорд","SBV Excelsior":"Эксельсиор",
"FC Bayern München":"Бавария","Bayern Munich":"Бавария","1. FC Köln":"Кёльн",
"VfB Stuttgart":"Штутгарт","FC Schalke 04":"Шальке 04",
"Bayer 04 Leverkusen":"Байер","SC Paderborn 07":"Падерборн",
"Rayo Vallecano de Madrid":"Райо Вальекано","Valencia CF":"Валенсия",
"RCD Espanyol de Barcelona":"Эспаньол","FC Barcelona":"Барселона",
"Real Madrid CF":"Реал Мадрид","Club Atlético de Madrid":"Атлетико Мадрид",
"Manchester City FC":"Манчестер Сити","Manchester United FC":"Манчестер Юнайтед",
"Arsenal FC":"Арсенал","Chelsea FC":"Челси","Liverpool FC":"Ливерпуль",
"Tottenham Hotspur FC":"Тоттенхэм","Newcastle United FC":"Ньюкасл",
"Paris Saint-Germain FC":"ПСЖ","Borussia Dortmund":"Боруссия Дортмунд",
"RB Leipzig":"РБ Лейпциг","Juventus FC":"Ювентус","AC Milan":"Милан",
"FC Internazionale Milano":"Интер","SSC Napoli":"Наполи",
"PSV":"ПСВ","AFC Ajax":"Аякс","SL Benfica":"Бенфика",
"Sporting Clube de Portugal":"Спортинг","FC Porto":"Порту",
"SV Werder Bremen":"Вердер","Hamburger SV":"Гамбург",
"FC Augsburg":"Аугсбург","1. FSV Mainz 05":"Майнц",
"Go Ahead Eagles":"Гоу Эхед Иглс","Fortuna Sittard":"Фортуна Ситтард",
"Sparta Rotterdam":"Спарта Роттердам","AZ":"АЗ Алкмар",
"Villarreal CF":"Вильярреал","Bologna FC 1909":"Болонья",
"Udinese Calcio":"Удинезе","Atalanta BC":"Аталанта",
"AS Roma":"Рома","Lille OSC":"Лилль","Racing Club de Lens":"Ланс",
"Vitória SC":"Витория Гимарайнш","Red Bull Bragantino":"Ред Булл Брагантино",
}
# Display fallback deliberately preserves unknown names instead of guessing wrong clubs.
def display(name):
    if not isinstance(name,str):return name
    if name in NAMES:return NAMES[name]
    # Only case-insensitive exact matches, never substring replacement.
    for original,russian in NAMES.items():
        if name.casefold()==original.casefold():return russian
    return name
