from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from functools import wraps
from .models import CookieResult, UserCookieClaim
from . import db
from sqlalchemy import func

user_bp = Blueprint('user', __name__)


def user_approved_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login'))
        if current_user.is_admin:
            return redirect(url_for('admin.dashboard'))
        if not current_user.is_approved:
            flash('Your account has not been approved yet.', 'warning')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated


# Plan display config
PLAN_META = {
    'premium': {'label': 'Premium', 'icon': '👑', 'color': '#E50914', 'desc': 'Ultra HD · 4 Screens'},
    'standard_with_ads': {'label': 'Standard + Ads', 'icon': '📺', 'color': '#F5A623', 'desc': 'HD · 2 Screens + Ads'},
    'standard': {'label': 'Standard', 'icon': '⭐', 'color': '#2196F3', 'desc': 'HD · 2 Screens'},
    'basic': {'label': 'Basic', 'icon': '📱', 'color': '#4CAF50', 'desc': 'SD · 1 Screen'},
    'mobile': {'label': 'Mobile', 'icon': '📲', 'color': '#9C27B0', 'desc': 'Mobile Only'},
    'free': {'label': 'Free', 'icon': '🆓', 'color': '#607D8B', 'desc': 'No Subscription'},
    'extra_member_premium': {'label': 'Extra Member', 'icon': '➕', 'color': '#FF5722', 'desc': 'Extra Member Premium'},
}

