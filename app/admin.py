from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, Response, current_app
from flask_login import login_required, current_user
from functools import wraps
from .models import User, CookieResult
from . import db
from .checker import check_single_cookie, parse_proxy_text, CHECKER_AVAILABLE
import threading
import json
import queue
import traceback
from datetime import datetime

admin_bp = Blueprint('admin', __name__)

# SSE progress queue (global)
progress_queue = queue.Queue()


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash('Akses ditolak. Hanya admin yang bisa mengakses halaman ini.', 'danger')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated


# ─── HELPER: Kumpulkan file contents ─────────────────────────────────────────

def _collect_from_files(files):
    contents = []
    for f in files:
        if f and f.filename:
            try:
                content = f.read().decode('utf-8', errors='ignore')
                if content.strip():
                    contents.append((f.filename, content))
            except Exception:
                pass
    return contents


def _collect_from_zip(zip_file):
    import zipfile, io
    contents = []
    try:
        data = zip_file.read()
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            for name in zf.namelist():
                if name.lower().endswith(('.txt', '.json')) and '__MACOSX' not in name:
                    try:
                        text = zf.read(name).decode('utf-8', errors='ignore')
                        if text.strip():
                            contents.append((name.split('/')[-1], text))
                    except Exception:
                        pass
    except Exception:
        pass
    return contents


def _collect_from_folder(folder_path):
    import os
    contents = []
    if not os.path.isdir(folder_path):
        return contents
    for fname in os.listdir(folder_path):
        if fname.lower().endswith(('.txt', '.json')):
            fpath = os.path.join(folder_path, fname)
            try:
                with open(fpath, 'r', encoding='utf-8', errors='ignore') as f:
                    text = f.read()
                if text.strip():
                    contents.append((fname, text))
            except Exception:
                pass
    return contents


# ─── BACKGROUND WORKER ───────────────────────────────────────────────────────

def _run_check_background(flask_app, file_contents, proxies, threads_count):
    """
    Jalankan pengecekan cookies di background thread.
    WAJIB pakai flask_app.app_context() agar bisa akses database.
    """
    with flask_app.app_context():
        results = {
            'done': 0, 'total': len(file_contents),
            'success': 0, 'failed': 0, 'error': 0
        }
        task_q = queue.Queue()
        for item in file_contents:
            task_q.put(item)

        db_results = []
        lock = threading.Lock()

        def worker():
            while True:
                try:
                    fname, content = task_q.get_nowait()
                except queue.Empty:
                    break
                try:
                    result = check_single_cookie(content, proxies)
                except Exception as e:
                    result = {'status': 'error', 'error_reason': str(e)}

                with lock:
                    results['done'] += 1
                    status = result.get('status', 'error')
                    if status in ('success', 'free'):
                        results['success'] += 1
                        db_results.append((fname, result))
                    elif status == 'failed':
                        results['failed'] += 1
                    else:
                        results['error'] += 1

                    progress_queue.put(json.dumps({
                        'done': results['done'],
                        'total': results['total'],
                        'success': results['success'],
                        'failed': results['failed'],
                        'error': results['error'],
                        'current': fname,
                        'status': status,
                    }))
                    print(f"[CHECK] {fname} -> {status} | Error: {result.get('error_reason', '')}")
                task_q.task_done()

        n_threads = min(threads_count, max(1, len(file_contents)))
        thread_list = [threading.Thread(target=worker, daemon=True) for _ in range(n_threads)]
        for t in thread_list:
            t.start()
        for t in thread_list:
            t.join()

        def sanitize(s):
            if not isinstance(s, str):
                return s
            return s.encode('utf-8', 'surrogatepass').decode('utf-8', 'ignore').replace('\x00', '')

        # ── Simpan ke database (dalam app_context) ──
        saved = 0
        try:
            for fname, result in db_results:
                try:
                    entry = CookieResult(
                        filename=sanitize(fname),
                        cookie_text=sanitize(result.get('cookie_text', '')),
                        plan_key=sanitize(result.get('plan_key', 'unknown')),
                        plan_name=sanitize(result.get('plan_name', 'Unknown')),
                        country=sanitize(result.get('country', 'Unknown')),
                        is_on_hold=bool(result.get('is_on_hold', False)),
                        email=sanitize(result.get('email')),
                        account_name=sanitize(result.get('account_name')),
                        quality=sanitize(result.get('quality')),
                        max_streams=sanitize(result.get('max_streams')),
                        plan_price=sanitize(result.get('plan_price')),
                        next_billing=sanitize(result.get('next_billing')),
                        payment_method=sanitize(result.get('payment_method')),
                        member_since=sanitize(result.get('member_since')),
                        extra_members=sanitize(result.get('extra_members')),
                        profiles=sanitize(result.get('profiles')),
                        hold_status=sanitize(result.get('hold_status')),
                        membership_status=sanitize(result.get('membership_status')),
                        source_file=sanitize(fname),
                        checked_at=datetime.utcnow(),
                    )
                    db.session.add(entry)
                    saved += 1
                except Exception as e:
                    print(f"[DB ERROR] Gagal tambah entry {fname}: {e}")
                    continue

            db.session.commit()
            print(f"[DB] Berhasil simpan {saved} cookies ke database.")
        except Exception as e:
            db.session.rollback()
            print(f"[DB ERROR] Commit gagal: {e}\n{traceback.format_exc()}")

        progress_queue.put(json.dumps({
            'done': results['total'],
            'total': results['total'],
            'success': results['success'],
            'failed': results['failed'],
            'error': results['error'],
            'saved': saved,
            'current': 'DONE',
            'status': 'done',
        }))


