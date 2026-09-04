import os

NTFY_TOPIC = os.getenv("NTFY_TOPIC") or "bolha_secret_alerts_59231"
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or ""

# Целевые поисковые категории (без мусора вроде мебели и одежды)
TARGET_URLS = [
    "https://www.bolha.com/search/?keywords=iphone&sort=new",
    "https://www.bolha.com/search/?keywords=samsung+galaxy&sort=new",
    "https://www.bolha.com/search/?keywords=prenosnik&sort=new",
    "https://www.bolha.com/search/?keywords=playstation+5&sort=new",
    "https://www.bolha.com/search/?keywords=rtx&sort=new"
]

MIN_PRICE = 20.0
MAX_PRICE = 750.0

# Боевые триггеры: дефекты, легкий ремонт, срочность, торг
POSITIVE_KEYWORDS = [
    # Дефекты экрана и корпуса
    "počeno steklo", "poceno steklo", "razbito steklo", "menjava stekla",
    "praska", "praske", "menjan ekran", "menjava ekrana", "črta na zaslonu",
    # Аккумулятор и питание
    "slaba baterija", "slabša baterija", "menjava baterije", "brez polnilca", "brez adapterja",
    # Проблемы софта/чистки/стиков
    "potrebno očistiti", "potrebno ocistiti", "ne prepozna diska", "drift", "drifta",
    # Срочная продажа и дисконт
    "nujno", "ugodno", "zaradi neuporabe", "zaradi nakupa novega", "menjam za", 
    "hitra prodaja", "ne rabim", "simbolična cena"
]

# Стоп-слова: отсекаем перекупов, скупку, кирпичи и подделки
STOP_WORDS = [
    # Скупка и реклама
    "odkup", "odkupujem", "kupim", "iščem", "iscem",
    # Невосстановимый брак / кирпичи
    "zaklenjen icloud", "icloud zaklenjen", "zaklenjen na", "matična plošča", 
    "maticna plosca", "zalit", "prišel v stik z vodo", "ne daje znakov", 
    "za dele", "za kosov", "samo deli", "ne prižge", "ne prizge",
    # Реплики и подделки
    "ponaredek", "replika", "fake", "kopija"
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "sl-SI,sl;q=0.9,en;q=0.8"
}
TIMEOUT = 15
MAX_RETRIES = 3
STATE_FILE = "seen_ids.json"
MAX_SEEN_IDS = 2500
