from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from functools import wraps
from .models import CookieResult
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
    # Udemy
    'udemy_premium': {'label': 'Premium', 'icon': '🎓', 'color': '#A435F0', 'desc': 'Paid Course Access'},
    # Crunchyroll
    'crunchyroll_premium': {'label': 'Premium', 'icon': '🟠', 'color': '#F47521', 'desc': 'Mega Fan / Fan'},
    # Claude
    'claude_pro': {'label': 'Pro', 'icon': '🎨', 'color': '#D97757', 'desc': 'Claude Pro Subscription'},
    # GOG
    'gog_premium': {'label': 'Account', 'icon': '⚙️', 'color': '#B145FF', 'desc': 'GOG.com Account'},
}

# Comprehensive country data: code -> (flag_emoji, full_english_name)
COUNTRY_DATA = {
    # Americas
    'US': ('🇺🇸', 'United States'),
    'CA': ('🇨🇦', 'Canada'),
    'MX': ('🇲🇽', 'Mexico'),
    'BR': ('🇧🇷', 'Brazil'),
    'AR': ('🇦🇷', 'Argentina'),
    'CL': ('🇨🇱', 'Chile'),
    'CO': ('🇨🇴', 'Colombia'),
    'PE': ('🇵🇪', 'Peru'),
    'VE': ('🇻🇪', 'Venezuela'),
    'EC': ('🇪🇨', 'Ecuador'),
    'BO': ('🇧🇴', 'Bolivia'),
    'PY': ('🇵🇾', 'Paraguay'),
    'UY': ('🇺🇾', 'Uruguay'),
    'DO': ('🇩🇴', 'Dominican Republic'),
    'GT': ('🇬🇹', 'Guatemala'),
    'HN': ('🇭🇳', 'Honduras'),
    'SV': ('🇸🇻', 'El Salvador'),
    'NI': ('🇳🇮', 'Nicaragua'),
    'CR': ('🇨🇷', 'Costa Rica'),
    'PA': ('🇵🇦', 'Panama'),
    'JM': ('🇯🇲', 'Jamaica'),
    'TT': ('🇹🇹', 'Trinidad and Tobago'),
    'CU': ('🇨🇺', 'Cuba'),
    'HT': ('🇭🇹', 'Haiti'),
    'BB': ('🇧🇧', 'Barbados'),
    'GY': ('🇬🇾', 'Guyana'),
    'SR': ('🇸🇷', 'Suriname'),
    # Europe
    'GB': ('🇬🇧', 'United Kingdom'),
    'DE': ('🇩🇪', 'Germany'),
    'FR': ('🇫🇷', 'France'),
    'IT': ('🇮🇹', 'Italy'),
    'ES': ('🇪🇸', 'Spain'),
    'NL': ('🇳🇱', 'Netherlands'),
    'BE': ('🇧🇪', 'Belgium'),
    'SE': ('🇸🇪', 'Sweden'),
    'NO': ('🇳🇴', 'Norway'),
    'DK': ('🇩🇰', 'Denmark'),
    'FI': ('🇫🇮', 'Finland'),
    'PL': ('🇵🇱', 'Poland'),
    'PT': ('🇵🇹', 'Portugal'),
    'GR': ('🇬🇷', 'Greece'),
    'AT': ('🇦🇹', 'Austria'),
    'CH': ('🇨🇭', 'Switzerland'),
    'IE': ('🇮🇪', 'Ireland'),
    'CZ': ('🇨🇿', 'Czech Republic'),
    'HU': ('🇭🇺', 'Hungary'),
    'RO': ('🇷🇴', 'Romania'),
    'BG': ('🇧🇬', 'Bulgaria'),
    'SK': ('🇸🇰', 'Slovakia'),
    'SI': ('🇸🇮', 'Slovenia'),
    'HR': ('🇭🇷', 'Croatia'),
    'RS': ('🇷🇸', 'Serbia'),
    'UA': ('🇺🇦', 'Ukraine'),
    'RU': ('🇷🇺', 'Russia'),
    'AL': ('🇦🇱', 'Albania'),
    'MK': ('🇲🇰', 'North Macedonia'),
    'LT': ('🇱🇹', 'Lithuania'),
    'LV': ('🇱🇻', 'Latvia'),
    'EE': ('🇪🇪', 'Estonia'),
    'LU': ('🇱🇺', 'Luxembourg'),
    'MT': ('🇲🇹', 'Malta'),
    'IS': ('🇮🇸', 'Iceland'),
    'BY': ('🇧🇾', 'Belarus'),
    'MD': ('🇲🇩', 'Moldova'),
    'BA': ('🇧🇦', 'Bosnia and Herzegovina'),
    'ME': ('🇲🇪', 'Montenegro'),
    'XK': ('🇽🇰', 'Kosovo'),
    'CY': ('🇨🇾', 'Cyprus'),
    # Asia and Pacific
    'CN': ('🇨🇳', 'China'),
    'JP': ('🇯🇵', 'Japan'),
    'KR': ('🇰🇷', 'South Korea'),
    'IN': ('🇮🇳', 'India'),
    'ID': ('🇮🇩', 'Indonesia'),
    'PH': ('🇵🇭', 'Philippines'),
    'VN': ('🇻🇳', 'Vietnam'),
    'TH': ('🇹🇭', 'Thailand'),
    'MY': ('🇲🇾', 'Malaysia'),
    'SG': ('🇸🇬', 'Singapore'),
    'HK': ('🇭🇰', 'Hong Kong'),
    'TW': ('🇹🇼', 'Taiwan'),
    'AU': ('🇦🇺', 'Australia'),
    'NZ': ('🇳🇿', 'New Zealand'),
    'PK': ('🇵🇰', 'Pakistan'),
    'BD': ('🇧🇩', 'Bangladesh'),
    'LK': ('🇱🇰', 'Sri Lanka'),
    'NP': ('🇳🇵', 'Nepal'),
    'MM': ('🇲🇲', 'Myanmar'),
    'KH': ('🇰🇭', 'Cambodia'),
    'MN': ('🇲🇳', 'Mongolia'),
    'BN': ('🇧🇳', 'Brunei'),
    'FJ': ('🇫🇯', 'Fiji'),
    'PG': ('🇵🇬', 'Papua New Guinea'),
    'AF': ('🇦🇫', 'Afghanistan'),
    'GE': ('🇬🇪', 'Georgia'),
    'AM': ('🇦🇲', 'Armenia'),
    'AZ': ('🇦🇿', 'Azerbaijan'),
    'KZ': ('🇰🇿', 'Kazakhstan'),
    'UZ': ('🇺🇿', 'Uzbekistan'),
    # Middle East
    'SA': ('🇸🇦', 'Saudi Arabia'),
    'AE': ('🇦🇪', 'United Arab Emirates'),
    'QA': ('🇶🇦', 'Qatar'),
    'KW': ('🇰🇼', 'Kuwait'),
    'BH': ('🇧🇭', 'Bahrain'),
    'OM': ('🇴🇲', 'Oman'),
    'JO': ('🇯🇴', 'Jordan'),
    'LB': ('🇱🇧', 'Lebanon'),
    'IQ': ('🇮🇶', 'Iraq'),
    'IR': ('🇮🇷', 'Iran'),
    'IL': ('🇮🇱', 'Israel'),
    'TR': ('🇹🇷', 'Turkey'),
    'SY': ('🇸🇾', 'Syria'),
    'YE': ('🇾🇪', 'Yemen'),
    # Africa
    'ZA': ('🇿🇦', 'South Africa'),
    'NG': ('🇳🇬', 'Nigeria'),
    'EG': ('🇪🇬', 'Egypt'),
    'KE': ('🇰🇪', 'Kenya'),
    'ET': ('🇪🇹', 'Ethiopia'),
    'GH': ('🇬🇭', 'Ghana'),
    'MA': ('🇲🇦', 'Morocco'),
    'DZ': ('🇩🇿', 'Algeria'),
    'TN': ('🇹🇳', 'Tunisia'),
    'CI': ('🇨🇮', 'Ivory Coast'),
    'TZ': ('🇹🇿', 'Tanzania'),
    'CM': ('🇨🇲', 'Cameroon'),
    'AO': ('🇦🇴', 'Angola'),
    'MZ': ('🇲🇿', 'Mozambique'),
    'ZM': ('🇿🇲', 'Zambia'),
    'ZW': ('🇿🇼', 'Zimbabwe'),
    'SN': ('🇸🇳', 'Senegal'),
    'TG': ('🇹🇬', 'Togo'),
    'BF': ('🇧🇫', 'Burkina Faso'),
    'ML': ('🇲🇱', 'Mali'),
    'MG': ('🇲🇬', 'Madagascar'),
    'BW': ('🇧🇼', 'Botswana'),
    'NA': ('🇳🇦', 'Namibia'),
    'RW': ('🇷🇼', 'Rwanda'),
    'UG': ('🇺🇬', 'Uganda'),
    'SD': ('🇸🇩', 'Sudan'),
    'GA': ('🇬🇦', 'Gabon'),
    'CD': ('🇨🇩', 'DR Congo'),
    'SC': ('🇸🇨', 'Seychelles'),
    'TD': ('🇹🇩', 'Chad'),
    'LY': ('🇱🇾', 'Libya'),
    'MU': ('🇲🇺', 'Mauritius'),
    'CV': ('🇨🇻', 'Cape Verde'),
    'YT': ('🇾🇹', 'Mayotte'),
    'MW': ('🇲🇼', 'Malawi'),
    'BI': ('🇧🇮', 'Burundi'),
    'SO': ('🇸🇴', 'Somalia'),
    # Global
    'XX': ('🌐', 'Global / Unknown'),
    'UNKNOWN': ('🌐', 'Global / Unknown'),
}


