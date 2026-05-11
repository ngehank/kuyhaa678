from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
import os

db = SQLAlchemy()
login_manager = LoginManager()


def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'netflix-cookie-manager-secret-2024'
    
    default_db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'cookies.db')
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', f'sqlite:///{default_db_path}')
        
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500MB upload limit
    app.config['MAX_FORM_PARTS'] = 10000       # Support 10000+ file parts
    app.config['MAX_FORM_MEMORY_SIZE'] = 500 * 1024 * 1024  # 500MB form memory

    db.init_app(app)
    
    with app.app_context():
        try:
            from sqlalchemy import text
            db.session.execute(text("ALTER TABLE cookie_results ADD COLUMN service_type VARCHAR(20) DEFAULT 'netflix'"))
            db.session.commit()
            print("DB Migration: Added service_type column.")
        except Exception as e:
            # Column might already exist or table doesn't exist yet
            db.session.rollback()

    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Silakan login untuk mengakses halaman ini.'
    login_manager.login_message_category = 'warning'

    from .models import User

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    from .auth import auth_bp
    from .admin import admin_bp
    from .user import user_bp

    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(user_bp, url_prefix='/user')

    from flask import redirect, url_for, render_template_string

    @app.route('/')
    def index():
        return redirect(url_for('auth.login'))

    @app.errorhandler(413)
    def too_large(e):
        from flask import flash
        flash('File too large! Maximum 500MB per upload.', 'danger')
        return redirect(url_for('admin.check'))

    @app.errorhandler(404)
    def not_found(e):
        return render_template_string('<h2 style="font-family:sans-serif;padding:40px">404 — Page not found. <a href="/">Go back</a></h2>'), 404

    return app
