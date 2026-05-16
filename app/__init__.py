from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix
from .models import db
from .auth import auth_bp, oauth
from .views import main_bp
from sqlalchemy import inspect, text
import os


def _ensure_user_avatar_filename_column():
    inspector = inspect(db.engine)
    if not inspector.has_table('user'):
        return

    user_columns = {column['name'] for column in inspector.get_columns('user')}
    if 'avatar_filename' in user_columns:
        return

    db.session.execute(text('ALTER TABLE user ADD COLUMN avatar_filename VARCHAR(255)'))
    db.session.commit()


def create_app():
    app = Flask(__name__, static_folder='static', template_folder='templates')
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-change-me')
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///garden.db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['UPLOAD_FOLDER'] = os.getenv('UPLOAD_FOLDER', '/data/uploads')
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
    app.config['AVATAR_FOLDER'] = os.getenv('AVATAR_FOLDER', '/data/avatars')

    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1, x_prefix=1)

    db.init_app(app)
    oauth.init_app(app)

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)

    with app.app_context():
        db.create_all()
        _ensure_user_avatar_filename_column()
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        os.makedirs(app.config['AVATAR_FOLDER'], exist_ok=True)

    return app
