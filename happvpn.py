import os
import re
import json
import time
import logging
import platform
import urllib.parse
import subprocess
from pathlib import Path

import requests
from bs4 import BeautifulSoup

HPWNR_LOCAL_NAME = "hpwnr.exe" if platform.system().lower() == "windows" else "hpwnr"

CHANNEL_URL = "https://t.me/s/happvpn"
CHECK_INTERVAL_SECONDS = 3600  # 1 час

FILE_AUTO = "subscription_auto.txt"
FILE_DEFAULT = "subscription_default.txt"

BRANDING_TEXT = "↖️ Telegram канал @goosedev_vpnsubs ↗️\n✨ HAPPiVPN cracked by @GooseDev72 ✨"
BRANDING_URL = "https://t.me/goosedev_vpnsubs"

HEADERS = {
    "User-Agent": "curl/1.0",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

def get_hpwnr_asset_name():
    system = platform.system().lower()
    machine = platform.machine().lower()
    
    if system == "windows":
        return "hpwnr-x86_64-pc-windows-gnu.exe"
    elif system == "linux":
        if machine in ("x86_64", "amd64"):
            return "hpwnr-x86_64-unknown-linux-musl"
        elif machine in ("aarch64", "arm64"):
            return "hpwnr-aarch64-unknown-linux-musl"
    elif system == "darwin":  # macOS
        if machine in ("x86_64", "amd64"):
            return "hpwnr-x86_64-apple-darwin"
        elif machine in ("aarch64", "arm64"):
            return "hpwnr-aarch64-apple-darwin"
            
    raise RuntimeError(f"Неподдерживаемая ОС/архитектура: {system} {machine}")

def ensure_hpwnr():
    if os.path.exists(HPWNR_LOCAL_NAME):
        logging.info(f"✅ Файл '{HPWNR_LOCAL_NAME}' уже существует.")
        return True
        
    try:
        asset_name = get_hpwnr_asset_name()
        logging.info(f"⬇️ Файл '{HPWNR_LOCAL_NAME}' не найден. Ищу '{asset_name}' на GitHub...")
        
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
            logging.error("💡 Скачай его вручную с https://github.com/Omegaplexx/hpwnr/releases")
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
        
    except requests.RequestException as e:
        logging.error(f"❌ Ошибка сети при скачивании hpwnr: {e}")
        logging.error("💡 Совет: Скачай файл вручную и положи его в папку со скриптом.")
        return False
    except Exception as e:
        logging.error(f"❌ Неожиданная ошибка: {e}")
        return False

def get_latest_crypt5_link():
    logging.info("Парсинг канала @happvpn...")
    try:
        response = requests.get(CHANNEL_URL, headers=HEADERS, timeout=15)
        response.raise_for_status()
    except requests.RequestException as e:
        logging.error(f"Ошибка при запросе к Telegram: {e}")
        return None

    soup = BeautifulSoup(response.text, 'html.parser')
    message_blocks = soup.find_all('div', class_='tgme_widget_message_text')
    
    if not message_blocks:
        logging.warning("Не найдено сообщений на странице.")
        return None

    latest_text = message_blocks[0].get_text()
    match = re.search(r'(happ://crypt5/[^\s]+)', latest_text)
    
    if match:
        link = match.group(1).strip()
        logging.info(f"Найдена ссылка: {link[:40]}...")
        return link
    
    logging.warning("Ссылка happ://crypt5/ в последнем сообщении не найдена.")
    return None

def decrypt_link(crypt_link):
    logging.info("Дешифровка ссылки...")
    try:
        result = subprocess.run(
            [f"./{HPWNR_LOCAL_NAME}" if platform.system() != "Windows" else HPWNR_LOCAL_NAME, crypt_link],
            capture_output=True,
            text=True,
            check=True,
            timeout=10
        )
        decrypted = result.stdout.strip()
        if not decrypted:
            raise ValueError("Пустой вывод от hpwnr")
        logging.info("Дешифровка успешна!")
        return decrypted
    except subprocess.CalledProcessError as e:
        logging.error(f"Ошибка hpwnr: {e.stderr.strip()}")
        return None
    except Exception as e:
        logging.error(f"Исключение при дешифровке: {e}")
        return None

def process_url(decrypted_url):
    decoded = urllib.parse.unquote(decrypted_url)
    
    if decoded.endswith('/auto'):
        url_auto = decoded
        url_default = decoded[:-5]
    else:
        url_auto = decoded.rstrip('/') + '/auto'
        url_default = decoded.rstrip('/')
        
    return url_auto, url_default

def fetch_and_process_subscription(url):
    logging.info(f"Скачивание подписки: {url[:50]}...")
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        content = resp.text.strip()
    except requests.RequestException as e:
        logging.error(f"Не удалось скачать подписку: {e}")
        return None

    if content.startswith('{'):
        try:
            data = json.loads(content)
            if isinstance(data, dict):
                data['announce'] = BRANDING_TEXT
                data['support_url'] = BRANDING_URL
                data['web_page_url'] = BRANDING_URL
                
                if 'outbounds' in data and isinstance(data['outbounds'], list):
                    for ob in data['outbounds']:
                        if isinstance(ob, dict) and 'tag' in ob:
                            old_tag = str(ob['tag'])
                            new_tag = re.sub(r'\s*[-–—]\s*TG:\s*@HappVPN\s*', ' ● ALL 🟢', old_tag, flags=re.IGNORECASE)
                            ob['tag'] = new_tag
                            
                return json.dumps(data, indent=2, ensure_ascii=False)
        except json.JSONDecodeError:
            pass

    lines = content.split('\n')
    processed_lines = []
    processed_lines.append(f"# {BRANDING_TEXT.replace(chr(10), ' | ')}")
    
    for line in lines:
        line = line.strip()
        if not line or line.startswith('#'):
            processed_lines.append(line)
            continue
            
        if '://' in line and '#' in line:
            base, fragment = line.rsplit('#', 1)
            new_fragment = re.sub(r'\s*[-–—]\s*TG:\s*@HappVPN\s*', ' ● ALL 🟢', fragment, flags=re.IGNORECASE)
            processed_lines.append(f"{base}#{new_fragment}")
        else:
            processed_lines.append(line)
            
    return '\n'.join(processed_lines)

def save_to_file(filepath, content):
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        logging.info(f"✅ Успешно сохранено в: {filepath}")
    except IOError as e:
        logging.error(f"Ошибка записи в {filepath}: {e}")

def main_loop():
    logging.info("🚀 Запуск парсера HAPPiVPN (GooseDev72 edition)")
    logging.info(f"Интервал проверки: {CHECK_INTERVAL_SECONDS} секунд")
    
    if not ensure_hpwnr():
        logging.error("Невозможно продолжить без hpwnr. Завершение работы.")
        return

    while True:
        try:
            logging.info("-" * 50)
            crypt_link = get_latest_crypt5_link()
            if not crypt_link:
                logging.info("Новых ссылок не найдено, ждем следующего цикла...")
                time.sleep(CHECK_INTERVAL_SECONDS)
                continue

            decrypted = decrypt_link(crypt_link)
            if not decrypted:
                time.sleep(CHECK_INTERVAL_SECONDS)
                continue

            url_auto, url_default = process_url(decrypted)
            
            content_auto = fetch_and_process_subscription(url_auto)
            if content_auto:
                save_to_file(FILE_AUTO, content_auto)
                
            content_default = fetch_and_process_subscription(url_default)
            if content_default:
                save_to_file(FILE_DEFAULT, content_default)

            logging.info("🎉 Цикл успешно завершен!")
            
        except Exception as e:
            logging.error(f"Непредвиденная ошибка в главном цикле: {e}")
            
        time.sleep(CHECK_INTERVAL_SECONDS)

if __name__ == "__main__":
    main_loop()
