import os
import re
import json
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

CHANNEL_URL = "https://t.me/s/happvpn"

FILE_AUTO = "subscription_auto.txt"
FILE_DEFAULT = "subscription_default.txt"

# Требуемое название профиля
PROFILE_TITLE = "#profile-title: base64:SEFQUGlWUE4gY3JhY2tlZCDinKg="
BRANDING_URL = "https://t.me/goosedev_vpnsubs"

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
        
    except requests.RequestException as e:
        logging.error(f"❌ Ошибка сети при скачивании hpwnr: {e}")
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

    latest_text = message_blocks[-1].get_text()
    match = re.search(r'(happ://crypt5/[A-Za-z0-9+/=]+)', latest_text)
    
    if match:
        link = match.group(1).strip()
        logging.info(f"🔗 ИЗВЛЕЧЕННАЯ ССЫЛКА ЦЕЛИКОМ: {link}")
        logging.info(f"📏 Длина ссылки: {len(link)} символов")
        return link
    
    logging.warning("Ссылка happ://crypt5/ в последнем сообщении не найдена.")
    return None

def decrypt_link(crypt_link):
    logging.info("Дешифровка ссылки...")
    try:
        cmd = [f"./{HPWNR_LOCAL_NAME}" if platform.system() != "Windows" else HPWNR_LOCAL_NAME, crypt_link]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=10)
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
        url_auto = decoded
        url_default = decoded[:-5]
    else:
        url_auto = decoded.rstrip('/') + '/auto'
        url_default = decoded.rstrip('/')
        
    return url_auto, url_default

def rename_config_tags(name_str):
    """Применяет регулярку для замены брендинга в именах."""
    return re.sub(r'\s*[-–—]\s*TG:\s*@HappVPN\s*', ' ● ALL 🟢', name_str, flags=re.IGNORECASE)

def fetch_and_process_subscription(url, is_default=False):
    logging.info(f"Скачивание подписки: {url[:50]}...")
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        content = resp.text.strip()
    except requests.RequestException as e:
        logging.error(f"Не удалось скачать подписку: {e}")
        return None

    # ================= ОБРАБОТКА JSON =================
    if content.startswith('[') or content.startswith('{'):
        try:
            data = json.loads(content)
            
            # 1. Если это МАССИВ конфигов (Xray/V2Ray список)
            if isinstance(data, list):
                logging.info("Обнаружен массив конфигов (JSON list).")
                for item in data:
                    if isinstance(item, dict):
                        if 'remarks' in item and isinstance(item['remarks'], str):
                            item['remarks'] = rename_config_tags(item['remarks'])
                        if 'tag' in item and isinstance(item['tag'], str):
                            item['tag'] = rename_config_tags(item['tag'])
                            
                final_json_str = json.dumps(data, indent=2, ensure_ascii=False)
                
            # 2. Если это ОБЪЕКТ (Sing-Box config)
            elif isinstance(data, dict):
                logging.info("Обнаружен объект Sing-Box (JSON dict).")
                if 'outbounds' in data and isinstance(data['outbounds'], list):
                    for ob in data['outbounds']:
                        if isinstance(ob, dict) and 'tag' in ob:
                            ob['tag'] = rename_config_tags(str(ob['tag']))
                
                # Для Sing-Box объекта в default можно продублировать заголовки внутрь JSON
                if is_default:
                    data['announce'] = PROFILE_TITLE
                    data['support_url'] = BRANDING_URL
                    data['web_page_url'] = BRANDING_URL
                    
                final_json_str = json.dumps(data, indent=2, ensure_ascii=False)
            else:
                final_json_str = content
                
            # Финализация: для default добавляем текстовый заголовок первой строкой и пакуем в Base64
            if is_default:
                final_content = f"{PROFILE_TITLE}\n{final_json_str}"
                return base64.b64encode(final_content.encode('utf-8')).decode('utf-8')
            else:
                return final_json_str
                
        except json.JSONDecodeError:
            logging.warning("Похоже на JSON, но не парсится. Обрабатываем как Plain Text.")

    # ================= ОБРАБОТКА PLAIN TEXT =================
    lines = content.split('\n')
    processed_lines = []
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        # Игнорируем старые заголовки, чтобы не было дублей
        if line.startswith('#'):
            continue
            
        if '://' in line and '#' in line:
            base, fragment = line.rsplit('#', 1)
            new_fragment = rename_config_tags(fragment)
            processed_lines.append(f"{base}#{new_fragment}")
        else:
            processed_lines.append(line)
            
    final_content = '\n'.join(processed_lines)
    
    if is_default:
        final_content = f"{PROFILE_TITLE}\n{final_content}"
        return base64.b64encode(final_content.encode('utf-8')).decode('utf-8')
        
    return final_content

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
    
    # AUTO: Чистый JSON/текст, только измененные имена
    content_auto = fetch_and_process_subscription(url_auto, is_default=False)
    if content_auto:
        save_to_file(FILE_AUTO, content_auto)
        
    # DEFAULT: С заголовками внутри Base64
    content_default = fetch_and_process_subscription(url_default, is_default=True)
    if content_default:
        save_to_file(FILE_DEFAULT, content_default)

    logging.info("🎉 Парсер успешно завершил работу!")
    return 0

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