# Comprehensive country data: code -> (flag_emoji, full_english_name)
COUNTRY_DATA = {
    # Americas
    'US': ('🇺🇸', 'United States'), 'CA': ('🇨🇦', 'Canada'), 'MX': ('🇲🇽', 'Mexico'),
    'BR': ('🇧🇷', 'Brazil'), 'AR': ('🇦🇷', 'Argentina'), 'CL': ('🇨🇱', 'Chile'),
    'CO': ('🇨🇴', 'Colombia'), 'PE': ('🇵🇪', 'Peru'), 'VE': ('🇻🇪', 'Venezuela'),
    'EC': ('🇪🇨', 'Ecuador'), 'BO': ('🇧🇴', 'Bolivia'), 'PY': ('🇵🇾', 'Paraguay'),
    'UY': ('🇺🇾', 'Uruguay'), 'DO': ('🇩🇴', 'Dominican Republic'), 'GT': ('🇬🇹', 'Guatemala'),
    'HN': ('🇭🇳', 'Honduras'), 'SV': ('🇸🇻', 'El Salvador'), 'NI': ('🇳🇮', 'Nicaragua'),
    'CR': ('🇨🇷', 'Costa Rica'), 'PA': ('🇵🇦', 'Panama'), 'JM': ('🇯🇲', 'Jamaica'),
    'TT': ('🇹🇹', 'Trinidad and Tobago'), 'CU': ('🇨🇺', 'Cuba'), 'HT': ('🇭🇹', 'Haiti'),
    'BB': ('🇧🇧', 'Barbados'), 'GY': ('🇬🇾', 'Guyana'), 'SR': ('🇸🇷', 'Suriname'),
    # Europe
    'GB': ('🇬🇧', 'United Kingdom'), 'DE': ('🇩🇪', 'Germany'), 'FR': ('🇫🇷', 'France'),
    'IT': ('🇮🇹', 'Italy'), 'ES': ('🇪🇸', 'Spain'), 'NL': ('🇳🇱', 'Netherlands'),
    'BE': ('🇧🇪', 'Belgium'), 'SE': ('🇸🇪', 'Sweden'), 'NO': ('🇳🇴', 'Norway'),
    'DK': ('🇩🇰', 'Denmark'), 'FI': ('🇫🇮', 'Finland'), 'PL': ('🇵🇱', 'Poland'),
    'PT': ('🇵🇹', 'Portugal'), 'GR': ('🇬🇷', 'Greece'), 'AT': ('🇦🇹', 'Austria'),
    'CH': ('🇨🇭', 'Switzerland'), 'IE': ('🇮🇪', 'Ireland'), 'CZ': ('🇨🇿', 'Czech Republic'),
    'HU': ('🇭🇺', 'Hungary'), 'RO': ('🇷🇴', 'Romania'), 'BG': ('🇧🇬', 'Bulgaria'),
    'SK': ('🇸🇰', 'Slovakia'), 'SI': ('🇸🇮', 'Slovenia'), 'HR': ('🇭🇷', 'Croatia'),
    'RS': ('🇷🇸', 'Serbia'), 'UA': ('🇺🇦', 'Ukraine'), 'RU': ('🇷🇺', 'Russia'),
    'AL': ('🇦🇱', 'Albania'), 'MK': ('🇲🇰', 'North Macedonia'), 'LT': ('🇱🇹', 'Lithuania'),
    'LV': ('🇱🇻', 'Latvia'), 'EE': ('🇪🇪', 'Estonia'), 'LU': ('🇱🇺', 'Luxembourg'),
    'MT': ('🇲🇹', 'Malta'), 'IS': ('🇮🇸', 'Iceland'), 'BY': ('🇧🇾', 'Belarus'),
    'MD': ('🇲🇩', 'Moldova'), 'BA': ('🇧🇦', 'Bosnia and Herzegovina'),
    'ME': ('🇲🇪', 'Montenegro'), 'XK': ('🇽🇰', 'Kosovo'), 'CY': ('🇨🇾', 'Cyprus'),
    # Asia and Pacific
    'CN': ('🇨🇳', 'China'), 'JP': ('🇯🇵', 'Japan'), 'KR': ('🇰🇷', 'South Korea'),
    'IN': ('🇮🇳', 'India'), 'ID': ('🇮🇩', 'Indonesia'), 'PH': ('🇵🇭', 'Philippines'),
    'VN': ('🇻🇳', 'Vietnam'), 'TH': ('🇹🇭', 'Thailand'), 'MY': ('🇲🇾', 'Malaysia'),
    'SG': ('🇸🇬', 'Singapore'), 'HK': ('🇭🇰', 'Hong Kong'), 'TW': ('🇹🇼', 'Taiwan'),
    'AU': ('🇦🇺', 'Australia'), 'NZ': ('🇳🇿', 'New Zealand'), 'PK': ('🇵🇰', 'Pakistan'),
    'BD': ('🇧🇩', 'Bangladesh'), 'LK': ('🇱🇰', 'Sri Lanka'), 'NP': ('🇳🇵', 'Nepal'),
    'MM': ('🇲🇲', 'Myanmar'), 'KH': ('🇰🇭', 'Cambodia'), 'MN': ('🇲🇳', 'Mongolia'),
    'BN': ('🇧🇳', 'Brunei'), 'FJ': ('🇫🇯', 'Fiji'), 'PG': ('🇵🇬', 'Papua New Guinea'),
    'AF': ('🇦🇫', 'Afghanistan'), 'GE': ('🇬🇪', 'Georgia'), 'AM': ('🇦🇲', 'Armenia'),
    'AZ': ('🇦🇿', 'Azerbaijan'), 'KZ': ('🇰🇿', 'Kazakhstan'), 'UZ': ('🇺🇿', 'Uzbekistan'),
    # Middle East
    'SA': ('🇸🇦', 'Saudi Arabia'), 'AE': ('🇦🇪', 'United Arab Emirates'), 'QA': ('🇶🇦', 'Qatar'),
    'KW': ('🇰🇼', 'Kuwait'), 'BH': ('🇧🇭', 'Bahrain'), 'OM': ('🇴🇲', 'Oman'),
    'JO': ('🇯🇴', 'Jordan'), 'LB': ('🇱🇧', 'Lebanon'), 'IQ': ('🇮🇶', 'Iraq'),
    'IR': ('🇮🇷', 'Iran'), 'IL': ('🇮🇱', 'Israel'), 'TR': ('🇹🇷', 'Turkey'),
    'SY': ('🇸🇾', 'Syria'), 'YE': ('🇾🇪', 'Yemen'),
    # Africa
    'ZA': ('🇿🇦', 'South Africa'), 'NG': ('🇳🇬', 'Nigeria'), 'EG': ('🇪🇬', 'Egypt'),
    'KE': ('🇰🇪', 'Kenya'), 'ET': ('🇪🇹', 'Ethiopia'), 'GH': ('🇬🇭', 'Ghana'),
    'MA': ('🇲🇦', 'Morocco'), 'DZ': ('🇩🇿', 'Algeria'), 'TN': ('🇹🇳', 'Tunisia'),
    'CI': ('🇨🇮', 'Ivory Coast'), 'TZ': ('🇹🇿', 'Tanzania'), 'CM': ('🇨🇲', 'Cameroon'),
    'AO': ('🇦🇴', 'Angola'), 'MZ': ('🇲🇿', 'Mozambique'), 'ZM': ('🇿🇲', 'Zambia'),
    'ZW': ('🇿🇼', 'Zimbabwe'), 'SN': ('🇸🇳', 'Senegal'), 'TG': ('🇹🇬', 'Togo'),
    'BF': ('🇧🇫', 'Burkina Faso'), 'ML': ('🇲🇱', 'Mali'), 'MG': ('🇲🇬', 'Madagascar'),
    'BW': ('🇧🇼', 'Botswana'), 'NA': ('🇳🇦', 'Namibia'), 'RW': ('🇷🇼', 'Rwanda'),
    'UG': ('🇺🇬', 'Uganda'), 'SD': ('🇸🇩', 'Sudan'), 'GA': ('🇬🇦', 'Gabon'),
    'CD': ('🇨🇩', 'DR Congo'), 'SC': ('🇸🇨', 'Seychelles'), 'TD': ('🇹🇩', 'Chad'),
    'LY': ('🇱🇾', 'Libya'), 'MU': ('🇲🇺', 'Mauritius'), 'CV': ('🇨🇻', 'Cape Verde'),
    'YT': ('🇾🇹', 'Mayotte'), 'MW': ('🇲🇼', 'Malawi'), 'BI': ('🇧🇮', 'Burundi'),
    'SO': ('🇸🇴', 'Somalia'),
    'XX': ('🌐', 'Global / Unknown'),
    'UNKNOWN': ('🌐', 'Global / Unknown'),
    'PS': ('🇵🇸', 'Palestine'),
}


