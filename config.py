import os

# Секретный топик Ntfy (можно задать через GitHub Secrets или поменять прямо здесь)
NTFY_TOPIC = os.getenv("NTFY_TOPIC") or "bolha_secret_alerts_59231"

# Ссылки на категории Bolha.com (обязательно с параметром sort=new для свежих объявлений)
TARGET_URLS = [
    "https://www.bolha.com/search/?keywords=telefon&sort=new",
    "https://www.bolha.com/search/?keywords=prenosnik&sort=new",
    "https://www.bolha.com/search/?keywords=playstation&sort=new"
]

# Настройки цен в EUR
MIN_PRICE = 15.0
MAX_PRICE = 800.0

# Триггеры для поиска (выгодные сделки, ремонт, срочность)
POSITIVE_KEYWORDS = [
    "garancija", "slaba baterija", "menjava baterije", "menjava stekla", "počeno steklo", 
    "praska", "brez polnilca", "ne prepozna diska", "potrebno očistiti",
    "nujno", "ugodno", "zaradi neuporabe", "menjam", "hitro"
]

# Стоп-слова (мусор, трупы, заблокированные устройства)
STOP_WORDS = [
    "zaklenjen", "icloud", "matična plošča", "zalit", "ne daje znakov", 
    "za dele", "ponaredek", "replika", "fake", "kopija"
]

# Настройки сети
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "sl-SI,sl;q=0.9,en-US;q=0.8,en;q=0.7"
}
TIMEOUT = 15
MAX_RETRIES = 3

# Путь к файлу состояния
STATE_FILE = "seen_ids.json"
MAX_SEEN_IDS = 2000  # Защита от бесконечного разрастания JSON
