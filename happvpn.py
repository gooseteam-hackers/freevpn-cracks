import os
import re
import sys
import logging
import platform
import urllib.parse
import subprocess
import base64
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

# ================= НАСТРОЙКИ =================
HPWNR_LOCAL_NAME = "hpwnr.exe" if platform.system().lower() == "windows" else "hpwnr"
HPWNR_LOCAL_PATH = os.path.join("core", HPWNR_LOCAL_NAME)

CHANNEL_URL = "https://t.me/s/happvpn"

FILE_AUTO = "subscription_auto.txt"
FILE_DEFAULT = "subscription_default.txt"

# Требуемое название профиля
PROFILE_TITLE = "#profile-title: base64:SEFQUGlWUE4gY3JhY2tlZCDinKg="

# Announce строка для default подписки
ANNOUNCE_LINE = "#announce: HAPPiVPN | @happvpn | " + datetime.now(timezone.utc).strftime("%Y-%m-%d")

HEADERS = {
    "User-Agent": "GooseDev72-Parser/1.0",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

# =============================================

def ensure_hpwnr():
    """Проверяет наличие hpwnr в папке core/ и делает его исполняемым."""
    if os.path.exists(HPWNR_LOCAL_PATH):
        logging.info(f"✅ Файл '{HPWNR_LOCAL_PATH}' найден.")
        if platform.system() != "Windows":
            os.chmod(HPWNR_LOCAL_PATH, 0o755)
        return True

    logging.error(f"❌ Файл '{HPWNR_LOCAL_PATH}' не найден!")
    logging.error("💡 Положи скомпилированный бинарный файл 'hpwnr' в папку 'core/' и закоммить его.")
    return False

def get_latest_crypt5_link():
    logging.info("Парсинг канала @happvpn...")
    try:
        response = requests.get(CHANNEL_URL, headers=HEADERS, timeout=15)
        response.raise_for_status()
    except Exception as e:
        logging.error(f"Ошибка при запросе к Telegram: {e}")
        return None

    # Явно декодируем как UTF-8
    try:
        page_text = response.content.decode('utf-8')
    except UnicodeDecodeError:
        page_text = response.content.decode('utf-8', errors='replace')

    soup = BeautifulSoup(page_text, 'html.parser')
    message_blocks = soup.find_all('div', class_='tgme_widget_message_text')

    if not message_blocks:
        logging.warning("Не найдено сообщений на странице.")
        return None

    latest_text = message_blocks[-1].get_text()
    match = re.search(r'(happ://crypt5/[A-Za-z0-9+/=]+)', latest_text)

    if match:
        link = match.group(1).strip()
        logging.info(f"🔗 ИЗВЛЕЧЕННАЯ ССЫЛКА: {link[:50]}...")
        return link

    logging.warning("Ссылка happ://crypt5/ в последнем сообщении не найдена.")
    return None

def decrypt_link(crypt_link):
    logging.info("Дешифровка ссылки...")
    try:
        cmd = [HPWNR_LOCAL_PATH, crypt_link]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
            encoding='utf-8',
            errors='replace'
        )
        decrypted = result.stdout.strip()
        if not decrypted:
            raise ValueError("Пустой вывод от hpwnr")
        logging.info("✅ Дешифровка успешна!")
        return decrypted
    except subprocess.CalledProcessError as e:
        stderr = (e.stderr or "").strip()
        logging.error(f"❌ Ошибка hpwnr: {stderr}")
        return None
    except Exception as e:
        logging.error(f"❌ Исключение при дешифровке: {e}")
        return None

def process_url(decrypted_url):
    """Разделяет ссылку на auto и default версии."""
    decoded = urllib.parse.unquote(decrypted_url)
    if decoded.endswith('/auto'):
        return decoded, decoded[:-5]
    else:
        return decoded.rstrip('/') + '/auto', decoded.rstrip('/')

def fetch_subscription(url):
    """Скачивает подписку по URL. Принудительно декодирует как UTF-8."""
    logging.info(f"Скачивание подписки: {url[:50]}...")
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        # ВАЖНО: декодируем вручную, а не через resp.text
        # т.к. requests.text может использовать неверную кодировку из headers
        try:
            return resp.content.decode('utf-8').strip()
        except UnicodeDecodeError:
            return resp.content.decode('utf-8', errors='replace').strip()
    except requests.RequestException as e:
        logging.error(f"Не удалось скачать подписку: {e}")
        return None

