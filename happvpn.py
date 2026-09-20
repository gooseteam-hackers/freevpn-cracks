import os
import re
import sys
import logging
import platform
import urllib.parse
import subprocess
import base64
from pathlib import Path

import requests
from bs4 import BeautifulSoup

# ================= НАСТРОЙКИ =================
HPWNR_LOCAL_NAME = "hpwnr.exe" if platform.system().lower() == "windows" else "hpwnr"
HPWNR_LOCAL_PATH = os.path.join("core", HPWNR_LOCAL_NAME)

CHANNEL_URL = "https://t.me/s/happvpn"

FILE_AUTO = "subscription_auto.txt"
FILE_DEFAULT = "subscription_default.txt"

PROFILE_TITLE = "#profile-title: base64:SEFQUGlWUE4gY3JhY2tlZCDinKg="

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

    soup = BeautifulSoup(response.text, 'html.parser')
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
            encoding='utf-8' # Гарантия от Mojibake
        )
        decrypted = result.stdout.strip()
        if not decrypted:
            raise ValueError("Пустой вывод от hpwnr")
        logging.info("✅ Дешифровка успешна!")
        return decrypted
    except subprocess.CalledProcessError as e:
        logging.error(f"❌ Ошибка hpwnr: {e.stderr.strip()}")
        return None
    except Exception as e:
        logging.error(f"❌ Исключение при дешифровке: {e}")
        return None

def process_url(decrypted_url):
    decoded = urllib.parse.unquote(decrypted_url)
    if decoded.endswith('/auto'):
        return decoded, decoded[:-5]
    else:
        return decoded.rstrip('/') + '/auto', decoded.rstrip('/')

def fetch_and_convert_to_uri(url):
    logging.info(f"Скачивание и конвертация в URI: {url[:50]}...")
    try:
        cmd = [HPWNR_LOCAL_PATH, url, "uri"]
        result = subprocess.run(
            cmd, 
            capture_output=True, 
            text=True, 
            check=True, 
            timeout=30,
            encoding='utf-8'
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        logging.error(f"❌ Ошибка hpwnr при конвертации: {e.stderr.strip()}")
        return None
    except Exception as e:
        logging.error(f"❌ Исключение при конвертации: {e}")
        return None

def clean_fragment(fragment):
    """Декодирует, чистит от мусора и кодирует обратно название конфига."""
    # 1. Декодируем URL, чтобы работать с обычным текстом (🇩🇪 [DE] - TG: @HappVPN IMO: 12345)
    decoded = urllib.parse.unquote(fragment)
    
    # 2. Удаляем нежелательные паттерны
    clean = re.sub(r'\s*[-–—|]?\s*(?:TG:\s*)?@HappVPN\s*', '', decoded, flags=re.IGNORECASE)
    clean = re.sub(r'\s*IMO:\s*\d+\s*', '', clean, flags=re.IGNORECASE)
    clean = re.sub(r'\s*\d{8,}\s*$', '', clean) # Убираем длинные числа в конце (номера), если остались
    
    # 3. Нормализуем пробелы
    clean = re.sub(r'\s+', ' ', clean).strip()
    
    # 4. Добавляем наш брендинг
    if not clean.endswith('● ALL 🟢'):
        clean = f"{clean} ● ALL 🟢"
    
    # 5. Кодируем обратно в URL-формат (пробелы станут %20, что корректно для URI)
    return urllib.parse.quote(clean, safe='')

def process_uri_output(uri_text, is_default=False):
    if not uri_text:
        return None
    
    lines = uri_text.split('\n')
    processed_lines = []
    
    # Фильтр: берем только валидные прокси-ссылки, игнорируя любой JSON-мусор
    valid_protocols = ('vless://', 'vmess://', 'trojan://', 'ss://', 'hy2://', 'hysteria2://', 'tuic://', 'socks://', 'http://')
    
    for line in lines:
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        
        if not any(line.lower().startswith(proto) for proto in valid_protocols):
            continue # Пропускаем JSON или некорректные строки
            
        if '://' in line and '#' in line:
            base, fragment = line.rsplit('#', 1)
            encoded_fragment = clean_fragment(fragment)
            processed_lines.append(f"{base}#{encoded_fragment}")
        else:
            # Если у ссылки вдруг нет фрагмента
            if not line.endswith('● ALL 🟢'):
                line = f"{line}#● ALL 🟢"
            processed_lines.append(line)
    
    final_text = '\n'.join(processed_lines)
    
    if is_default:
        # Для default: заголовок + ВСЕ ссылки, и только потом ОДНО общее Base64 кодирование
        final_text = f"{PROFILE_TITLE}\n{final_text}"
        return base64.b64encode(final_text.encode('utf-8')).decode('utf-8')
    
    # Для auto: возвращаем чистый текст ссылок без Base64 и без заголовка
    return final_text

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
    
    # 1. AUTO версия (чистые ссылки)
    uri_auto = fetch_and_convert_to_uri(url_auto)
    content_auto = process_uri_output(uri_auto, is_default=False)
    if content_auto:
        save_to_file(FILE_AUTO, content_auto)
        
    # 2. DEFAULT версия (с заголовком и общим Base64)
    uri_default = fetch_and_convert_to_uri(url_default)
    content_default = process_uri_output(uri_default, is_default=True)
    if content_default:
        save_to_file(FILE_DEFAULT, content_default)

    logging.info("🎉 Парсер успешно завершил работу!")
    return 0

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
