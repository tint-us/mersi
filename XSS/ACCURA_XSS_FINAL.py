import time
import urllib.parse
import random
import concurrent.futures
import requests
import threading
from selenium import webdriver
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from colorama import Fore, Style, init

init(autoreset=True)

# === KONFIGURASI TELEGRAM BOT ===
TELEGRAM_TOKEN = "7678434898:AAHZcSAA7PSM3IbQqEHIX4PToEKtuX9-naA"
TELEGRAM_CHAT_ID = "5440362299"

MAX_BROWSER = 3
firefox_sema = threading.Semaphore(MAX_BROWSER)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:117.0) Gecko/20100101 Firefox/117.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_1; rv:117.0) Gecko/20100101 Firefox/117.0",
    "Mozilla/5.0 (X11; Linux x86_64; rv:117.0) Gecko/20100101 Firefox/117.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:118.0) Gecko/20100101 Firefox/118.0",
    "Mozilla/5.0 (X11; Linux x86_64; rv:119.0) Gecko/20100101 Firefox/119.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:120.0) Gecko/20100101 Firefox/120.0",
    "Mozilla/5.0 (Windows NT 6.1; WOW64; rv:115.0) Gecko/20100101 Firefox/115.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:137.0) Gecko/20100101 Firefox/137.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:118.0) Gecko/20100101 Firefox/118.0",
    "Mozilla/5.0 (X11; Linux x86_64; rv:119.0) Gecko/20100101 Firefox/119.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:120.0) Gecko/20100101 Firefox/120.0",
    "Mozilla/5.0 (Windows NT 6.1; WOW64; rv:115.0) Gecko/20100101 Firefox/115.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.6312.107 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.6167.184 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Chrome/122.0.6261.70 Safari/605.1.15",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_0_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.1 Safari/605.1.15",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.6367.60 Safari/537.36 Edg/124.0.2478.51",
    "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.6312.107 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 12; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.6261.70 Mobile Safari/537.36",
    "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
    "Mozilla/5.0 (compatible; bingbot/2.0; +http://www.bing.com/bingbot.htm)"
]

tested_combinations = set()
tested_lock = threading.Lock()

print(Fore.GREEN + Style.BRIGHT + r"""

 ▄▄▄·  ▄▄·  ▄▄· ▄• ▄▌▄▄▄   ▄▄▄·     ▐▄• ▄ .▄▄ · .▄▄ · 
▐█ ▀█ ▐█ ▌▪▐█ ▌▪█▪██▌▀▄ █·▐█ ▀█      █▌█▌▪▐█ ▀. ▐█ ▀. 
▄█▀▀█ ██ ▄▄██ ▄▄█▌▐█▌▐▀▀▄ ▄█▀▀█      ·██· ▄▀▀▀█▄▄▀▀▀█▄
▐█ ▪▐▌▐███▌▐███▌▐█▄█▌▐█•█▌▐█ ▪▐▌    ▪▐█·█▌▐█▄▪▐█▐█▄▪▐█
 ▀  ▀ ·▀▀▀ ·▀▀▀  ▀▀▀ .▀  ▀ ▀  ▀     •▀▀ ▀▀ ▀▀▀▀  ▀▀▀▀ 

🔥 ACCURA XSS + Telegram Notifier (Firefox Only) 🔥
""")

def send_telegram_notification(url, payload, param, browser_status):
    message = (
        f"✅ *XSS Detected!*\n\n"
        f"🔗 *URL:* `{url}`\n"
        f"💉 *Payload:* `{payload}`\n"
        f"📍 *Parameter:* `{param}`\n"
        f"{browser_status}"
    )
    url_api = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True
    }
    try:
        requests.post(url_api, data=data)
    except Exception as e:
        print(Fore.RED + f"[!] Error kirim Telegram: {e}")

