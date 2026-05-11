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
            flash('Akun Anda belum disetujui admin.', 'warning')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated


# Plan display config
PLAN_META = {
    'premium': {'label': 'Premium', 'icon': '👑', 'color': '#E50914', 'desc': 'Ultra HD · 4 Layar'},
    'standard_with_ads': {'label': 'Standard + Ads', 'icon': '📺', 'color': '#F5A623', 'desc': 'HD · 2 Layar + Iklan'},
    'standard': {'label': 'Standard', 'icon': '⭐', 'color': '#2196F3', 'desc': 'HD · 2 Layar'},
    'basic': {'label': 'Basic', 'icon': '📱', 'color': '#4CAF50', 'desc': 'SD · 1 Layar'},
    'mobile': {'label': 'Mobile', 'icon': '📲', 'color': '#9C27B0', 'desc': 'Mobile Only'},
    'free': {'label': 'Free', 'icon': '🆓', 'color': '#607D8B', 'desc': 'Tanpa Langganan'},
    'extra_member_premium': {'label': 'Extra Member', 'icon': '➕', 'color': '#FF5722', 'desc': 'Extra Member Premium'},
}

COUNTRY_FLAGS = {
    'US': '🇺🇸', 'ID': '🇮🇩', 'JP': '🇯🇵', 'KR': '🇰🇷', 'GB': '🇬🇧',
    'DE': '🇩🇪', 'FR': '🇫🇷', 'BR': '🇧🇷', 'IN': '🇮🇳', 'AU': '🇦🇺',
    'CA': '🇨🇦', 'MX': '🇲🇽', 'ES': '🇪🇸', 'IT': '🇮🇹', 'NL': '🇳🇱',
    'SE': '🇸🇪', 'NO': '🇳🇴', 'DK': '🇩🇰', 'FI': '🇫🇮', 'PL': '🇵🇱',
    'RU': '🇷🇺', 'TR': '🇹🇷', 'SA': '🇸🇦', 'AE': '🇦🇪', 'SG': '🇸🇬',
    'MY': '🇲🇾', 'TH': '🇹🇭', 'PH': '🇵🇭', 'VN': '🇻🇳', 'HK': '🇭🇰',
    'TW': '🇹🇼', 'CN': '🇨🇳', 'AR': '🇦🇷', 'CL': '🇨🇱', 'CO': '🇨🇴',
    'PE': '🇵🇪', 'NG': '🇳🇬', 'ZA': '🇿🇦', 'EG': '🇪🇬', 'PK': '🇵🇰',
}


def get_flag(country_code):
    return COUNTRY_FLAGS.get((country_code or '').upper(), '🌍')


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

    countries = [{'code': r.country, 'flag': get_flag(r.country), 'count': r.count}
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

    countries = [{'code': r.country, 'flag': get_flag(r.country), 'count': r.count}
                 for r in country_data]

    return render_template('user/plan.html', plan_key=plan_key, plan_meta=plan_meta, countries=countries, current_service=service)


@user_bp.route('/country/<country_code>')
@login_required
@user_approved_required
def country_view(country_code):
    """Lihat semua cookies dari suatu negara."""
    service = request.args.get('service', 'netflix')
    page = request.args.get('page', 1, type=int)
    plan_filter = request.args.get('plan', '')

    query = CookieResult.query.filter(CookieResult.country == country_code.upper(), CookieResult.service_type == service)
    if plan_filter:
        query = query.filter(CookieResult.plan_key == plan_filter)

    pagination = query.order_by(CookieResult.checked_at.desc()).paginate(page=page, per_page=12)

    plans_in_country = db.session.query(
        CookieResult.plan_key, CookieResult.plan_name
    ).filter(CookieResult.country == country_code.upper(), CookieResult.service_type == service).distinct().all()

    flag = get_flag(country_code)
    return render_template('user/country.html',
                           country_code=country_code.upper(),
                           flag=flag,
                           pagination=pagination,
                           plans_in_country=plans_in_country,
                           plan_filter=plan_filter,
                           plan_meta=PLAN_META,
                           current_service=service)


@user_bp.route('/cookie/<int:cookie_id>')
@login_required
@user_approved_required
def cookie_detail(cookie_id):
    """Halaman detail cookie — tampilkan info akun."""
    cookie = CookieResult.query.get_or_404(cookie_id)
    flag = get_flag(cookie.country)
    plan_meta = PLAN_META.get(cookie.plan_key, {'label': cookie.plan_name, 'icon': '📦', 'color': '#607D8B'})
    return render_template('user/cookie_detail.html', cookie=cookie, flag=flag, plan_meta=plan_meta)


@user_bp.route('/get-token/<int:cookie_id>', methods=['POST'])
@login_required
@user_approved_required
def get_token(cookie_id):
    """Generate NFToken on-demand dari cookies."""
    cookie = CookieResult.query.get_or_404(cookie_id)
    from .nftoken import generate_nftoken
    result = generate_nftoken(cookie.cookie_text)
    return jsonify(result)
