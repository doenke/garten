from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix
from .models import db
from .auth import auth_bp, oauth
from .views import main_bp
import os
from sqlalchemy import inspect


_WEAK_SECRET_KEY_VALUES = {
    'changeme',
    'change-me',
    'change_me',
    'default',
    'dev',
    'development',
    'insecure',
    'placeholder',
    'replace-me',
    'replace_me',
    'secret',
    'test',
    'dev-secret-change-me',
}


def _validate_secret_key(secret_key):
    if not secret_key or not secret_key.strip():
        raise RuntimeError(
            'Konfigurationsfehler: SECRET_KEY ist nicht gesetzt. '
            'Setze eine zufällige, ausreichend lange SECRET_KEY-Umgebungsvariable.'
        )

    normalized = secret_key.strip().lower()
    if normalized in _WEAK_SECRET_KEY_VALUES:
        raise RuntimeError(
            'Konfigurationsfehler: SECRET_KEY ist zu schwach oder ein Platzhalter. '
            'Nutze einen zufälligen, nicht erratbaren Wert (mindestens 32 Zeichen).'
        )

    if len(secret_key) < 32:
        raise RuntimeError(
            'Konfigurationsfehler: SECRET_KEY ist zu kurz. '
            'Nutze mindestens 32 Zeichen mit hoher Entropie.'
        )


def _validate_oidc_config():
    oidc_vars = [
        'OIDC_SERVER_METADATA_URL',
        'OIDC_CLIENT_ID',
        'OIDC_CLIENT_SECRET',
    ]
    values = {name: os.getenv(name, '').strip() for name in oidc_vars}

    oidc_enabled = any(values.values())
    if not oidc_enabled:
        return

    missing = [name for name, value in values.items() if not value]
    if missing:
        raise RuntimeError(
            'Konfigurationsfehler: OIDC ist teilweise konfiguriert, aber folgende Variablen fehlen: '
            f"{', '.join(missing)}"
        )


def create_app():
    app = Flask(__name__, static_folder='static', template_folder='templates')

    secret_key = os.getenv('SECRET_KEY')
    _validate_secret_key(secret_key)
    _validate_oidc_config()

    app.config['SECRET_KEY'] = secret_key
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///garden.db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['UPLOAD_FOLDER'] = os.getenv('UPLOAD_FOLDER', '/data/uploads')
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
    app.config['AVATAR_FOLDER'] = os.getenv('AVATAR_FOLDER', '/data/avatars')
    app.config['MAP_FOLDER'] = os.getenv('MAP_FOLDER', '/data/maps')
    app.config['WIDGET_API_KEY'] = os.getenv('WIDGET_API_KEY', '').strip()

    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1, x_prefix=1)

    db.init_app(app)
    oauth.init_app(app)

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)

    with app.app_context():
        db.create_all()
        _run_schema_upgrades()

        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        os.makedirs(app.config['AVATAR_FOLDER'], exist_ok=True)
        os.makedirs(app.config['MAP_FOLDER'], exist_ok=True)

    return app


def _run_schema_upgrades():
    """Apply lightweight, idempotent schema upgrades for existing databases."""
    inspector = inspect(db.engine)
    upgrades = [
        ('location_timeline_entry', 'is_title_entry'),
        ('plant_event', 'is_title_entry'),
    ]
    for table_name, column_name in upgrades:
        if table_name not in inspector.get_table_names():
            continue
        existing_columns = {column['name'] for column in inspector.get_columns(table_name)}
        if column_name in existing_columns:
            continue
        db.session.execute(
            db.text(
                f'ALTER TABLE {table_name} '
                'ADD COLUMN is_title_entry BOOLEAN NOT NULL DEFAULT 0'
            )
        )
    _ensure_timeline_title_entry_uniqueness(inspector)
    _migrate_legacy_timeline_entries(inspector)
    db.session.commit()




