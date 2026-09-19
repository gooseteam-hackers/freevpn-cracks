import os
import re
import sys
import time
import logging
import platform
import subprocess
import base64
from pathlib import Path

# ================= НАСТРОЙКИ =================
HPWNR_LOCAL_NAME = "hpwnr.exe" if platform.system().lower() == "windows" else "hpwnr"

CHANNEL_URL = "https://t.me/s/happvpn"
CHECK_INTERVAL_SECONDS = 3600  # 1 час

FILE_AUTO = "subscription_auto.txt"
FILE_DEFAULT = "subscription_default.txt"

# Требуемое название профиля
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

def get_hpwnr_asset_name():
    system = platform.system().lower()
    machine = platform.machine().lower()
    
    if system == "windows":
        return "hpwnr-windows-x64.exe" if machine in ("x86_64", "amd64") else "hpwnr-windows-x86.exe"
    elif system == "linux":
        if machine in ("x86_64", "amd64"):
            return "hpwnr-linux-x86_64"
        elif machine in ("aarch64", "arm64"):
            return "hpwnr-linux-arm64"
        elif machine in ("armv7l", "armv7"):
            return "hpwnr-linux-armv7"
    elif system == "darwin":
        if machine in ("x86_64", "amd64"):
            return "hpwnr-macos-x86_64"
        elif machine in ("aarch64", "arm64"):
            return "hpwnr-macos-arm64"
            
    raise RuntimeError(f"Неподдерживаемая ОС/архитектура: {system} {machine}.")

def ensure_hpwnr():
    if os.path.exists(HPWNR_LOCAL_NAME):
        logging.info(f"✅ Файл '{HPWNR_LOCAL_NAME}' уже существует.")
        return True
        
    try:
        asset_name = get_hpwnr_asset_name()
        logging.info(f"⬇️ Файл '{HPWNR_LOCAL_NAME}' не найден. Ищу '{asset_name}' на GitHub...")
        
        import requests
        api_url = "https://api.github.com/repos/Omegaplexx/hpwnr/releases/latest"
        api_headers = {"Accept": "application/vnd.github.v3+json", "User-Agent": "GooseDev72-Parser"}
        response = requests.get(api_url, headers=api_headers, timeout=10)
        response.raise_for_status()
        
        release_data = response.json()
        download_url = None
        
        for asset in release_data.get("assets", []):
            if asset["name"] == asset_name:
                download_url = asset["browser_download_url"]
                break
                
        if not download_url:
            logging.error(f"❌ Не удалось найти ассет '{asset_name}' в последнем релизе.")
            return False
            
        logging.info(f"🔗 Начинаю загрузку: {download_url}")
        file_response = requests.get(download_url, headers={"User-Agent": "GooseDev72-Parser"}, timeout=30)
        file_response.raise_for_status()
        
        with open(HPWNR_LOCAL_NAME, "wb") as f:
            f.write(file_response.content)
            
        if platform.system() != "Windows":
            os.chmod(HPWNR_LOCAL_NAME, 0o755)
            
        logging.info(f"✅ Успешно скачано и сохранено как '{HPWNR_LOCAL_NAME}'!")
        return True
        
    except Exception as e:
        logging.error(f"❌ Ошибка при скачивании hpwnr: {e}")
        return False

def get_latest_crypt5_link():
    logging.info("Парсинг канала @happvpn...")
    try:
        import requests
        from bs4 import BeautifulSoup
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
        logging.info(f"🔗 ИЗВЛЕЧЕННАЯ ССЫЛКА ЦЕЛИКОМ: {link}")
        return link
    
    logging.warning("Ссылка happ://crypt5/ в последнем сообщении не найдена.")
    return None

