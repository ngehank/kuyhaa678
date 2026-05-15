"""
crunchyroll_checker.py — Crunchyroll Cookie Checker Logic (Deep Extraction)
"""
import requests
import random
import re
import json
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

def check_crunchyroll_cookie(cookie_text: str, proxy_list: list = None) -> dict:
    cookies = parse_cookies(cookie_text)
    cookie_str = '; '.join([f'{k}={v}' for k, v in cookies.items()])
    proxy = {'http': random.choice(proxy_list), 'https': random.choice(proxy_list)} if proxy_list else None
    
    headers = {
        'User-Agent': USER_AGENT,
        'Cookie': cookie_str,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
    }

    try:
        # Step 1: Visit membership page
        resp = requests.get('https://www.crunchyroll.com/account/membership', headers=headers, proxies=proxy, timeout=15, verify=False, allow_redirects=True)
        
        # Check for Cloudflare/Access Denied
        if resp.status_code == 403 or 'cf-browser-verification' in resp.text:
            return {'status': 'failed', 'error_reason': 'Cloudflare / IP Blocked'}

        # If redirected to login, invalid
        if 'login' in resp.url.lower():
            return {'status': 'failed', 'error_reason': 'Session expired (Redirected to login)'}

        html = resp.text
        is_premium = False
        username = "Active User"
        
        # Look for JSON state (very reliable)
        # window.__INITIAL_STATE__ = {...};
        state_match = re.search(r'window\.__INITIAL_STATE__\s*=\s*({.*?});', html)
        if state_match:
            try:
                state = json.loads(state_match.group(1))
                user_data = state.get('user', {})
                if user_data:
                    username = user_data.get('username', username)
                    # Check for subscription info in state
                    # Note: structure might vary, but usually has a 'subscription' or 'tier'
                    is_premium = user_data.get('is_premium', False)
                    # Fallback check in state
                    if not is_premium:
                        is_premium = 'premium' in str(state).lower()
            except:
                pass

        # Manual HTML checks if JSON fails
        if not is_premium:
            is_premium = any(x in html for x in ['Premium', 'Mega Fan', 'Fan Membership', 'Manage Plan', 'Abonnement', 'Membres'])

        # Country from locale
        locale = cookies.get('c_locale', 'Unknown')
        country = locale.split('-')[-1].upper() if '-' in locale else 'Unknown'

        return {
            'status': 'success' if is_premium else 'free',
            'plan_name': 'Premium' if is_premium else 'Free',
            'plan_key': 'crunchyroll_premium' if is_premium else 'free',
            'account_name': username,
            'country': country,
            'cookie_text': cookie_text
        }

    except Exception as e:
        return {'status': 'failed', 'error_reason': str(e)}

    return {'status': 'failed', 'error_reason': 'Invalid or expired cookies'}
