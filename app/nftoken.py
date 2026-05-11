"""
nftoken.py — Generate NFToken on-demand (tidak disimpan ke database)
"""
import sys
import os
import requests
from urllib3.exceptions import InsecureRequestWarning

requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

try:
    from .netflix_checker_main import (
        create_nftoken,
        build_nftoken_links,
        has_usable_nftoken,
        extract_netflix_cookie_bundles,
        cookies_dict_from_netscape,
        decode_netflix_value,
    )
    NFTOKEN_AVAILABLE = True
except ImportError as e:
    NFTOKEN_AVAILABLE = False
    print(f"[WARNING] Could not import nftoken: {e}")


def generate_nftoken(cookie_text: str) -> dict:
    """
    Generate NFToken dari cookie text.
    Returns:
      {
        'success': bool,
        'pc_url': str | None,
        'mobile_url': str | None,
        'expires_at': str | None,
        'error': str | None
      }
    """
    if not NFTOKEN_AVAILABLE:
        return {'success': False, 'error': 'NFToken module not available'}

    try:
        bundles = extract_netflix_cookie_bundles(cookie_text)
        if not bundles:
            return {'success': False, 'error': 'Cookie tidak valid'}

        bundle = bundles[0]
        cookies = bundle.get('cookies') or cookies_dict_from_netscape(bundle.get('netscape_text', ''))

        nftoken_data, err = create_nftoken(cookies, attempts=2)

        if not nftoken_data or not has_usable_nftoken(nftoken_data):
            return {'success': False, 'error': err or 'Token tidak tersedia'}

        token = decode_netflix_value(nftoken_data.get('token'))
        expires = nftoken_data.get('expires_at_utc')

        pc_url = f'https://netflix.com/?nftoken={token}'
        mobile_url = f'https://netflix.com/unsupported?nftoken={token}'

        return {
            'success': True,
            'token': token,
            'pc_url': pc_url,
            'mobile_url': mobile_url,
            'expires_at': expires,
            'error': None,
        }

    except Exception as e:
        return {'success': False, 'error': str(e)}
