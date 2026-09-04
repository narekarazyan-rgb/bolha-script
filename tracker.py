import os
import sys
import re
import json
import time
import logging
import requests
from bs4 import BeautifulSoup
import config

sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout
)

TOPIC = os.getenv("NTFY_TOPIC") or getattr(config, "NTFY_TOPIC", None) or "bolha_secret_alerts_59231"
GEMINI_KEY = os.getenv("GEMINI_API_KEY") or getattr(config, "GEMINI_API_KEY", None) or ""
GEMINI_MODEL = "gemini-3.6-flash"

def load_seen_ids():
    if os.path.exists(config.STATE_FILE):
        try:
            with open(config.STATE_FILE, "r", encoding="utf-8") as f:
                return set(json.load(f))
        except Exception as e:
            logging.error(f"Ошибка загрузки seen_ids: {e}")
    return set()

def save_seen_ids(seen_ids):
    ids_list = sorted(list(seen_ids))[-config.MAX_SEEN_IDS:]
    with open(config.STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(ids_list, f, indent=4)

def parse_price(price_str):
    if not price_str or "dogovor" in price_str.lower():
        return 0.0
    cleaned = re.sub(r"[^\d,]", "", price_str.replace(".", ""))
    cleaned = cleaned.replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return 0.0

def analyze_deal_with_ai(title, price, description):
    """Оценка лота через Gemini 3.6 Flash без обрезки текста."""
    if not GEMINI_KEY:
        return "⚠️ ИИ отключен (нет ключа GEMINI_API_KEY)"

    prompt = (
        f"Ты эксперт по перепродаже и компонентному ремонту техники в Словении.\n"
        f"Оцени объявление с Bolha.com:\n"
        f"Товар: {title}\n"
        f"Цена: {price} EUR\n"
        f"Описание продавца: {description}\n\n"
        f"Дай емкий анализ на русском языке:\n"
        f"1. Вердикт: [БРАТЬ / ДУМАТЬ / МУСОР]\n"
        f"2. Суть: выгода, примерная сложность/цена ремонта, риск скрытого брака, ликвидно ли на рынке Словении."
    )

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_KEY}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 500
        }
    }

    try:
        resp = requests.post(url, json=payload, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            return data["candidates"][0]["content"]["parts"][0]["text"].strip()
        else:
            logging.warning(f"Gemini вернул статус {resp.status_code}: {resp.text}")
            return f"⚠️ Ошибка Gemini API ({resp.status_code})"
    except Exception as e:
        logging.error(f"Сбой запроса к ИИ: {e}")
        return "⚠️ Таймаут генерации ответа"

def send_ntfy_push(title, message, url, tags):
    payload = {
        "topic": TOPIC,
        "title": title,
        "message": message,
        "tags": tags,
        "priority": 4,
        "click": url
    }
    try:
        response = requests.post("https://ntfy.sh/", json=payload, timeout=10)
        response.raise_for_status()
        logging.info(f"✅ Пуш отправлен: {title}")
    except Exception as e:
        logging.error(f"❌ Сбой пуша: {e}")

def process_item(item, seen_ids):
    title_elem = item.select_one("h3.entity-title a")
    if not title_elem:
        return

    title = title_elem.text.strip()
    link = "https://www.bolha.com" + title_elem.get("href", "")
    
    match_id = re.search(r"-(\d+)/?$", link)
    if not match_id:
        return
    item_id = match_id.group(1)

    if item_id in seen_ids:
        return

    seen_ids.add(item_id)

    price_elem = item.select_one("strong.price")
    price_str = price_elem.text.strip() if price_elem else "0"
    price = parse_price(price_str)

    desc_elem = item.select_one("div.entity-description-main")
    description = desc_elem.text.strip() if desc_elem else ""

    location_elem = item.select_one("span.entity-pub-location")
    location = location_elem.text.strip() if location_elem else "Neznano"

    if not (config.MIN_PRICE <= price <= config.MAX_PRICE):
        return

    full_text = f"{title} {description}".lower()

    for stop_word in config.STOP_WORDS:
        if stop_word in full_text:
            return

    found_triggers = [w for w in config.POSITIVE_KEYWORDS if w in full_text]
    
    if found_triggers:
        logging.info(f"🔥 НАЙДЕН ЛОТ: {title} (€{price}) | Триггеры: {found_triggers}")
        
        # Получаем полный вердикт от Gemini 3.6 Flash
        ai_verdict = analyze_deal_with_ai(title, price, description)

        push_title = f"{title} — €{price}"
        push_message = (
            f"📍 {location}\n"
            f"🎯 Триггер: {', '.join(found_triggers)}\n\n"
            f"🤖 ВЕРДИКТ GEMINI:\n{ai_verdict}"
        )
        send_ntfy_push(push_title, push_message, link, tags=["robot", "wrench"])

def main():
    seen_ids = load_seen_ids()
    new_items_found = False

    for url in config.TARGET_URLS:
        logging.info(f"Скрапинг: {url}")
        for attempt in range(config.MAX_RETRIES):
            try:
                response = requests.get(url, headers=config.HEADERS, timeout=config.TIMEOUT)
                response.raise_for_status()
                
                soup = BeautifulSoup(response.text, "html.parser")
                items = soup.select("li.EntityList-item article.entity-body")
                
                for item in items:
                    process_item(item, seen_ids)
                
                new_items_found = True
                break
            except requests.exceptions.RequestException as e:
                logging.warning(f"Ошибка {url} (попытка {attempt+1}): {e}")
                time.sleep(3)
        time.sleep(1)

    if new_items_found:
        save_seen_ids(seen_ids)
        logging.info("База обновлена.")

if __name__ == "__main__":
    main()
