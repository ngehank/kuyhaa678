"""
claude_checker.py — Claude.ai Cookie Checker Logic (Robust Version)
"""
import requests
import random
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

def check_claude_cookie(cookie_text: str, proxy_list: list = None) -> dict:
    cookies = parse_cookies(cookie_text)
    cookie_str = '; '.join([f'{k}={v}' for k, v in cookies.items()])
    proxy = {'http': random.choice(proxy_list), 'https': random.choice(proxy_list)} if proxy_list else None
    
    headers = {
        'User-Agent': USER_AGENT,
        'Cookie': cookie_str,
        'Accept': 'application/json',
        'Referer': 'https://claude.ai/chats',
        'Cache-Control': 'no-cache',
    }

    try:
        # Claude API endpoint for bootstrap (contains user state)
        resp = requests.get('https://claude.ai/api/bootstrap', headers=headers, proxies=proxy, timeout=15, verify=False)
        
        if resp.status_code == 200:
            data = resp.json()
            user = data.get('me', {})
            if user:
                # Check subscription
                is_pro = False
                orgs = data.get('organizations', [])
                for org in orgs:
                    if org.get('capabilities', {}).get('has_subscription'):
                        is_pro = True
                        break
                
                return {
                    'status': 'success',
                    'plan_name': 'Claude Pro' if is_pro else 'Claude Free',
                    'plan_key': 'claude_pro' if is_pro else 'free',
                    'email': user.get('email', 'Active Account'),
                    'account_name': user.get('name', 'Claude User'),
                    'country': 'Unknown',
                    'cookie_text': cookie_text
                }

        # Fallback to organizations
        resp = requests.get('https://claude.ai/api/organizations', headers=headers, proxies=proxy, timeout=15, verify=False)
        if resp.status_code == 200:
            orgs = resp.json()
            if orgs:
                return {
                    'status': 'success',
                    'plan_name': 'Account Valid',
                    'plan_key': 'free',
                    'cookie_text': cookie_text
                }

    except Exception as e:
        return {'status': 'failed', 'error_reason': str(e)}

    return {'status': 'failed', 'error_reason': 'Invalid or expired cookies'}