def get_flag(country_code):
    code = (country_code or 'XX').upper()
    if code == 'UNKNOWN':
        code = 'XX'
    return COUNTRY_DATA.get(code, ('🌍', code))[0]


def get_country_name(country_code):
    code = (country_code or 'XX').upper()
    if code == 'UNKNOWN':
        code = 'XX'
    return COUNTRY_DATA.get(code, ('🌍', code))[1]


@user_bp.route('/')
@login_required
@user_approved_required
def dashboard():
    service = request.args.get('service', 'netflix')

    # Plan cards with counts
    plan_data = db.session.query(
        CookieResult.plan_key,
        CookieResult.plan_name,
        func.count(CookieResult.id).label('count')
    ).filter(
        CookieResult.service_type == service,
        CookieResult.is_on_hold == False
    ).group_by(CookieResult.plan_key).all()

    plans = []
    for row in plan_data:
        meta = PLAN_META.get(row.plan_key, {
            'label': row.plan_name or row.plan_key,
            'icon': '📦', 'color': '#607D8B', 'desc': ''
        })
        plans.append({
            'key': row.plan_key,
            'label': meta['label'],
            'icon': meta['icon'],
            'color': meta['color'],
            'desc': meta['desc'],
            'count': row.count,
        })

    # Country summary
    country_data = db.session.query(
        CookieResult.country,
        func.count(CookieResult.id).label('count')
    ).filter(
        CookieResult.service_type == service,
        CookieResult.is_on_hold == False,
        CookieResult.plan_key != 'free'
    ).group_by(CookieResult.country).order_by(
        func.count(CookieResult.id).desc()
    ).all()

    countries = [
        {'code': r.country, 'flag': get_flag(r.country), 'name': get_country_name(r.country), 'count': r.count}
        for r in country_data
    ]

    total = CookieResult.query.filter(
        CookieResult.service_type == service,
        CookieResult.is_on_hold == False,
        CookieResult.plan_key != 'free'
    ).count()

    from datetime import datetime, timedelta
    twenty_four_hours_ago = datetime.utcnow() - timedelta(hours=24)
    daily_claims_count = UserCookieClaim.query.filter(
        UserCookieClaim.user_id == current_user.id,
        UserCookieClaim.claimed_at >= twenty_four_hours_ago
    ).count()

    return render_template('user/dashboard.html', 
                           countries=countries, 
                           total=total, 
                           daily_claims_count=daily_claims_count,
                           current_service=service)

