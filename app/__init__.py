from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix
from .models import db
from .auth import auth_bp, oauth
from .views import main_bp
import os
from sqlalchemy import inspect
from .models import LightNeed, Plant, SoilProperty, DatabaseCatalog, DatabaseIdentifier, plant_light_need, plant_soil_property, plant_database_identifier


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
    app.config['MAX_ATTACHMENT_SIZE_BYTES'] = max(
        0,
        int(os.getenv('MAX_ATTACHMENT_SIZE_BYTES', str(15 * 1024 * 1024))),
    )
    app.config['MAX_CONTENT_LENGTH'] = app.config['MAX_ATTACHMENT_SIZE_BYTES']
    app.config['AVATAR_FOLDER'] = os.getenv('AVATAR_FOLDER', '/data/avatars')
    app.config['MAP_FOLDER'] = os.getenv('MAP_FOLDER', '/data/maps')
    app.config['WIDGET_API_KEY'] = os.getenv('WIDGET_API_KEY', '').strip()
    app.config['STATS_UPLOAD_CACHE_TTL_SECONDS'] = max(0, int(os.getenv('STATS_UPLOAD_CACHE_TTL_SECONDS', '60')))
    app.config['HEADER_LOGO_URL'] = os.getenv('HEADER_LOGO_URL', '').strip()
    app.config['COMMON_NAME_LOOKUP_LANG'] = os.getenv('COMMON_NAME_LOOKUP_LANG', 'de').strip().lower() or 'de'

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
    _ensure_light_need_schema(inspector)
    _ensure_soil_property_schema(inspector)
    _ensure_timeline_title_entry_uniqueness(inspector)
    _ensure_plant_extended_schema(inspector)
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


def _ensure_light_need_schema(inspector):
    table_names = set(inspector.get_table_names())
    if 'light_need' not in table_names:
        LightNeed.__table__.create(bind=db.engine, checkfirst=True)
    if 'plant_light_need' not in table_names:
        plant_light_need.create(bind=db.engine, checkfirst=True)

    key_label_pairs = [
        ('full_sun', 'Sonnig'),
        ('part_shade', 'Halbschatten'),
        ('shade', 'Schatten'),
    ]
    existing = {row.key for row in LightNeed.query.all()}
    for key, label in key_label_pairs:
        if key not in existing:
            db.session.add(LightNeed(key=key, label=label))
    db.session.flush()


def _ensure_soil_property_schema(inspector):
    table_names = set(inspector.get_table_names())
    if 'soil_property' not in table_names:
        SoilProperty.__table__.create(bind=db.engine, checkfirst=True)
    if 'plant_soil_property' not in table_names:
        plant_soil_property.create(bind=db.engine, checkfirst=True)


def _ensure_plant_extended_schema(inspector):
    table_names = set(inspector.get_table_names())
    if 'database_catalog' not in table_names:
        DatabaseCatalog.__table__.create(bind=db.engine, checkfirst=True)
    if 'database_identifier' not in table_names:
        DatabaseIdentifier.__table__.create(bind=db.engine, checkfirst=True)
    if 'plant_database_identifier' not in table_names:
        plant_database_identifier.create(bind=db.engine, checkfirst=True)

    if 'plant' in table_names:
        columns = {col['name'] for col in inspector.get_columns('plant')}
        if 'cultivar' not in columns:
            db.session.execute(db.text('ALTER TABLE plant ADD COLUMN cultivar VARCHAR(255)'))
        if 'scientific_name' not in columns:
            db.session.execute(db.text('ALTER TABLE plant ADD COLUMN scientific_name VARCHAR(255)'))