# ─── ROUTES ──────────────────────────────────────────────────────────────────

@admin_bp.route('/')
@login_required
@admin_required
def dashboard():
    total = CookieResult.query.count()
    from sqlalchemy import func
    plan_stats = db.session.query(
        CookieResult.plan_key,
        CookieResult.plan_name,
        func.count(CookieResult.id).label('count')
    ).group_by(CookieResult.plan_key).all()

    country_stats = db.session.query(
        CookieResult.country,
        func.count(CookieResult.id).label('count')
    ).group_by(CookieResult.country).order_by(
        func.count(CookieResult.id).desc()
    ).limit(15).all()

    pending_users = User.query.filter_by(is_approved=False, is_admin=False).count()
    total_users = User.query.filter_by(is_admin=False).count()

    return render_template('admin/dashboard.html',
                           total=total,
                           plan_stats=plan_stats,
                           country_stats=country_stats,
                           pending_users=pending_users,
                           total_users=total_users)


@admin_bp.route('/check', methods=['GET', 'POST'])
@login_required
@admin_required
def check():
    if request.method == 'POST':
        proxy_text = request.form.get('proxies', '')
        threads_count = max(1, min(int(request.form.get('threads', 5) or 5), 30))
        proxies = parse_proxy_text(proxy_text) if proxy_text.strip() else []
        upload_mode = request.form.get('upload_mode', 'files')
        file_contents = []

        if upload_mode == 'zip':
            zip_file = request.files.get('zip_file')
            if not zip_file or zip_file.filename == '':
                flash('Pilih file ZIP terlebih dahulu.', 'danger')
                return redirect(url_for('admin.check'))
            file_contents = _collect_from_zip(zip_file)
            if not file_contents:
                flash('ZIP tidak mengandung file cookie yang valid (.txt/.json).', 'danger')
                return redirect(url_for('admin.check'))

        elif upload_mode == 'folder':
            folder_path = request.form.get('folder_path', '').strip()
            if not folder_path:
                flash('Masukkan path folder.', 'danger')
                return redirect(url_for('admin.check'))
            file_contents = _collect_from_folder(folder_path)
            if not file_contents:
                flash(f'Folder tidak ditemukan atau kosong: {folder_path}', 'danger')
                return redirect(url_for('admin.check'))

        else:  # files
            files = request.files.getlist('cookies')
            if not files or all(f.filename == '' for f in files):
                flash('Pilih minimal 1 file cookie.', 'danger')
                return redirect(url_for('admin.check'))
            file_contents = _collect_from_files(files)

        if not file_contents:
            flash('Tidak ada file cookie yang valid ditemukan.', 'danger')
            return redirect(url_for('admin.check'))

        # Kosongkan queue lama
        while not progress_queue.empty():
            try:
                progress_queue.get_nowait()
            except queue.Empty:
                break

        # Ambil app instance SEBELUM spawn thread
        flask_app = current_app._get_current_object()

        t = threading.Thread(
            target=_run_check_background,
            args=(flask_app, file_contents, proxies, threads_count),
            daemon=True
        )
        t.start()
        return render_template('admin/checking.html',
                               total=len(file_contents),
                               checker_ok=CHECKER_AVAILABLE)

    return render_template('admin/check.html', checker_ok=CHECKER_AVAILABLE)


