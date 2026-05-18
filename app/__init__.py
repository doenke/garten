from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix
from .models import db
from .auth import auth_bp, oauth
from .views import main_bp
from sqlalchemy import inspect, text
import json
from sqlalchemy.exc import OperationalError
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


def _has_column(table_name, column_name):
    inspector = inspect(db.engine)
    if not inspector.has_table(table_name):
        return False
    return any(column['name'] == column_name for column in inspector.get_columns(table_name))


def _drop_column_if_exists(table_name, column_name):
    if not _has_column(table_name, column_name):
        return

    try:
        db.session.execute(text(f'ALTER TABLE {table_name} DROP COLUMN {column_name}'))
    except OperationalError as exc:
        message = str(exc.orig) if getattr(exc, 'orig', None) else str(exc)
        if 'no such column' not in message:
            raise




def _to_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _convert_normalized_to_geo(points_json, calibration_json):
    try:
        points = json.loads(points_json or '[]')
        calibration = json.loads(calibration_json or '[]')
    except (TypeError, ValueError, json.JSONDecodeError):
        return points_json

    if len(calibration) < 2:
        return points_json

    p1, p2 = calibration[0], calibration[1]
    x1, y1 = _to_float(p1.get('x')), _to_float(p1.get('y'))
    x2, y2 = _to_float(p2.get('x')), _to_float(p2.get('y'))
    gx1, gy1 = _to_float(p1.get('coord_x')), _to_float(p1.get('coord_y'))
    gx2, gy2 = _to_float(p2.get('coord_x')), _to_float(p2.get('coord_y'))

    if None in {x1, y1, x2, y2, gx1, gy1, gx2, gy2} or x1 == x2 or y1 == y2:
        return points_json

    def px_to_geo(px, py):
        return {
            'x': gx1 + ((px - x1) / (x2 - x1)) * (gx2 - gx1),
            'y': gy1 + ((py - y1) / (y2 - y1)) * (gy2 - gy1),
        }

    converted = []
    for point in points:
        px, py = _to_float(point.get('x')), _to_float(point.get('y'))
        if px is None or py is None:
            continue
        converted.append(px_to_geo(px, py))
    return json.dumps(converted)


def _migrate_coordinates_to_geo_if_needed():
    if not _has_column('garden_map', 'coordinates_version'):
        return
    gm = db.session.execute(text('SELECT id, calibration_points, boundary_points, coordinates_version FROM garden_map ORDER BY id ASC LIMIT 1')).mappings().first()
    if not gm or (gm['coordinates_version'] or 1) >= 2:
        return

    calibration_points = gm['calibration_points'] or '[]'
    boundary_converted = _convert_normalized_to_geo(gm['boundary_points'] or '[]', calibration_points)
    db.session.execute(text('UPDATE garden_map SET boundary_points=:boundary_points, coordinates_version=2 WHERE id=:id'), {'boundary_points': boundary_converted, 'id': gm['id']})

    locations = db.session.execute(text('SELECT id, polygon_points FROM location')).mappings().all()
    for row in locations:
        db.session.execute(text('UPDATE location SET polygon_points=:polygon_points WHERE id=:id'), {'polygon_points': _convert_normalized_to_geo(row['polygon_points'] or '[]', calibration_points), 'id': row['id']})

    plants = db.session.execute(text('SELECT id, map_x, map_y FROM plant')).mappings().all()
    try:
        calibration = json.loads(calibration_points or '[]')
    except Exception:
        calibration = []
    if len(calibration) >= 2:
        p1, p2 = calibration[0], calibration[1]
        x1, y1 = _to_float(p1.get('x')), _to_float(p1.get('y'))
        x2, y2 = _to_float(p2.get('x')), _to_float(p2.get('y'))
        gx1, gy1 = _to_float(p1.get('coord_x')), _to_float(p1.get('coord_y'))
        gx2, gy2 = _to_float(p2.get('coord_x')), _to_float(p2.get('coord_y'))
        if None not in {x1, y1, x2, y2, gx1, gy1, gx2, gy2} and x1 != x2 and y1 != y2:
            for row in plants:
                px, py = _to_float(row['map_x']), _to_float(row['map_y'])
                if px is None or py is None:
                    continue
                geo_x = gx1 + ((px - x1) / (x2 - x1)) * (gx2 - gx1)
                geo_y = gy1 + ((py - y1) / (y2 - y1)) * (gy2 - gy1)
                db.session.execute(text('UPDATE plant SET map_x=:map_x, map_y=:map_y WHERE id=:id'), {'map_x': geo_x, 'map_y': geo_y, 'id': row['id']})

    db.session.commit()
