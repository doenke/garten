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

        db.session.execute(text("""
            CREATE TABLE IF NOT EXISTS plant_event (
                id INTEGER PRIMARY KEY,
                plant_id INTEGER NOT NULL,
                event_type VARCHAR(32) NOT NULL,
                event_at DATETIME NOT NULL,
                title VARCHAR(255) NOT NULL,
                description TEXT,
                attachment_filename VARCHAR(255),
                attachment_kind VARCHAR(16),
                creator_id INTEGER NOT NULL,
                FOREIGN KEY(plant_id) REFERENCES plant(id),
                FOREIGN KEY(creator_id) REFERENCES user(id)
            )
        """))
        db.session.execute(text("""
            INSERT INTO plant_event (plant_id, event_type, event_at, title, description, creator_id)
            SELECT p.id, 'plant_event', COALESCE(p.planting_date, CURRENT_TIMESTAMP), 'Eingepflanzt', 'Pflanze wurde eingepflanzt.', p.creator_id
            FROM plant p
            WHERE p.planting_date IS NOT NULL
              AND NOT EXISTS (SELECT 1 FROM plant_event pe WHERE pe.plant_id = p.id AND pe.title = 'Eingepflanzt')
        """))
        db.session.execute(text("""
            INSERT INTO plant_event (plant_id, event_type, event_at, title, description, attachment_filename, attachment_kind, creator_id)
            SELECT plant_id, 'user_comment', COALESCE(uploaded_at, CURRENT_TIMESTAMP), COALESCE(comment, 'Foto'), comment, filename, 'image', creator_id
            FROM plant_photo pp
            WHERE NOT EXISTS (SELECT 1 FROM plant_event pe WHERE pe.plant_id = pp.plant_id AND pe.attachment_filename = pp.filename)
        """))
        db.session.execute(text("""
            INSERT INTO plant_event (plant_id, event_type, event_at, title, description, creator_id)
            SELECT plant_id, 'user_comment', COALESCE(created_at, CURRENT_TIMESTAMP), 'Kommentar', comment, creator_id
            FROM plant_note pn
            WHERE NOT EXISTS (SELECT 1 FROM plant_event pe WHERE pe.plant_id = pn.plant_id AND pe.description = pn.comment AND pe.creator_id = pn.creator_id)
        """))
        db.session.commit()

        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        os.makedirs(app.config['AVATAR_FOLDER'], exist_ok=True)

    return app
