"""
gog_checker.py — GOG.com Cookie Checker Logic
"""
import requests
import random
from urllib3.exceptions import InsecureRequestWarning

requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'

def parse_cookies(text: str) -> dict:
    cookies = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith('#'): continue
        parts = line.split('\t')
        if len(parts) >= 7:
            cookies[parts[5].strip()] = parts[6].strip()
        elif '=' in line:
            for pair in line.split(';'):
                if '=' in pair:
                    k, v = pair.split('=', 1)
                    cookies[k.strip()] = v.strip()
    return cookies

def check_gog_cookie(cookie_text: str, proxy_list: list = None) -> dict:
    cookies = parse_cookies(cookie_text)
    cookie_str = '; '.join([f'{k}={v}' for k, v in cookies.items()])
    proxy = {'http': random.choice(proxy_list), 'https': random.choice(proxy_list)} if proxy_list else None
    
    headers = {
        'User-Agent': USER_AGENT,
        'Cookie': cookie_str,
    }

    try:
        # GOG user data endpoint
        resp = requests.get('https://www.gog.com/userData.json', headers=headers, proxies=proxy, timeout=15, verify=False)
        if resp.status_code == 200:
            data = resp.json()
            if data.get('isLoggedIn'):
                return {
                    'status': 'success',
                    'plan_name': 'Account Valid',
                    'plan_key': 'gog_premium',
                    'account_name': data.get('username', ''),
                    'country': data.get('country', 'Unknown').upper(),
                    'cookie_text': cookie_text
                }
    except Exception as e:
        return {'status': 'failed', 'error_reason': str(e)}

    return {'status': 'failed', 'error_reason': 'Invalid or expired cookies'}
