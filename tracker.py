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
        logging.info(f"✅ УСПЕШНО ОТПРАВЛЕН ПУШ в топик '{TOPIC}': {title}")
    except Exception as e:
        logging.error(f"❌ ОШИБКА ОТПРАВКИ NTFY: {e}")

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

    # Фильтр по цене
    if not (config.MIN_PRICE <= price <= config.MAX_PRICE):
        logging.info(f"  [ПРОПУСК: ЦЕНА] {price}€ вне диапазона ({config.MIN_PRICE}-{config.MAX_PRICE}€): {title[:40]}")
        return

    full_text = f"{title} {description}".lower()

    # Фильтр по стоп-словам
    for stop_word in config.STOP_WORDS:
        if stop_word in full_text:
            logging.info(f"  [ПРОПУСК: СТОП-СЛОВО '{stop_word}'] {title[:40]}")
            return

    # Проверка триггеров
    found_triggers = [word for word in config.POSITIVE_KEYWORDS if word in full_text]
    
    if found_triggers:
        logging.info(f"🔥 НАЙДЕНО СОВПАДЕНИЕ ({found_triggers}): {title} (€{price})")
        push_title = f"{title} — €{price}"
        push_message = (
            f"📍 Lokacija: {location}\n"
            f"🔥 Trigger: {', '.join(found_triggers)}\n"
            f"📝 Opis: {description[:100]}..."
        )
        send_ntfy_push(push_title, push_message, link, tags=["moneybag", "wrench"])
    else:
        logging.info(f"  [ПРОПУСК: НЕТ ТРИГГЕРОВ] {title[:40]}")

def main():
    logging.info(f"Старт скрипта. Топик: {TOPIC}")
    
    # ТЕСТОВЫЙ ПУШ ПРИ СТАРТЕ ДЛЯ ПРОВЕРКИ СВЯЗИ
    send_ntfy_push(
        "Bolha Scraper запущен!", 
        "Связь с GitHub Actions работает отлично.", 
        "https://www.bolha.com", 
        ["rocket"]
    )

    seen_ids = load_seen_ids()
    new_items_found = False

    for url in config.TARGET_URLS:
        logging.info(f"Scraping: {url}")
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
                logging.warning(f"Error {url} (Attempt {attempt+1}): {e}")
                time.sleep(3)
                
        time.sleep(1)

    if new_items_found:
        save_seen_ids(seen_ids)
        logging.info("Состояние базы сохранено.")

if __name__ == "__main__":
    main()
