from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix
from .models import db
from .auth import auth_bp, oauth
from .views import main_bp
from sqlalchemy import inspect, text
import os


def _ensure_column(table_name, column_name, ddl, backfill_sql=None):
    inspector = inspect(db.engine)
    if not inspector.has_table(table_name):
        return

    columns = {column['name'] for column in inspector.get_columns(table_name)}
    if column_name in columns:
        return

    db.session.execute(text(f'ALTER TABLE {table_name} ADD COLUMN {ddl}'))
    if backfill_sql:
        db.session.execute(text(backfill_sql))
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
        _ensure_column('user', 'avatar_filename', 'avatar_filename VARCHAR(255)')
        _ensure_column(
            'location',
            'creator_id',
            'creator_id INTEGER',
            backfill_sql='UPDATE location SET creator_id = user_id WHERE creator_id IS NULL'
        )
        _ensure_column(
            'plant',
            'creator_id',
            'creator_id INTEGER',
            backfill_sql='UPDATE plant SET creator_id = user_id WHERE creator_id IS NULL'
        )

        _ensure_column('plant', 'bloom_start_month', 'bloom_start_month INTEGER')
        _ensure_column('plant', 'bloom_end_month', 'bloom_end_month INTEGER')
        _ensure_column('plant', 'soil', 'soil TEXT')
        _ensure_column('plant', 'height_without_bloom_cm', 'height_without_bloom_cm INTEGER')
        _ensure_column('plant', 'height_with_bloom_cm', 'height_with_bloom_cm INTEGER')
        _ensure_column(
            'plant_photo',
            'creator_id',
            'creator_id INTEGER',
            backfill_sql='UPDATE plant_photo SET creator_id = user_id WHERE creator_id IS NULL'
        )
        _ensure_column(
            'plant_note',
            'creator_id',
            'creator_id INTEGER',
            backfill_sql='UPDATE plant_note SET creator_id = user_id WHERE creator_id IS NULL'
        )
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        os.makedirs(app.config['AVATAR_FOLDER'], exist_ok=True)

    return app