def load_payloads():
    try:
        with open("payloads.txt", "r") as file:
            payloads = []
            for line in file:
                raw = line.strip()
                if not raw:
                    continue
                decoded = urllib.parse.unquote(raw)
                payloads.append(decoded)
            return payloads
    except FileNotFoundError:
        print(Fore.RED + "[!] File 'payloads.txt' tidak ditemukan.")
        return []

payloads = load_payloads()

def generate_headers():
    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Accept-Language": "en-US,en;q=0.9",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "TE": "Trailers"
    }
    return headers

def test_in_firefox(url):
    options = FirefoxOptions()
    options.add_argument('--headful')  # Headful mode
    user_agent = random.choice(USER_AGENTS)
    options.set_preference("general.useragent.override", user_agent)

    with firefox_sema:
        try:
            driver = webdriver.Firefox(options=options)
            driver.set_page_load_timeout(20)
            driver.get(url)
            WebDriverWait(driver, 5).until(EC.alert_is_present())
            driver.switch_to.alert.dismiss()
            driver.quit()
            return True
        except:
            try:
                driver.quit()
            except:
                pass
            return False

def test_payload(url, payload, param):
    unique_key = f"{url}|{payload}|{param}"
    with tested_lock:
        if unique_key in tested_combinations:
            return
        tested_combinations.add(unique_key)

    print(f"{Fore.CYAN}🔍 Scanning: {url}")
    hit = test_in_firefox(url)
    if hit:
        print(Fore.GREEN + f"\n✅ XSS BERHASIL!")
        print(Fore.GREEN + f"🔗 URL: {url}")
        print(Fore.WHITE + f"💉 Payload di parameter `{param}`:")
        print(Fore.YELLOW + f"{payload}")
        browser_status = f"🌐 Browser: Firefox ✅"
        print(Fore.WHITE + browser_status + "\n")
        send_telegram_notification(url, payload, param, browser_status)

def inject_payloads(url, payloads):
    parsed = urllib.parse.urlparse(url)
    queries = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    fragment = parsed.fragment

    for payload in payloads:
        if queries:  # If the URL has query parameters
            for i, (key, value) in enumerate(queries):
                temp_queries = queries.copy()
                temp_queries[i] = (key, payload)
                new_query = urllib.parse.urlencode(temp_queries)
                injected_url = urllib.parse.urlunparse(parsed._replace(query=new_query))
                test_payload(injected_url, payload, key)
        else:
            if fragment:  # If URL has fragment part
                injected_url = urllib.parse.urlunparse(parsed._replace(fragment=f"{fragment}{payload}"))
                test_payload(injected_url, payload, 'FRAGMENT')
            else:  # If there is no query and no fragment
                new_path = parsed.path.strip('/') + payload
                injected_url = urllib.parse.urlunparse(parsed._replace(path=new_path))
                test_payload(injected_url, payload, 'PATH')

def scan_quick_and_mass(target, payloads):
    print(f"{Fore.CYAN}🔍 Scanning {target} with multiple payloads...")

    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        futures = [executor.submit(inject_payloads, target, payloads) for payload in payloads]
        concurrent.futures.wait(futures)

# Example of mass scanning multiple targets
def scan_multiple_targets(targets, payloads):
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        futures = [executor.submit(scan_quick_and_mass, target, payloads) for target in targets]
        concurrent.futures.wait(futures)

def send_completion_notification():
    message = "✅ Scan XSS selesai! Semua target sudah dipindai."
    url_api = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True
    }
    try:
        requests.post(url_api, data=data)
        print(Fore.GREEN + "🔔 Pemberitahuan Telegram berhasil dikirim: Scan selesai.")
    except Exception as e:
        print(Fore.RED + f"[!] Error kirim Telegram: {e}")

# Panggil fungsi ini setelah selesai scanning semua target
try:
    with open("targets.txt", "r") as file:
        urls = [line.strip() for line in file if line.strip()]
        scan_multiple_targets(urls, payloads)
    send_completion_notification()  # Notifikasi setelah selesai
except FileNotFoundError:
    print(Fore.RED + "[!] File 'targets.txt' tidak ditemukan.")
