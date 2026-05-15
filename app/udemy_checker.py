"""
udemy_checker.py — Udemy Cookie Checker Logic
"""
import re
import json
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

def check_udemy_cookie(cookie_text: str, proxy_list: list = None) -> dict:
    cookies = parse_cookies(cookie_text)
    if not cookies:
        return {'status': 'failed', 'error_reason': 'Invalid cookie format'}

    cookie_str = '; '.join([f'{k}={v}' for k, v in cookies.items()])
    proxy = {'http': random.choice(proxy_list), 'https': random.choice(proxy_list)} if proxy_list else None
    
    url = 'https://www.udemy.com/api-2.0/users/me/'
    headers = {
        'User-Agent': USER_AGENT,
        'Cookie': cookie_str,
        'Accept': 'application/json, text/plain, */*',
        'Referer': 'https://www.udemy.com/',
    }

    try:
        resp = requests.get(url, headers=headers, proxies=proxy, timeout=15, verify=False)
        if resp.status_code == 200:
            data = resp.json()
            return {
                'status': 'success',
                'plan_name': 'Account Valid',
                'plan_key': 'udemy_premium',
                'country': data.get('locale', 'Unknown').split('_')[-1].upper(),
                'email': data.get('email', ''),
                'account_name': data.get('display_name', ''),
                'cookie_text': cookie_text
            }
        else:
            # Fallback to homepage check
            resp = requests.get('https://www.udemy.com/', headers=headers, proxies=proxy, timeout=15, verify=False)
            if 'ud_cache_logged_in=1' in cookie_str or 'ud-user-jwt' in cookie_str:
                 # Check if we see profile in HTML
                 if 'auth-user-dropdown' in resp.text or 'header--user-nav' in resp.text:
                     return {
                        'status': 'success',
                        'plan_name': 'Account Valid (Scraped)',
                        'plan_key': 'premium',
                        'country': 'Unknown',
                        'cookie_text': cookie_text
                     }
    except Exception as e:
        return {'status': 'failed', 'error_reason': str(e)}

    return {'status': 'failed', 'error_reason': 'Invalid or expired cookies'}