def get_flag(country_code):
    code = (country_code or 'XX').upper()
    if code == 'UNKNOWN': code = 'XX'
    return COUNTRY_DATA.get(code, ('🌍', code))[0]


def get_country_name(country_code):
    code = (country_code or 'XX').upper()
    if code == 'UNKNOWN': code = 'XX'
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
    ).filter(CookieResult.service_type == service).group_by(CookieResult.plan_key).all()

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
    ).filter(CookieResult.service_type == service).group_by(CookieResult.country).order_by(func.count(CookieResult.id).desc()).all()

    countries = [{'code': r.country, 'flag': get_flag(r.country), 'name': get_country_name(r.country), 'count': r.count}
                 for r in country_data]

    total = CookieResult.query.filter(CookieResult.service_type == service).count()
    return render_template('user/dashboard.html', plans=plans, countries=countries, total=total, current_service=service)


@user_bp.route('/plan/<plan_key>')
@login_required
@user_approved_required
def plan_view(plan_key):
    """Lihat semua negara yang tersedia dalam satu plan."""
    service = request.args.get('service', 'netflix')
    plan_meta = PLAN_META.get(plan_key, {'label': plan_key, 'icon': '📦', 'color': '#607D8B'})

    country_data = db.session.query(
        CookieResult.country,
        func.count(CookieResult.id).label('count')
    ).filter(CookieResult.plan_key == plan_key, CookieResult.service_type == service).group_by(CookieResult.country).order_by(
        func.count(CookieResult.id).desc()
    ).all()

    countries = [{'code': r.country, 'flag': get_flag(r.country), 'name': get_country_name(r.country), 'count': r.count}
                 for r in country_data]

    return render_template('user/plan.html', plan_key=plan_key, plan_meta=plan_meta, countries=countries, current_service=service)