def decrypt_link(crypt_link):
    logging.info("Дешифровка ссылки...")
    try:
        cmd = [f"./{HPWNR_LOCAL_NAME}" if platform.system() != "Windows" else HPWNR_LOCAL_NAME, crypt_link]
        result = subprocess.run(
            cmd, 
            capture_output=True, 
            text=True, 
            check=True, 
            timeout=10,
            encoding='utf-8' # Явное указание UTF-8 предотвращает Mojibake
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
    """Разделяет ссылку на auto и default версии."""
    # URL-decode не обязателен здесь, так как hpwnr и так выдаст чистый URL, 
    # но на всякий случай оставим для корректной обработки
    import urllib.parse
    decoded = urllib.parse.unquote(decrypted_url)
    
    if decoded.endswith('/auto'):
        url_auto = decoded
        url_default = decoded[:-5]
    else:
        url_auto = decoded.rstrip('/') + '/auto'
        url_default = decoded.rstrip('/')
        
    return url_auto, url_default

def fetch_and_convert_to_uri(url):
    """Скачивает подписку по URL и конвертирует её в чистые vless:// ссылки через hpwnr."""
    logging.info(f"Скачивание и конвертация в URI: {url[:50]}...")
    try:
        cmd = [
            f"./{HPWNR_LOCAL_NAME}" if platform.system() != "Windows" else HPWNR_LOCAL_NAME, 
            url, 
            "uri"  # Ключевая команда: конвертирует JSON Xray в список vless:// ссылок
        ]
        result = subprocess.run(
            cmd, 
            capture_output=True, 
            text=True, 
            check=True, 
            timeout=30,
            encoding='utf-8' # ГАРАНТИЯ корректной обработки эмодзи и кириллицы (🇪🇺 Автовыбор)
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        logging.error(f"❌ Ошибка hpwnr при конвертации: {e.stderr.strip()}")
        return None
    except Exception as e:
        logging.error(f"❌ Исключение при конвертации: {e}")
        return None

def process_uri_output(uri_text, is_default=False):
    """Очищает имена конфигов и применяет брендинг."""
    if not uri_text:
        return None
    
    lines = uri_text.split('\n')
    processed_lines = []
    
    for line in lines:
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        
        if '://' in line and '#' in line:
            base, fragment = line.rsplit('#', 1)
            
            # 1. Агрессивно удаляем "TG: @HappVPN", "@HappVPN", "imo" и подобные хвосты
            clean_fragment = re.sub(r'\s*[-–—|]?\s*(?:TG:\s*)?@HappVPN\s*', '', fragment, flags=re.IGNORECASE)
            clean_fragment = re.sub(r'\s*imo\s*', '', clean_fragment, flags=re.IGNORECASE) # Страховка от артефактов "imo"
            clean_fragment = clean_fragment.strip()
            
            # 2. Добавляем наш брендинг, если его еще нет
            if not clean_fragment.endswith('● ALL 🟢'):
                clean_fragment = f"{clean_fragment} ● ALL 🟢"
            
            # Убираем возможные двойные пробелы перед ●
            clean_fragment = re.sub(r'\s+● ALL 🟢', ' ● ALL 🟢', clean_fragment)
            
            processed_lines.append(f"{base}#{clean_fragment}")
        else:
            processed_lines.append(line)
    
    final_text = '\n'.join(processed_lines)
    
    if is_default:
        # Для default: добавляем заголовок ПЕРВОЙ строкой и кодируем ВЕСЬ результат в Base64
        final_text = f"{PROFILE_TITLE}\n{final_text}"
        return base64.b64encode(final_text.encode('utf-8')).decode('utf-8')
    
    # Для auto: возвращаем чистый текст ссылок без Base64 и без заголовка
    return final_text

def save_to_file(filepath, content):
    try:
        with open(filepath, 'w', encoding='utf-8') as f: # Явное указание UTF-8 при записи
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
    
    # 1. Обрабатываем AUTO версию (чистые ссылки)
    uri_auto = fetch_and_convert_to_uri(url_auto)
    content_auto = process_uri_output(uri_auto, is_default=False)
    if content_auto:
        save_to_file(FILE_AUTO, content_auto)
        
    # 2. Обрабатываем DEFAULT версию (с заголовком и Base64)
    uri_default = fetch_and_convert_to_uri(url_default)
    content_default = process_uri_output(uri_default, is_default=True)
    if content_default:
        save_to_file(FILE_DEFAULT, content_default)

    logging.info("🎉 Парсер успешно завершил работу!")
    return 0

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
