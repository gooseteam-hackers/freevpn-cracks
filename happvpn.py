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

# На что заменяем "мусорные" имена
REPLACEMENT = "ALL 🟢"

# Паттерны имён, которые нужно заменить (TG: @HappVPN, IMO: <число>, Link: <число>)
NAME_PATTERNS = [
    re.compile(r'TG:\s*@HappVPN', re.IGNORECASE),
    re.compile(r'IMO:\s*\d+'),
    re.compile(r'Link:\s*\d+'),
]

# Схемы URI, у которых имя находится во фрагменте после '#'
URI_SCHEMES = ('vless://', 'vmess://', 'trojan://', 'ss://', 'hysteria2://', 'hy2://', 'hysteria://', 'tuic://')

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
        # ВАЖНО: декодируем вручную, а не через resp.text,
        # т.к. requests.text может взять неверную кодировку из HTTP-заголовков
        try:
            return resp.content.decode('utf-8').strip()
        except UnicodeDecodeError:
            return resp.content.decode('utf-8', errors='replace').strip()
    except requests.RequestException as e:
        logging.error(f"Не удалось скачать подписку: {e}")
        return None

def unwrap_base64(text, max_rounds=3):
    """
    Если контент целиком является Base64 (подписка пришла закодированной),
    распаковывает его до plaintext (JSON / vless:// / заголовки).
    Защищает от двойного кодирования в default.
    """
    content = text.strip()
    for _ in range(max_rounds):
        # Уже plaintext — не трогаем
        if content.startswith(('#', '{', '[') + URI_SCHEMES):
            break
        compact = re.sub(r'\s+', '', content)
        if len(compact) < 16 or not re.fullmatch(r'[A-Za-z0-9+/=]+', compact):
            break
        try:
            decoded = base64.b64decode(compact, validate=True).decode('utf-8')
        except Exception:
            break
        if not decoded.strip():
            break
        logging.info("📦 Обнаружен слой Base64 в подписке — распаковываю.")
        content = decoded.strip()
    return content

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

def sanitize_plain(text):
    """Заменяет 'TG: @HappVPN', 'IMO: <число>', 'Link: <число>' на 'ALL 🟢' в обычном тексте."""
    for rx in NAME_PATTERNS:
        text = rx.sub(REPLACEMENT, text)
    return text

def sanitize_content(content):
    """
    Чистит имена нод:
    - В JSON / plaintext — прямой заменой.
    - В URI (vless://...#IMYA) — декодирует фрагмент, чистит, кодирует обратно.
      Это важно: в default подписке имена приходят percent-encoded
      (IMO%3A%2099363429720), и обычная regex их не видела.
    """
    out = []
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith(URI_SCHEMES) and '#' in stripped:
            head, frag = stripped.split('#', 1)
            frag_clean = sanitize_plain(urllib.parse.unquote(frag))
            out.append(head + '#' + urllib.parse.quote(frag_clean, safe=''))
        else:
            out.append(sanitize_plain(line))
    return '\n'.join(out)

def process_auto(content):
    """
    AUTO версия: максимально passthrough + чистка имён.
    JSON возвращаем как есть, URI возвращаем как есть.
    """
    content = content.strip()
    content = sanitize_content(content)

    if content.startswith('{') or content.startswith('['):
        logging.info("AUTO: JSON конфиг, возвращаем как есть (passthrough) + имена почищены")
    else:
        logging.info("AUTO: возвращаем как есть + имена почищены")
    return content

def process_default(content):
    """
    DEFAULT версия:
    1. Распаковываем Base64 (если подписка пришла закодированной) — без двойного кодирования
    2. Если это JSON - конвертируем в vless:// URI
    3. Чистим имена (в т.ч. в percent-encoded фрагментах)
    4. Собираем: #profile-title -> #announce -> vless://...
    5. Кодируем всё в Base64 ОДИН раз
    """
    content = unwrap_base64(content.strip())

    # Если это JSON, конвертируем в URI
    if content.startswith('{') or content.startswith('['):
        logging.info("DEFAULT: JSON конфиг, конвертируем в URI")
        uri_content = convert_to_uri(content)
        if not uri_content:
            logging.error("Не удалось конвертировать JSON в URI")
            return None
        # На случай, если hpwnr вернул base64 — распаковываем
        content = unwrap_base64(uri_content)

    # Чистим имена нод
    content = sanitize_content(content)

    # Собираем финальный контент:
    # #profile-title: ...
    # #announce: ...
    # vless://...
    # vless://...
    final_content = f"{PROFILE_TITLE}\n{ANNOUNCE_LINE}\n{content}"

    # Кодируем всё в Base64 один раз
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

    # Обрабатываем AUTO (passthrough + чистка имён)
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