def convert_to_uri(content):
    """Конвертирует JSON конфиги в vless:// ссылки через hpwnr."""
    logging.info("Конвертация в URI...")
    try:
        cmd = [HPWNR_LOCAL_PATH, "uri"]
        result = subprocess.run(
            cmd,
            input=content,
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
            encoding='utf-8',
            errors='replace'
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        stderr = (e.stderr or "").strip()
        logging.error(f"❌ Ошибка hpwnr при конвертации: {stderr}")
        return None
    except Exception as e:
        logging.error(f"❌ Исключение при конвертации: {e}")
        return None

def process_auto(content):
    """
    AUTO версия: максимально passthrough.
    Если это JSON - возвращаем как есть.
    Если это уже URI - возвращаем как есть.
    + Заменяем "IMO: <число>" на "ALL 🟢"
    """
    content = content.strip()

    # Заменяем "IMO: 99363429720" (и похожие) на "ALL 🟢"
    content = re.sub(r'IMO:\s*\d+', 'ALL 🟢', content)

    # Проверяем, начинается ли с { или [ (JSON)
    if content.startswith('{') or content.startswith('['):
        logging.info("AUTO: JSON конфиг, возвращаем как есть (passthrough)")
        return content

    # Иначе возвращаем как есть (уже URI или другой формат)
    logging.info("AUTO: возвращаем как есть")
    return content

def process_default(content):
    """
    DEFAULT версия:
    1. Если это JSON - конвертируем в vless:// URI
    2. Добавляем заголовок первой строкой
    3. Добавляем #announce: строку
    4. Кодируем всё в Base64
    """
    content = content.strip()

    # Если это JSON, конвертируем в URI
    if content.startswith('{') or content.startswith('['):
        logging.info("DEFAULT: JSON конфиг, конвертируем в URI")
        uri_content = convert_to_uri(content)
        if not uri_content:
            logging.error("Не удалось конвертировать JSON в URI")
            return None
        content = uri_content

    # Заменяем "IMO: <число>" на "ALL 🟢" в vless ссылках тоже
    content = re.sub(r'IMO:\s*\d+', 'ALL 🟢', content)

    # Собираем финальный контент:
    # #profile-title: ...
    # #announce: ...
    # vless://...
    # vless://...
    final_content = f"{PROFILE_TITLE}\n{ANNOUNCE_LINE}\n{content}"

    # Кодируем всё в Base64
    logging.info("DEFAULT: кодируем в Base64")
    return base64.b64encode(final_content.encode('utf-8')).decode('utf-8')

def save_to_file(filepath, content):
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        logging.info(f"✅ Успешно сохранено в: {filepath}")
    except IOError as e:
        logging.error(f"Ошибка записи в {filepath}: {e}")

def main():
    logging.info("🚀 Запуск парсера HAPPiVPN (GooseDev72 edition) - ОДНОКРАТНЫЙ РЕЖИМ")

    if not ensure_hpwnr():
        logging.error("Невозможно продолжить без hpwnr. Завершение работы.")
        return 1

    crypt_link = get_latest_crypt5_link()
    if not crypt_link:
        logging.info("Новых ссылок не найдено. Завершение работы.")
        return 1

    decrypted = decrypt_link(crypt_link)
    if not decrypted:
        logging.error("Ошибка дешифровки. Завершение работы.")
        return 1

    url_auto, url_default = process_url(decrypted)

    # Скачиваем обе подписки
    content_auto_raw = fetch_subscription(url_auto)
    content_default_raw = fetch_subscription(url_default)

    if not content_auto_raw or not content_default_raw:
        logging.error("Не удалось скачать одну из подписок. Завершение работы.")
        return 1

    # Обрабатываем AUTO (passthrough + замена IMO)
    content_auto = process_auto(content_auto_raw)
    if content_auto:
        save_to_file(FILE_AUTO, content_auto)

    # Обрабатываем DEFAULT (profile-title + announce + vless -> base64)
    content_default = process_default(content_default_raw)
    if content_default:
        save_to_file(FILE_DEFAULT, content_default)

    logging.info("🎉 Парсер успешно завершил работу!")
    return 0

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