@user_bp.route('/country/<country_code>')
@login_required
@user_approved_required
def country_view(country_code):
    """Render the country view where user selects device."""
    service = request.args.get('service', 'netflix')
    flag = get_flag(country_code)
    country_name = get_country_name(country_code)
    return render_template('user/country.html',
                           country_code=country_code.upper(),
                           country_name=country_name,
                           flag=flag,
                           current_service=service)

import json
import os
import random



@user_bp.route('/api/generate/<country_code>', methods=['POST'])
@login_required
@user_approved_required
def api_generate_token(country_code):
    """Generate NFToken on-demand based on device."""
    device = request.args.get('device', 'desktop')
    service = 'netflix'

    from datetime import datetime, timedelta
    twenty_four_hours_ago = datetime.utcnow() - timedelta(hours=24)
    daily_claims_count = UserCookieClaim.query.filter(
        UserCookieClaim.user_id == current_user.id,
        UserCookieClaim.claimed_at >= twenty_four_hours_ago
    ).count()

    limit = getattr(current_user, 'max_daily_claims', 5)
    if limit is None: limit = 5

    if daily_claims_count >= limit:
        return jsonify({'error': f'Daily limit ({limit} tokens) reached. Please try again tomorrow.'}), 403

    total_left = getattr(current_user, 'total_claims_left', 20)
    if total_left is None: total_left = 20
    if total_left <= 0:
        return jsonify({'error': 'Your total claims quota has run out. Please contact Admin.'}), 403

    base_query = CookieResult.query.filter(
        CookieResult.service_type == service,
        CookieResult.is_on_hold == False
    )
    if country_code.strip().upper() == 'UNKNOWN':
        base_query = base_query.filter(CookieResult.country.in_(['Unknown', 'UNKNOWN', 'unknown', 'XX', 'xx']))
    else:
        base_query = base_query.filter(CookieResult.country == country_code.strip())

    if device == 'mobile':
        base_query = base_query.filter(CookieResult.plan_key != 'free')
    else:
        base_query = base_query.filter(CookieResult.plan_key.notin_(['free', 'mobile']))

    from sqlalchemy import select as sa_select, func
    exhausted_cookies_sq = sa_select(UserCookieClaim.cookie_id).group_by(
        UserCookieClaim.cookie_id
    ).having(func.count(UserCookieClaim.id) >= 2).scalar_subquery()

    available_cookies = base_query.filter(
        CookieResult.id.notin_(exhausted_cookies_sq)
    ).all()
    
    if not available_cookies:
        return jsonify({'error': 'No available accounts found for this country and device.'}), 404

    from .nftoken import generate_nftoken
    ads_pct = getattr(current_user, 'ads_percentage', 0)
    
    for attempt in range(3):
        if not available_cookies:
            break
            
        is_ads = random.randint(1, 100) <= ads_pct
        ads_candidates = [c for c in available_cookies if c.plan_key == 'standard_with_ads']
        non_ads_candidates = [c for c in available_cookies if c.plan_key != 'standard_with_ads']
        
        if is_ads and ads_candidates:
            selected_cookie = random.choice(ads_candidates)
        elif non_ads_candidates:
            selected_cookie = random.choice(non_ads_candidates)
        elif ads_candidates:
            selected_cookie = random.choice(ads_candidates)
        else:
            break

        result = generate_nftoken(selected_cookie.cookie_text)
        
        if result.get('success'):
            try:
                claim = UserCookieClaim(
                    user_id=current_user.id,
                    cookie_id=selected_cookie.id,
                    service_type=service
                )
                db.session.add(claim)
                if current_user.total_claims_left is not None and current_user.total_claims_left > 0:
                    current_user.total_claims_left -= 1
                db.session.commit()
            except Exception:
                db.session.rollback()
            return jsonify(result)
        else:
            available_cookies.remove(selected_cookie)

    return jsonify({'error': 'Failed to generate token. Netflix servers might be blocking our proxies. Please try again.'}), 500
