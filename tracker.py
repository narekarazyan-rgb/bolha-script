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

def load_seen_ids():
    if os.path.exists(config.STATE_FILE):
        try:
            with open(config.STATE_FILE, "r", encoding="utf-8") as f:
                return set(json.load(f))
        except Exception as e:
            logging.error(f"Failed to load seen_ids: {e}")
    return set()

def save_seen_ids(seen_ids):
    # Ограничиваем размер истории, сохраняя только последние MAX_SEEN_IDS
    ids_list = list(seen_ids)[-config.MAX_SEEN_IDS:]
    with open(config.STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(ids_list, f, indent=4)

def parse_price(price_str):
    if not price_str or "dogovor" in price_str.lower():
        return 0.0
    # Убираем все кроме цифр и запятой (словенский формат: 1.250,50 €)
    cleaned = re.sub(r"[^\d,]", "", price_str.replace(".", ""))
    cleaned = cleaned.replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return 0.0

def send_ntfy_push(title, message, url, tags):
    payload = {
        "topic": config.NTFY_TOPIC,
        "title": title,
        "message": message,
        "tags": tags,
        "priority": 4, # High priority
        "click": url
    }
    
    try:
        response = requests.post("https://ntfy.sh/", json=payload, timeout=10)
        response.raise_for_status()
        logging.info(f"Ntfy push sent successfully: {title}")
    except Exception as e:
        logging.error(f"Failed to send push notification: {e}")

def process_item(item, seen_ids):
    # Парсинг базовых элементов карточки (Bolha HTML structure)
    title_elem = item.select_one("h3.entity-title a")
    if not title_elem:
        return

    title = title_elem.text.strip()
    link = "https://www.bolha.com" + title_elem.get("href", "")
    
    # Извлечение ID (иногда лежит в data-id, иногда в URL, берем из URL как самое надежное)
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

    # 1. Фильтр цены
    if not (config.MIN_PRICE <= price <= config.MAX_PRICE):
        return

    full_text = f"{title} {description}".lower()

    # 2. Фильтр стоп-слов
    if any(stop_word in full_text for stop_word in config.STOP_WORDS):
        logging.info(f"Ignored (Stop Word): {title}")
        return

    # 3. Поиск триггеров выгодной сделки
    found_triggers = [word for word in config.POSITIVE_KEYWORDS if word in full_text]
    
    if found_triggers:
        logging.info(f"MATCH FOUND: {title} - {price}€")
        push_title = f"{title} — €{price}"
        push_message = (
            f"📍 Lokacija: {location}\n"
            f"🔥 Trigger: {', '.join(found_triggers)}\n"
            f"📝 Opis: {description[:100]}..."
        )
        send_ntfy_push(push_title, push_message, link, tags=["moneybag", "wrench"])

def main():
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
                break # Успех, выходим из цикла retry
                
            except requests.exceptions.RequestException as e:
                logging.warning(f"Error fetching {url} (Attempt {attempt+1}/{config.MAX_RETRIES}): {e}")
                time.sleep(5)
                
        time.sleep(2) # Пауза между категориями

    if new_items_found:
        save_seen_ids(seen_ids)
        logging.info("State saved.")

if __name__ == "__main__":
    main()