"""
spotify_checker_main.py — Core Spotify Cookie Checker Logic (Scraping Edition)

Uses sp_dc cookie to authenticate against Spotify's account overview page.
This method is more robust against the 403 Forbidden Error 54113 that affects
internal API endpoints.

Flow:
  1. Visit https://www.spotify.com/id-id/account/overview/
  2. If redirected to login -> invalid
  3. Extract __NEXT_DATA__ JSON from HTML
  4. Parse plan, country, email, and display name.
"""

import re
import json
import requests
import random
from urllib3.exceptions import InsecureRequestWarning

requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

USER_AGENT = (
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
    'AppleWebKit/537.36 (KHTML, like Gecko) '
    'Chrome/124.0.0.0 Safari/537.36'
)

# ─── COOKIE PARSING ─────────────────────────────────────────────────────────

def parse_spotify_cookie_text(text: str) -> dict:
    cookies = {}
    text = text.strip()
    if not text:
        return cookies

    # JSON formats
    if text.startswith('[') or text.startswith('{'):
        try:
            data = json.loads(text)
            if isinstance(data, list):
                for item in data:
                    cookies[item.get('name', '')] = item.get('value', '')
            elif isinstance(data, dict):
                for k, v in data.items():
                    if isinstance(v, str): cookies[k] = v
            if cookies: return cookies
        except: pass

    # Netscape/Line format
    for line in text.splitlines():
        line = line.strip()
        if not line: continue
        
        # Handle #HttpOnly_
        if line.startswith('#HttpOnly_'):
            line = line[10:]
        elif line.startswith('#'):
            continue

        parts = line.split('\t')
        if len(parts) >= 7:
            name = parts[5].strip()
            value = parts[6].strip()
            if name and value: cookies[name] = value
            continue

        # key=value format
        if '=' in line:
            header_text = line[7:].strip() if line.lower().startswith('cookie:') else line
            for pair in header_text.split(';'):
                if '=' in pair:
                    k, v = pair.split('=', 1)
                    cookies[k.strip()] = v.strip()

    return {k: v for k, v in cookies.items() if k and v}


# ─── SCRAPING LOGIC ────────────────────────────────────────────────────────

def check_spotify_cookie(cookie_text: str, proxy_list: list = None) -> dict:
    """
    Main check function using scraping of account overview page.
    """
    cookies = parse_spotify_cookie_text(cookie_text)
    if not cookies or 'sp_dc' not in cookies:
        return {'status': 'failed', 'error_reason': 'Missing sp_dc cookie'}

    cookie_str = '; '.join([f'{k}={v}' for k, v in cookies.items()])
    
    # Try a few URLs just in case
    urls = [
        'https://www.spotify.com/id-id/account/overview/',
        'https://www.spotify.com/us/account/overview/',
        'https://www.spotify.com/account/overview/'
    ]
    
    proxy = {'http': random.choice(proxy_list), 'https': random.choice(proxy_list)} if proxy_list else None

    for url in urls:
        headers = {
            'User-Agent': USER_AGENT,
            'Cookie': cookie_str,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Upgrade-Insecure-Requests': '1',
        }

        try:
            print(f"    [SPOTIFY] Trying scrape: {url}")
            resp = requests.get(url, headers=headers, proxies=proxy, timeout=20, verify=False, allow_redirects=True)
            
            # If redirected to login, the cookie is invalid for this subdomain/path
            if 'login' in resp.url.lower():
                print(f"    [SPOTIFY] Redirected to login at {url}")
                continue
            
            if resp.status_code == 200:
                # 1. Look for __NEXT_DATA__ JSON
                next_data_match = re.search(r'<script id="__NEXT_DATA__" type="application/json">([^<]+)</script>', resp.text)
                if next_data_match:
                    try:
                        data = json.loads(next_data_match.group(1))
                        # 1. Try account overview props
                        props = data.get('props', {}).get('pageProps', {})
                        account = props.get('account', {})
                        
                        plan_name = account.get('plan', {}).get('name')
                        if not plan_name:
                             plan_name = props.get('subscription', {}).get('planName')
                        
                        country = account.get('country')
                        if not country:
                            # Try common paths in __NEXT_DATA__
                            country = props.get('market') or props.get('country', {}).get('flagCode')
                        
                        email = account.get('email')
                        username = account.get('username') or data.get('query', {}).get('username') or account.get('displayName')
                        
                        # 2. Try nested product data
                        if not plan_name:
                             plan_name = data.get('props', {}).get('pageProps', {}).get('product', {}).get('name')

                        if plan_name or country:
                            return format_result(plan_name, country, email, username, cookie_str)
                    except:
                        pass
                
                # 3. Fallback regex extraction (more aggressive)
                plan_match = re.search(r'"planName":"([^"]+)"', resp.text) or re.search(r'"plan":\{"name":"([^"]+)"', resp.text)
                country_match = re.search(r'"country":\{"name":"[^"]+","flagCode":"([^"]+)"', resp.text) or re.search(r'"market":"([^"]+)"', resp.text)
                email_match = re.search(r'"email":"([^"]+)"', resp.text)
                
                if plan_match or country_match:
                    return format_result(
                        plan_match.group(1) if plan_match else "Unknown",
                        country_match.group(1) if country_match else "Unknown",
                        email_match.group(1) if email_match else "",
                        "",
                        cookie_str
                    )

        except Exception as e:
            print(f"    [SPOTIFY] Error scraping {url}: {str(e)}")

    return {'status': 'failed', 'error_reason': 'Invalid session or account protected'}


def format_result(plan_name, country, email, username, cookie_str):
    """Normalize and format the final result dictionary."""
    plan_name = plan_name or "Free"
    is_premium = "free" not in plan_name.lower()
    
    # Simple plan mapping
    plan_key = "free"
    if "premium" in plan_name.lower(): plan_key = "premium"
    if "family" in plan_name.lower(): plan_key = "family"
    if "duo" in plan_name.lower(): plan_key = "duo"
    if "student" in plan_name.lower(): plan_key = "student"

    return {
        'status': 'success' if is_premium else 'free',
        'cookie_text': get_netscape_text(parse_spotify_cookie_text(cookie_str)),
        'plan_key': plan_key,
        'plan_name': plan_name,
        'country': (country or "Unknown").upper(),
        'email': email or "",
        'account_name': username or "",
        'is_on_hold': False,
    }


def get_netscape_text(cookies: dict) -> str:
    lines = ['# Netscape HTTP Cookie File']
    for name, value in cookies.items():
        lines.append(f'.spotify.com\tTRUE\t/\tTRUE\t0\t{name}\t{value}')
    return '\n'.join(lines)


# Legacy wrapper for checker.py
def check_single_spotify_cookie(cookie_text: str, proxy_list: list = None) -> dict:
    return check_spotify_cookie(cookie_text, proxy_list)