@admin_bp.route('/progress-stream')
@login_required
@admin_required
def progress_stream():
    def generate():
        while True:
            try:
                msg = progress_queue.get(timeout=30)
                yield f"data: {msg}\n\n"
                data = json.loads(msg)
                if data.get('status') == 'done' or data.get('current') == 'DONE':
                    break
            except queue.Empty:
                yield 'data: {"heartbeat": true}\n\n'
    return Response(generate(), mimetype='text/event-stream',
                    headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})


@admin_bp.route('/debug-checker')
@login_required
@admin_required
def debug_checker():
    """Cek apakah modul checker berhasil di-import."""
    from .checker import CHECKER_AVAILABLE
    import sys, os
    checker_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        'Netflix-Cookie-Checker-main'
    )
    main_exists = os.path.exists(os.path.join(checker_dir, 'main.py'))
    info = {
        'checker_available': CHECKER_AVAILABLE,
        'checker_dir': checker_dir,
        'main_py_exists': main_exists,
        'db_count': CookieResult.query.count(),
    }
    return jsonify(info)


@admin_bp.route('/results')
@login_required
@admin_required
def results():
    page = request.args.get('page', 1, type=int)
    plan_filter = request.args.get('plan', '')
    country_filter = request.args.get('country', '')
    search = request.args.get('search', '')

    query = CookieResult.query
    if plan_filter:
        query = query.filter(CookieResult.plan_key == plan_filter)
    if country_filter:
        query = query.filter(CookieResult.country == country_filter)
    if search:
        query = query.filter(
            (CookieResult.email.ilike(f'%{search}%')) |
            (CookieResult.account_name.ilike(f'%{search}%')) |
            (CookieResult.country.ilike(f'%{search}%'))
        )

    pagination = query.order_by(CookieResult.checked_at.desc()).paginate(page=page, per_page=20)
    from sqlalchemy import func
    plans = db.session.query(CookieResult.plan_key, CookieResult.plan_name).distinct().all()
    countries = db.session.query(CookieResult.country).distinct().order_by(CookieResult.country).all()

    return render_template('admin/results.html',
                           pagination=pagination,
                           plans=plans,
                           countries=countries,
                           plan_filter=plan_filter,
                           country_filter=country_filter,
                           search=search)


@admin_bp.route('/delete/<int:cookie_id>', methods=['POST'])
@login_required
@admin_required
def delete_cookie(cookie_id):
    cookie = CookieResult.query.get_or_404(cookie_id)
    db.session.delete(cookie)
    db.session.commit()
    flash('Cookie berhasil dihapus.', 'success')
    return redirect(request.referrer or url_for('admin.results'))


@admin_bp.route('/delete-expired', methods=['POST'])
@login_required
@admin_required
def delete_expired():
    from datetime import date
    today = date.today().isoformat()
    deleted = 0
    for c in CookieResult.query.all():
        if c.next_billing:
            try:
                if c.next_billing[:10] < today:
                    db.session.delete(c)
                    deleted += 1
            except Exception:
                pass
    db.session.commit()
    flash(f'{deleted} cookies expired dihapus dari database.', 'success')
    return redirect(url_for('admin.results'))


@admin_bp.route('/delete-all', methods=['POST'])
@login_required
@admin_required
def delete_all():
    try:
        CookieResult.query.delete()
        db.session.commit()
        flash('Semua data cookies berhasil dikosongkan.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Gagal menghapus data: {e}', 'danger')
    return redirect(url_for('admin.results'))


@admin_bp.route('/users')
@login_required
@admin_required
def users():
    all_users = User.query.filter_by(is_admin=False).order_by(User.created_at.desc()).all()
    return render_template('admin/users.html', users=all_users)


@admin_bp.route('/users/approve/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def approve_user(user_id):
    user = User.query.get_or_404(user_id)
    user.is_approved = True
    db.session.commit()
    flash(f'User "{user.username}" telah disetujui.', 'success')
    return redirect(url_for('admin.users'))


@admin_bp.route('/users/reject/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def reject_user(user_id):
    user = User.query.get_or_404(user_id)
    db.session.delete(user)
    db.session.commit()
    flash('User telah dihapus.', 'info')
    return redirect(url_for('admin.users'))


@admin_bp.route('/api/stats')
@login_required
@admin_required
def api_stats():
    from sqlalchemy import func
    plan_stats = db.session.query(
        CookieResult.plan_key, func.count(CookieResult.id)
    ).group_by(CookieResult.plan_key).all()
    return jsonify({p: c for p, c in plan_stats})