def _ensure_timeline_title_entry_uniqueness(inspector):
    table_names = set(inspector.get_table_names())
    if 'timeline_entry' not in table_names:
        return

    existing_indexes = {index['name'] for index in inspector.get_indexes('timeline_entry')}
    if 'ux_timeline_entry_single_title_per_scope' in existing_indexes:
        return

    dialect = db.engine.dialect.name
    if dialect == 'sqlite':
        db.session.execute(db.text(
            'CREATE UNIQUE INDEX IF NOT EXISTS ux_timeline_entry_single_title_per_scope '
            'ON timeline_entry (scope_type, scope_id) WHERE is_title_entry = 1'
        ))
    elif dialect == 'postgresql':
        db.session.execute(db.text(
            'CREATE UNIQUE INDEX IF NOT EXISTS ux_timeline_entry_single_title_per_scope '
            'ON timeline_entry (scope_type, scope_id) WHERE is_title_entry IS TRUE'
        ))

def _migrate_legacy_timeline_entries(inspector):
    """Backfill timeline_entry from legacy timeline tables without duplicates."""
    table_names = set(inspector.get_table_names())
    if 'timeline_entry' not in table_names:
        return

    if 'plant_event' in table_names:
        plant_event_columns = {
            column['name']
            for column in inspector.get_columns('plant_event')
        }
        plant_created_at_expr = 'pe.created_at' if 'created_at' in plant_event_columns else 'pe.event_at'
        db.session.execute(
            db.text(
                f"""
                INSERT INTO timeline_entry (
                    scope_type, scope_id, created_at, event_at, event_type, title, description,
                    attachment_filename, attachment_kind, is_title_entry, creator_id
                )
                SELECT
                    'plant',
                    pe.plant_id,
                    {plant_created_at_expr},
                    pe.event_at,
                    pe.event_type,
                    pe.title,
                    pe.description,
                    pe.attachment_filename,
                    pe.attachment_kind,
                    pe.is_title_entry,
                    pe.creator_id
                FROM plant_event pe
                WHERE NOT EXISTS (
                    SELECT 1
                    FROM timeline_entry te
                    WHERE te.scope_type = 'plant'
                      AND te.scope_id = pe.plant_id
                      AND te.created_at = {plant_created_at_expr}
                      AND ((te.event_at = pe.event_at) OR (te.event_at IS NULL AND pe.event_at IS NULL))
                      AND te.event_type = pe.event_type
                      AND te.title = pe.title
                      AND (te.description = pe.description OR (te.description IS NULL AND pe.description IS NULL))
                      AND (te.attachment_filename = pe.attachment_filename OR (te.attachment_filename IS NULL AND pe.attachment_filename IS NULL))
                      AND (te.attachment_kind = pe.attachment_kind OR (te.attachment_kind IS NULL AND pe.attachment_kind IS NULL))
                      AND te.is_title_entry = pe.is_title_entry
                      AND te.creator_id = pe.creator_id
                )
                """
            )
        )

    if 'location_timeline_entry' in table_names:
        db.session.execute(
            db.text(
                """
                INSERT INTO timeline_entry (
                    scope_type, scope_id, created_at, event_at, event_type, title, description,
                    attachment_filename, attachment_kind, is_title_entry, creator_id
                )
                SELECT
                    'location',
                    lte.location_id,
                    lte.created_at,
                    lte.created_at,
                    'location_update',
                    NULL,
                    lte.comment,
                    lte.photo_filename,
                    'image',
                    lte.is_title_entry,
                    lte.creator_id
                FROM location_timeline_entry lte
                WHERE NOT EXISTS (
                    SELECT 1
                    FROM timeline_entry te
                    WHERE te.scope_type = 'location'
                      AND te.scope_id = lte.location_id
                      AND te.created_at = lte.created_at
                      AND te.event_at = lte.created_at
                      AND te.event_type = 'location_update'
                      AND te.title IS NULL
                      AND te.description = lte.comment
                      AND te.attachment_filename = lte.photo_filename
                      AND te.attachment_kind = 'image'
                      AND te.is_title_entry = lte.is_title_entry
                      AND te.creator_id = lte.creator_id
                )
                """
            )
        )