def create_app():
    app = Flask(__name__, static_folder='static', template_folder='templates')
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-change-me')
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///garden.db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['UPLOAD_FOLDER'] = os.getenv('UPLOAD_FOLDER', '/data/uploads')
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
    app.config['AVATAR_FOLDER'] = os.getenv('AVATAR_FOLDER', '/data/avatars')
    app.config['MAP_FOLDER'] = os.getenv('MAP_FOLDER', '/data/maps')

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
        _ensure_column('location', 'color', "color VARCHAR(7)")
        _ensure_column('location', 'polygon_points', "polygon_points TEXT")
        _ensure_column(
            'plant',
            'creator_id',
            'creator_id INTEGER',
            backfill_sql='UPDATE plant SET creator_id = user_id WHERE creator_id IS NULL'
        )
        _ensure_column('plant', 'map_x', 'map_x FLOAT')
        _ensure_column('plant', 'map_y', 'map_y FLOAT')

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
            CREATE TABLE IF NOT EXISTS garden_map (
                id INTEGER PRIMARY KEY,
                filename VARCHAR(255),
                calibration_points TEXT,
                boundary_points TEXT
            )
        """))
        _ensure_column('garden_map', 'boundary_points', 'boundary_points TEXT')
        _ensure_column('garden_map', 'coordinates_version', 'coordinates_version INTEGER DEFAULT 1')
        _drop_column_if_exists('garden_map', 'user_id')
        if _has_column('plant', 'planting_date'):
            db.session.execute(text("""
                INSERT INTO plant_event (plant_id, event_type, event_at, title, description, creator_id)
                SELECT p.id, 'plant_event', COALESCE(p.planting_date, CURRENT_TIMESTAMP), 'Eingepflanzt', 'Pflanze wurde eingepflanzt.', p.creator_id
                FROM plant p
                WHERE p.planting_date IS NOT NULL
                  AND p.creator_id IS NOT NULL
                  AND NOT EXISTS (SELECT 1 FROM plant_event pe WHERE pe.plant_id = p.id AND pe.title = 'Eingepflanzt')
            """))
        db.session.execute(text("""
            INSERT INTO plant_event (plant_id, event_type, event_at, title, description, attachment_filename, attachment_kind, creator_id)
            SELECT plant_id, 'user_comment', COALESCE(uploaded_at, CURRENT_TIMESTAMP), COALESCE(comment, 'Foto'), comment, filename, 'image', creator_id
            FROM plant_photo pp
            WHERE pp.creator_id IS NOT NULL
              AND NOT EXISTS (SELECT 1 FROM plant_event pe WHERE pe.plant_id = pp.plant_id AND pe.attachment_filename = pp.filename)
        """))
        db.session.execute(text("""
            INSERT INTO plant_event (plant_id, event_type, event_at, title, description, creator_id)
            SELECT plant_id, 'user_comment', COALESCE(created_at, CURRENT_TIMESTAMP), 'Kommentar', comment, creator_id
            FROM plant_note pn
            WHERE pn.creator_id IS NOT NULL
              AND NOT EXISTS (SELECT 1 FROM plant_event pe WHERE pe.plant_id = pn.plant_id AND pe.description = pn.comment AND pe.creator_id = pn.creator_id)
        """))
        _migrate_coordinates_to_geo_if_needed()

        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        os.makedirs(app.config['AVATAR_FOLDER'], exist_ok=True)
        os.makedirs(app.config['MAP_FOLDER'], exist_ok=True)

    return app
