import os
import re
import json
import time
import logging
import requests
from bs4 import BeautifulSoup
import config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

TOPIC = os.getenv("NTFY_TOPIC") or getattr(config, "NTFY_TOPIC", None) or "bolha_secret_alerts_59231"
GEMINI_KEY = os.getenv("GEMINI_API_KEY") or getattr(config, "GEMINI_API_KEY", None) or ""

def load_seen_ids():
    if os.path.exists(config.STATE_FILE):
        try:
            with open(config.STATE_FILE, "r", encoding="utf-8") as f:
                return set(json.load(f))
        except Exception as e:
            logging.error(f"Failed to load seen_ids: {e}")
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
    """Анализирует объявление через Gemini 2.5 Flash API."""
    if not GEMINI_KEY:
        return "⚠️ ИИ отключен (не задан GEMINI_API_KEY в Secrets)"

    prompt = (
        f"Ты эксперт по перепродаже и ремонту техники в Словении. "
        f"Оцени объявление с Bolha.com:\n"
        f"Название: {title}\n"
        f"Цена: {price} EUR\n"
        f"Описание: {description}\n\n"
        f"Дай предельно краткий вердикт в 2-3 строках:\n"
        f"1. Вердикт: БРАТЬ / ДУМАТЬ / МУСОР\n"
        f"2. Оценка выгоды/ремонта (стоит ли чинить или перепродавать, нет ли скрытого подвоха)."
    )

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_KEY}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.2, "maxOutputTokens": 150}
    }

    try:
        resp = requests.post(url, json=payload, timeout=12)
        if resp.status_code == 200:
            data = resp.json()
            return data["candidates"][0]["content"]["parts"][0]["text"].strip()
        else:
            logging.warning(f"Gemini API returned status {resp.status_code}: {resp.text}")
            return "⚠️ Ошибка ответа AI API"
    except Exception as e:
        logging.error(f"AI Analysis failed: {e}")
        return "⚠️ Таймаут/сбой AI анализа"

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
        logging.info(f"Push sent: {title}")
    except Exception as e:
        logging.error(f"Push failed: {e}")

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

    # Проверка стоп-слов
    for stop_word in config.STOP_WORDS:
        if stop_word in full_text:
            return

    # Проверка ключевых триггеров
    found_triggers = [w for w in config.POSITIVE_KEYWORDS if w in full_text]
    
    if found_triggers:
        logging.info(f"MATCH: {title} (€{price}) | Triggers: {found_triggers}")
        
        # Запрос к ИИ для валидации лота
        ai_assessment = analyze_deal_with_ai(title, price, description)

        push_title = f"{title} — €{price}"
        push_message = (
            f"📍 {location}\n"
            f"🎯 Триггеры: {', '.join(found_triggers)}\n\n"
            f"🤖 ВЕРДИКТ ИИ:\n{ai_assessment}"
        )
        send_ntfy_push(push_title, push_message, link, tags=["robot", "wrench"])

def main():
    seen_ids = load_seen_ids()
    new_items_found = False

    for url in config.TARGET_URLS:
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
                time.sleep(3)
        time.sleep(1)

    if new_items_found:
        save_seen_ids(seen_ids)

if __name__ == "__main__":
    main()
