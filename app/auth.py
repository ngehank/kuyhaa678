from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from .models import User
from . import db

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        if current_user.is_admin:
            return redirect(url_for('admin.dashboard'))
        return redirect(url_for('user.dashboard'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        remember = bool(request.form.get('remember'))

        user = User.query.filter_by(username=username).first()
        if not user or not check_password_hash(user.password_hash, password):
            flash('Username atau password salah.', 'danger')
            return render_template('auth/login.html')

        if not user.is_admin and not user.is_approved:
            flash('Akun Anda belum disetujui admin. Silakan tunggu persetujuan.', 'warning')
            return render_template('auth/login.html')

        login_user(user, remember=remember)
        if user.is_admin:
            return redirect(url_for('admin.dashboard'))
        return redirect(url_for('user.dashboard'))

    return render_template('auth/login.html')


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('auth.login'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm = request.form.get('confirm_password', '')

        if not username or not email or not password:
            flash('Semua field harus diisi.', 'danger')
            return render_template('auth/register.html')

        if len(username) < 3:
            flash('Username minimal 3 karakter.', 'danger')
            return render_template('auth/register.html')

        if password != confirm:
            flash('Password tidak cocok.', 'danger')
            return render_template('auth/register.html')

        if len(password) < 6:
            flash('Password minimal 6 karakter.', 'danger')
            return render_template('auth/register.html')

        if User.query.filter_by(username=username).first():
            flash('Username sudah digunakan.', 'danger')
            return render_template('auth/register.html')

        if User.query.filter_by(email=email).first():
            flash('Email sudah terdaftar.', 'danger')
            return render_template('auth/register.html')

        user = User(
            username=username,
            email=email,
            password_hash=generate_password_hash(password),
            is_admin=False,
            is_approved=False,
        )
        db.session.add(user)
        db.session.commit()
        flash('Registrasi berhasil! Menunggu persetujuan admin.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('auth/register.html')


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Anda telah logout.', 'info')
    return redirect(url_for('auth.login'))