@user_bp.route('/country/<country_code>')
@login_required
@user_approved_required
def country_view(country_code):
    """Langsung pilih akun terbaik dari negara & generate token/cookie."""
    service = request.args.get('service', 'netflix')
    plan_filter = request.args.get('plan', '')

    country_code_normalized = country_code.strip()
    if country_code_normalized.upper() == 'UNKNOWN':
        query = CookieResult.query.filter(
            CookieResult.country.in_(['Unknown', 'UNKNOWN', 'unknown', 'XX', 'xx']),
            CookieResult.service_type == service
        )
    else:
        query = CookieResult.query.filter(
            CookieResult.country == country_code_normalized,
            CookieResult.service_type == service
        )

    if plan_filter:
        query = query.filter(CookieResult.plan_key == plan_filter)

    # Otomatis pilih akun terbaik (checked paling baru)
    selected_cookie = query.order_by(CookieResult.checked_at.desc()).first()

    # Hitung total untuk info
    total_available = query.count()

    # Plan info untuk display
    plan_meta_selected = PLAN_META.get(
        selected_cookie.plan_key if selected_cookie else plan_filter,
        {'label': plan_filter or 'Unknown', 'icon': '📦', 'color': '#607D8B', 'desc': ''}
    )

    flag = get_flag(country_code)
    country_name = get_country_name(country_code)

    return render_template('user/country.html',
                           country_code=country_code.upper(),
                           country_name=country_name,
                           flag=flag,
                           cookie=selected_cookie,
                           total_available=total_available,
                           plan_filter=plan_filter,
                           plan_meta=PLAN_META,
                           plan_meta_selected=plan_meta_selected,
                           current_service=service)


@user_bp.route('/api/country/<country_code>')
@login_required
@user_approved_required
def api_country_data(country_code):
    service = request.args.get('service', 'netflix')
    plan_filter = request.args.get('plan', '')
    
    query = CookieResult.query.filter(CookieResult.service_type == service)
    if country_code.strip().upper() == 'UNKNOWN':
        query = query.filter(CookieResult.country.in_(['Unknown', 'UNKNOWN', 'unknown', 'XX', 'xx']))
    else:
        query = query.filter(CookieResult.country == country_code.strip())
        
    if plan_filter:
        query = query.filter(CookieResult.plan_key == plan_filter)
        
    cookie = query.order_by(CookieResult.checked_at.desc()).first()
    if not cookie:
        return jsonify({'error': 'No cookies found'}), 404
        
    return jsonify({
        'id': cookie.id,
        'plan_key': cookie.plan_key,
        'checked_at': cookie.checked_at,
        'cookie_text': cookie.cookie_text
    })


@user_bp.route('/cookie/<int:cookie_id>')
@login_required
@user_approved_required
def cookie_detail(cookie_id):
    """Halaman detail cookie — tampilkan info akun."""
    cookie = CookieResult.query.get_or_404(cookie_id)
    flag = get_flag(cookie.country)
    country_name = get_country_name(cookie.country)
    plan_meta = PLAN_META.get(cookie.plan_key, {'label': cookie.plan_name, 'icon': '📦', 'color': '#607D8B'})
    return render_template('user/cookie_detail.html', cookie=cookie, flag=flag, plan_meta=plan_meta, country_name=country_name)


@user_bp.route('/get-token/<int:cookie_id>', methods=['POST'])
@login_required
@user_approved_required
def get_token(cookie_id):
    """Generate NFToken on-demand dari cookies."""
    cookie = CookieResult.query.get_or_404(cookie_id)
    from .nftoken import generate_nftoken
    result = generate_nftoken(cookie.cookie_text)
    return jsonify(result)
