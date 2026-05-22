import os
import json
import time
from functools import wraps
from datetime import datetime
from flask import Blueprint, current_app, g, render_template, request, redirect, url_for, session, jsonify, send_from_directory
from .models import db, User, Location, Plant, PlantPhoto, PlantNote, GardenMap, TimelineEntry, LightNeed
from .services.timeline_service import save_uploaded_attachment, set_single_title_entry, delete_timeline_entry, build_unique_upload_name

main_bp = Blueprint('main', __name__)
ALLOWED = {'png', 'jpg', 'jpeg', 'webp', 'gif', 'pdf'}
IMAGE_TYPES = {'png', 'jpg', 'jpeg', 'webp', 'gif'}
ALLOWED_ATTACHMENT_MIME_TYPES = {
    'image/png',
    'image/jpeg',
    'image/webp',
    'image/gif',
    'application/pdf',
}
TRASH_LOCATION_NAME = "Papierkorb"
EVENT_TYPE_MAP = {
    'planting': 'plant_event',
    'outplant': 'plant_event',
    'transplant': 'plant_event',
    'user_comment': 'user_event',
    'care_event': 'care_event',
    'measurement': 'measurement_event',
}

SYSTEM_EVENT_TEMPLATES = {
    'planting': {'title': 'Eingepflanzt', 'description': 'Pflanze wurde eingepflanzt.'},
    'transplant': {'title': 'Umgepflanzt', 'description': 'Pflanze wurde umgepflanzt.'},
    'outplant': {'title': 'Ausgepflanzt', 'description': 'Pflanze wurde ausgepflanzt.'},
}

PLANTING_STATE_TYPES = {
    'Eingepflanzt': 'planting',
    'Umgepflanzt': 'transplant',
    'Ausgepflanzt': 'outplant',
}

_upload_stats_cache = {
    'expires_at': 0.0,
    'upload_folder': None,
    'uploads': 0,
    'upload_size_bytes': 0,
}

LIGHT_NEED_OPTIONS = [
    {'key': 'full_sun', 'label': 'Sonnig', 'icon': '☀️'},
    {'key': 'part_shade', 'label': 'Halbschatten', 'icon': '⛅'},
    {'key': 'shade', 'label': 'Schatten', 'icon': '🌑'},
]
LIGHT_NEED_KEY_TO_LABEL = {item['key']: item['label'] for item in LIGHT_NEED_OPTIONS}
LIGHT_NEED_ICON_BY_KEY = {item['key']: item['icon'] for item in LIGHT_NEED_OPTIONS}


def parse_light_need_keys(values):
    keys = [value.strip() for value in values if value and value.strip() in LIGHT_NEED_KEY_TO_LABEL]
    return keys


def format_light_need_labels(light_needs):
    return ', '.join(light_need.label for light_need in light_needs)


def create_timeline_entry(*, scope_type, scope_id, creator_id, created_at=None, event_at=None, event_type=None, title=None, description=None, attachment_filename=None, attachment_kind=None):
    entry = TimelineEntry(
        scope_type=scope_type,
        scope_id=scope_id,
        created_at=created_at or datetime.utcnow(),
        event_at=event_at,
        event_type=event_type,
        title=title,
        description=description,
        attachment_filename=attachment_filename,
        attachment_kind=attachment_kind,
        creator_id=creator_id,
    )
    db.session.add(entry)
    return entry


def location_sort_criteria():
    return (
        db.case((Location.name == TRASH_LOCATION_NAME, 1), else_=0).asc(),
        Location.name.asc(),
        Location.id.asc(),
    )


def create_system_event(plant_id, key, creator_id, event_at=None, description=None):
    tpl = SYSTEM_EVENT_TEMPLATES[key]
    create_timeline_entry(
        scope_type='plant',
        scope_id=plant_id,
        event_at=event_at or datetime.utcnow(),
        event_type='plant_event',
        title=tpl['title'],
        description=description if description is not None else tpl['description'],
        creator_id=creator_id,
    )

def current_user():
    cached_user_loaded = getattr(g, '_current_user_loaded', False)
    if cached_user_loaded:
        return g._current_user

    uid = session.get('user_id')
    user = User.query.get(uid) if uid else None
    g._current_user = user
    g._current_user_loaded = True
    return user

def login_required(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        if not current_user():
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return wrapped

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED


def widget_api_key_required(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        configured_key = (current_app.config.get('WIDGET_API_KEY') or '').strip()
        if not configured_key:
            return jsonify({'error': 'Widget API key is not configured'}), 503

        api_key = (request.headers.get('X-API-Key') or '').strip()
        if not api_key:
            auth_header = (request.headers.get('Authorization') or '').strip()
            if auth_header.lower().startswith('bearer '):
                api_key = auth_header[7:].strip()

        if api_key != configured_key:
            return jsonify({'error': 'Unauthorized'}), 401
        return f(*args, **kwargs)
    return wrapped


def parse_bloom_months(form):
    bloom_start_month = form.get('bloom_start_month', type=int)
    bloom_end_month = form.get('bloom_end_month', type=int)
    if (bloom_start_month is None) != (bloom_end_month is None):
        return None, None, False
    return bloom_start_month, bloom_end_month, True

def get_or_create_garden_map():
    garden_map = GardenMap.query.order_by(GardenMap.id.asc()).first()
    if garden_map:
        return garden_map
    garden_map = GardenMap(calibration_points='[]', boundary_points='[]')
    db.session.add(garden_map)
    db.session.flush()
    return garden_map

def get_or_create_trash_location():
    trash_locations = Location.query.filter_by(name=TRASH_LOCATION_NAME).order_by(Location.id.asc()).all()
    if trash_locations:
        trash = trash_locations[0]
        for duplicate in trash_locations[1:]:
            Plant.query.filter_by(location_id=duplicate.id).update({'location_id': trash.id})
            db.session.delete(duplicate)
        db.session.flush()
        return trash
    trash = Location(
        name=TRASH_LOCATION_NAME,
        description="Automatisch erstellt. Gelöschte Pflanzen landen hier.",
        user_id=current_user().id,
        creator_id=current_user().id
    )
    db.session.add(trash)
    db.session.flush()
    return trash

@main_bp.route('/healthz')
def healthz():
    try:
        db.session.execute(db.text('SELECT 1'))
        return jsonify({'status': 'ok'}), 200
    except Exception:
        return jsonify({'status': 'error'}), 500


@main_bp.route('/api/stats', methods=['GET'])
@widget_api_key_required
def api_stats():
    plant_count = db.session.query(db.func.count(Plant.id)).scalar() or 0
    bed_count = db.session.query(db.func.count(Location.id)).filter(Location.name != TRASH_LOCATION_NAME).scalar() or 0
    upload_folder = current_app.config.get('UPLOAD_FOLDER')
    cache_ttl = current_app.config.get('STATS_UPLOAD_CACHE_TTL_SECONDS', 60)
    now = time.monotonic()
    should_refresh = (
        _upload_stats_cache['upload_folder'] != upload_folder
        or now >= _upload_stats_cache['expires_at']
    )
    if should_refresh:
        upload_count = 0
        upload_total_size = 0
        if upload_folder and os.path.isdir(upload_folder):
            for root, _, files in os.walk(upload_folder):
                for filename in files:
                    full_path = os.path.join(root, filename)
                    if not os.path.isfile(full_path):
                        continue
                    upload_count += 1
                    upload_total_size += os.path.getsize(full_path)
        _upload_stats_cache['upload_folder'] = upload_folder
        _upload_stats_cache['uploads'] = upload_count
        _upload_stats_cache['upload_size_bytes'] = upload_total_size
        _upload_stats_cache['expires_at'] = now + max(0, cache_ttl)

    upload_count = _upload_stats_cache['uploads']
    upload_total_size = _upload_stats_cache['upload_size_bytes']

    database_size = 0
    db_uri = current_app.config.get('SQLALCHEMY_DATABASE_URI', '')
    if isinstance(db_uri, str) and db_uri.startswith('sqlite:///'):
        sqlite_path = db_uri.replace('sqlite:///', '', 1)
        if sqlite_path and os.path.isfile(sqlite_path):
            database_size = os.path.getsize(sqlite_path)

    return jsonify({
        'plants': plant_count,
        'beds': bed_count,
        'uploads': upload_count,
        'upload_size_bytes': upload_total_size,
        'database_size_bytes': database_size,
    }), 200

@main_bp.route('/manifest.webmanifest')
def manifest():
    return send_from_directory(current_app.static_folder, 'manifest.webmanifest', mimetype='application/manifest+json')

@main_bp.route('/sw.js')
def sw():
    return send_from_directory(current_app.static_folder, 'sw.js', mimetype='application/javascript')


@main_bp.route('/favicon.svg')
def favicon():
    return send_from_directory(current_app.static_folder, 'favicon.svg', mimetype='image/svg+xml')

@main_bp.route('/uploads/<path:filename>')
@login_required
def uploads(filename):
    return send_from_directory(current_app.config['UPLOAD_FOLDER'], filename)

@main_bp.route('/avatars/<path:filename>')
@login_required
def avatars(filename):
    return send_from_directory(current_app.config['AVATAR_FOLDER'], filename)

@main_bp.route('/')
@login_required
def index():
    user = current_user()
    locations = Location.query.order_by(*location_sort_criteria()).all()
    garden_map = GardenMap.query.order_by(GardenMap.id.asc()).first()
    location_plant_counts = {
        location_id: count
        for location_id, count in db.session.query(Plant.location_id, db.func.count(Plant.id)).group_by(Plant.location_id).all()
    }
    plants = (
        db.session.query(Plant, Location)
        .join(Location, Plant.location_id == Location.id)
        .filter(Location.name != TRASH_LOCATION_NAME)
        .order_by(Location.name.asc(), Plant.name.asc())
        .all()
    )
    return render_template(
        'index.html',
        user=user,
        locations=locations,
        location_plant_counts=location_plant_counts,
        garden_map=garden_map,
        plants=plants,
    )


@main_bp.route('/config')
@login_required
def config():
    user = current_user()
    garden_map = GardenMap.query.order_by(GardenMap.id.asc()).first()
    locations = Location.query.order_by(*location_sort_criteria()).all()
    return render_template(
        'config.html',
        user=user,
        garden_map=garden_map,
        locations=locations,
    )

@main_bp.route('/locations/new', methods=['POST'])
@login_required
def new_location():
    user = current_user()
    loc = Location(name=request.form['name'], description=request.form.get('description'), color=request.form.get('color') or '#2f6d40', user_id=user.id, creator_id=user.id)
    db.session.add(loc)
    db.session.commit()
    return redirect(url_for('main.index'))

@main_bp.route('/locations/<int:location_id>')
@login_required
def location_detail(location_id):
    loc = Location.query.get_or_404(location_id)
    plants = Plant.query.filter_by(location_id=loc.id).all()
    plant_ids = [plant.id for plant in plants]
    plant_title_images_by_id = {}
    if plant_ids:
        title_events = (
            TimelineEntry.query
            .filter(
                TimelineEntry.scope_type == 'plant',
                TimelineEntry.scope_id.in_(plant_ids),
                TimelineEntry.is_title_entry.is_(True),
                TimelineEntry.attachment_kind == 'image',
                TimelineEntry.attachment_filename.isnot(None),
            )
            .all()
        )
        plant_title_images_by_id = {
            (event.scope_id if hasattr(event, 'scope_id') else event.plant_id): event.attachment_filename
            for event in title_events
            if event.attachment_filename
        }
    timeline_entries = (
        TimelineEntry.query
        .filter_by(scope_type='location', scope_id=loc.id)
        .order_by(TimelineEntry.created_at.desc())
        .all()
    )
    location_plant_markers = [
        {'id': plant.id, 'name': plant.name, 'map_x': plant.map_x, 'map_y': plant.map_y}
        for plant in plants
    ]
    garden_map = GardenMap.query.order_by(GardenMap.id.asc()).first()
    other_locations = Location.query.filter(Location.id != loc.id).order_by(*location_sort_criteria()).all()
    return render_template(
        'location.html',
        location=loc,
        plants=plants,
        plant_title_images_by_id=plant_title_images_by_id,
        timeline_entries=timeline_entries,
        location_plant_markers=location_plant_markers,
        user=current_user(),
        creators={u.id: u for u in User.query.all()},
        garden_map=garden_map,
        light_need_options=LIGHT_NEED_OPTIONS,
        other_location_polygons=[
            {
                'id': other_loc.id,
                'name': other_loc.name,
                'color': other_loc.color or '#2f6d40',
                'polygon_points': other_loc.polygon_points or '[]',
            }
            for other_loc in other_locations
        ],
    )


@main_bp.route('/locations/<int:location_id>/timeline/new', methods=['POST'])
@login_required
def new_location_timeline_entry(location_id):
    location = Location.query.get_or_404(location_id)
    description = (request.form.get('description') or '').strip()
    attachment = request.files.get('attachment')

    unique = save_uploaded_attachment(
        attachment,
        current_app.config['UPLOAD_FOLDER'],
        ALLOWED,
        ALLOWED_ATTACHMENT_MIME_TYPES,
        current_app.config.get('MAX_ATTACHMENT_SIZE_BYTES'),
    )
    if not description or not unique:
        return redirect(url_for('main.location_detail', location_id=location.id))

    create_timeline_entry(
        scope_type='location',
        scope_id=location.id,
        description=description,
        attachment_filename=unique,
        attachment_kind='image',
        creator_id=current_user().id,
    )
    db.session.commit()
    return redirect(url_for('main.location_detail', location_id=location.id))



@main_bp.route('/locations/<int:location_id>/timeline/<int:entry_id>/set-title', methods=['POST'])
@login_required
def set_location_timeline_title(location_id, entry_id):
    location = Location.query.get_or_404(location_id)
    set_single_title_entry(
        model=TimelineEntry,
        owner_filter=(TimelineEntry.scope_type == 'location', TimelineEntry.scope_id == location.id),
        entry_id_field=TimelineEntry.id,
        entry_id_value=entry_id,
    )
    db.session.commit()
    return redirect(url_for('main.location_detail', location_id=location.id))


@main_bp.route('/locations/<int:location_id>/timeline/<int:entry_id>/delete', methods=['POST'])
@login_required
def delete_location_timeline_entry(location_id, entry_id):
    location = Location.query.get_or_404(location_id)
    entry = TimelineEntry.query.filter_by(id=entry_id, scope_type='location', scope_id=location.id).first_or_404()
    delete_timeline_entry(entry, current_app.config['UPLOAD_FOLDER'], ('attachment_filename',))
    db.session.delete(entry)
    db.session.commit()
    return redirect(url_for('main.location_detail', location_id=location.id))

@main_bp.route('/locations/<int:location_id>/plants/new', methods=['POST'])
@login_required
def new_plant(location_id):
    light_need_keys = parse_light_need_keys(request.form.getlist('light_need'))
    selected_light_needs = LightNeed.query.filter(LightNeed.key.in_(light_need_keys)).order_by(LightNeed.id.asc()).all()
    bloom_start_month, bloom_end_month, bloom_months_valid = parse_bloom_months(request.form)
    if not bloom_months_valid:
        return redirect(url_for('main.location_detail', location_id=location_id))

    p = Plant(
        location_id=location_id,
        name=request.form['name'],
        common_name=request.form.get('common_name'),
        source=request.form.get('source'),
        light_need='',
        bloom_start_month=bloom_start_month,
        bloom_end_month=bloom_end_month,
        flower_color=request.form.get('flower_color'),
        soil=request.form.get('soil'),
        height_without_bloom_cm=request.form.get('height_without_bloom_cm', type=int),
        height_with_bloom_cm=request.form.get('height_with_bloom_cm', type=int),
        info=request.form.get('info'),
        creator_id=current_user().id
    )
    p.light_needs = selected_light_needs
    db.session.add(p)
    db.session.flush()
    event_at = datetime.utcnow()
    tpl = SYSTEM_EVENT_TEMPLATES['planting']
    create_timeline_entry(
        scope_type='plant',
        scope_id=p.id,
        event_at=event_at,
        event_type='plant_event',
        title=tpl['title'],
        description=tpl['description'],
        creator_id=current_user().id
    )
    db.session.commit()
    return redirect(url_for('main.plant_detail', plant_id=p.id))

@main_bp.route('/locations/<int:location_id>/delete', methods=['POST'])
@login_required
def delete_location(location_id):
    location = Location.query.get_or_404(location_id)
    if location.name == TRASH_LOCATION_NAME:
        return redirect(url_for('main.index'))
    trash = get_or_create_trash_location()
    if location.id == trash.id:
        return redirect(url_for('main.index'))
    plants = Plant.query.filter_by(location_id=location.id).all()
    for plant in plants:
        plant.location_id = trash.id
    # Location nur entfernen, wenn keine abhängigen Timeline-Einträge existieren.
    has_timeline_entries = TimelineEntry.query.filter_by(scope_type='location', scope_id=location.id).first() is not None
    if not has_timeline_entries:
        db.session.delete(location)
    db.session.commit()
    return redirect(url_for('main.index'))

@main_bp.route('/plants/<int:plant_id>')
@login_required
def plant_detail(plant_id):
    plant = Plant.query.get_or_404(plant_id)
    events = TimelineEntry.query.filter_by(scope_type='plant', scope_id=plant.id).order_by(TimelineEntry.event_at.desc(), TimelineEntry.created_at.desc()).all()
    photos = PlantPhoto.query.filter_by(plant_id=plant.id).order_by(PlantPhoto.uploaded_at.desc()).all()
    notes = PlantNote.query.filter_by(plant_id=plant.id).order_by(PlantNote.created_at.desc()).all()
    month_names = ['Jan', 'Feb', 'Mär', 'Apr', 'Mai', 'Jun', 'Jul', 'Aug', 'Sep', 'Okt', 'Nov', 'Dez']
    last_plant_event = next((ev for ev in events if ev.event_type == 'plant_event' and ev.title in PLANTING_STATE_TYPES), None)
    is_planted = bool(last_plant_event and PLANTING_STATE_TYPES[last_plant_event.title] in {'planting', 'transplant'})
    location = Location.query.get(plant.location_id)
    garden_map = GardenMap.query.order_by(GardenMap.id.asc()).first()
    location_plants = Plant.query.filter_by(location_id=plant.location_id).order_by(Plant.name.asc()).all()
    location_plant_markers = [
        {'id': item.id, 'name': item.name, 'map_x': item.map_x, 'map_y': item.map_y}
        for item in location_plants
    ]
    title_event = next((event for event in events if event.is_title_entry), None)
    return render_template(
        'plant.html',
        plant=plant,
        location=location,
        events=events,
        photos=photos,
        notes=notes,
        user=current_user(),
        locations=Location.query.order_by(*location_sort_criteria()).all(),
        creators={u.id: u for u in User.query.all()},
        today_date=datetime.utcnow().date().isoformat(),
        month_names=month_names,
        is_planted=is_planted,
        garden_map=garden_map,
        location_plant_markers=location_plant_markers,
        title_event=title_event,
        light_need_options=LIGHT_NEED_OPTIONS,
        light_need_icon_by_key=LIGHT_NEED_ICON_BY_KEY,
    )


@main_bp.route('/maps/<path:filename>')
@login_required
def maps(filename):
    return send_from_directory(current_app.config['MAP_FOLDER'], filename)


@main_bp.route('/map/upload', methods=['POST'])
@login_required
def upload_map():
    file = request.files.get('map_image')
    if file and file.filename and allowed_file(file.filename):
        unique = build_unique_upload_name(file.filename)
        file.save(os.path.join(current_app.config['MAP_FOLDER'], unique))
        garden_map = get_or_create_garden_map()
        garden_map.filename = unique
        db.session.commit()
    return redirect(request.referrer or url_for('main.index'))


@main_bp.route('/map/calibration', methods=['POST'])
@login_required
def save_calibration():
    payload = request.form.get('calibration_points', '[]')
    garden_map = get_or_create_garden_map()
    garden_map.calibration_points = payload
    db.session.commit()
    return redirect(request.referrer or url_for('main.index'))


@main_bp.route('/map/boundary', methods=['POST'])
@login_required
def save_boundary():
    payload = request.form.get('boundary_points', '[]')
    garden_map = get_or_create_garden_map()
    garden_map.boundary_points = payload
    db.session.commit()
    return redirect(request.referrer or url_for('main.config'))


@main_bp.route('/locations/<int:location_id>/map', methods=['POST'])
@login_required
def save_location_map(location_id):
    loc = Location.query.get_or_404(location_id)
    loc.color = request.form.get('color') or '#2f6d40'
    loc.polygon_points = request.form.get('polygon_points') or '[]'
    db.session.commit()
    return redirect(url_for('main.location_detail', location_id=location_id))


@main_bp.route('/locations/<int:location_id>/color', methods=['POST'])
@login_required
def save_location_color(location_id):
    loc = Location.query.get_or_404(location_id)
    if loc.name == TRASH_LOCATION_NAME:
        return redirect(request.referrer or url_for('main.index'))
    loc.color = request.form.get('color') or '#2f6d40'
    db.session.commit()
    return redirect(request.referrer or url_for('main.index'))


@main_bp.route('/plants/<int:plant_id>/position', methods=['POST'])
@login_required
def save_plant_position(plant_id):
    plant = Plant.query.get_or_404(plant_id)
    is_json_request = request.is_json
    payload = request.get_json(silent=True) if is_json_request else None
    plant.map_x = (payload or {}).get('map_x') if is_json_request else request.form.get('map_x', type=float)
    plant.map_y = (payload or {}).get('map_y') if is_json_request else request.form.get('map_y', type=float)
    db.session.commit()
    if is_json_request:
        return jsonify({'ok': True, 'map_x': plant.map_x, 'map_y': plant.map_y})
    return redirect(url_for('main.plant_detail', plant_id=plant_id))



@main_bp.route('/plants/<int:plant_id>/masterdata', methods=['POST'])
@login_required
def update_masterdata(plant_id):
    plant = Plant.query.get_or_404(plant_id)

    field_labels = {
        'name': 'Name',
        'common_name': 'Bürgerlicher Name',
        'source': 'Quelle',
        'light_need': 'Lichtbedarf',
        'bloom_start_month': 'Blütezeit von',
        'bloom_end_month': 'Blütezeit bis',
        'flower_color': 'Blütenfarbe',
        'soil': 'Boden',
        'height_without_bloom_cm': 'Höhe ohne Blüte (cm)',
        'height_with_bloom_cm': 'Höhe mit Blüte (cm)',
        'info': 'Info',
        'map_x': 'Position X (Lat)',
        'map_y': 'Position Y (Lon)',
    }

    bloom_start_month, bloom_end_month, bloom_months_valid = parse_bloom_months(request.form)
    if not bloom_months_valid:
        return redirect(url_for('main.plant_detail', plant_id=plant.id))

    updates = {
        'name': request.form.get('name', '').strip(),
        'common_name': request.form.get('common_name', '').strip() or None,
        'source': request.form.get('source', '').strip() or None,
        'bloom_start_month': bloom_start_month,
        'bloom_end_month': bloom_end_month,
        'flower_color': request.form.get('flower_color', '').strip() or None,
        'soil': request.form.get('soil', '').strip() or None,
        'height_without_bloom_cm': request.form.get('height_without_bloom_cm', type=int),
        'height_with_bloom_cm': request.form.get('height_with_bloom_cm', type=int),
        'info': request.form.get('info', '').strip() or None,
        'map_x': request.form.get('map_x', type=float),
        'map_y': request.form.get('map_y', type=float),
    }

    changes = []
    for field, new_value in updates.items():
        old_value = getattr(plant, field)
        if old_value != new_value:
            old_display = old_value if old_value not in (None, '') else '-'
            new_display = new_value if new_value not in (None, '') else '-'
            changes.append(f"{field_labels[field]}: {old_display} → {new_display}")
            setattr(plant, field, new_value)

    light_need_keys = parse_light_need_keys(request.form.getlist('light_need'))
    new_light_needs = LightNeed.query.filter(LightNeed.key.in_(light_need_keys)).order_by(LightNeed.id.asc()).all()
    old_light_need_display = format_light_need_labels(plant.light_needs) or '-'
    new_light_need_display = format_light_need_labels(new_light_needs) or '-'
    if old_light_need_display != new_light_need_display:
        changes.append(f"Lichtbedarf: {old_light_need_display} → {new_light_need_display}")
        plant.light_needs = new_light_needs
        plant.light_need = ''

    if changes:
        create_timeline_entry(
            scope_type='plant',
            scope_id=plant.id,
            event_type='data_event',
            event_at=datetime.utcnow(),
            title='Pflanzendaten geändert',
            description='\n'.join(changes),
            creator_id=current_user().id
        )

    db.session.commit()
    return redirect(url_for('main.plant_detail', plant_id=plant.id))
@main_bp.route('/plants/<int:plant_id>/delete', methods=['POST'])
@login_required
def delete_plant(plant_id):
    plant = Plant.query.get_or_404(plant_id)
    trash = get_or_create_trash_location()
    if plant.location_id != trash.id:
        create_system_event(plant.id, 'outplant', current_user().id)
    plant.location_id = trash.id
    db.session.commit()
    return redirect(url_for('main.plant_detail', plant_id=plant.id))

@main_bp.route('/plants/<int:plant_id>/move', methods=['POST'])
@login_required
def move_plant(plant_id):
    plant = Plant.query.get_or_404(plant_id)
    target_location_id = request.form.get('location_id', type=int)
    target_location = Location.query.get_or_404(target_location_id)
    source_location = Location.query.get_or_404(plant.location_id)
    user_id = current_user().id
    trash = get_or_create_trash_location()

    if source_location.id != target_location.id:
        if source_location.id == trash.id and target_location.id != trash.id:
            create_system_event(plant.id, 'planting', user_id)
        elif target_location.id == trash.id and source_location.id != trash.id:
            create_system_event(plant.id, 'outplant', user_id)
        elif source_location.id != trash.id and target_location.id != trash.id:
            description = f"Umgepflanzt von Beet {source_location.name} nach Beet {target_location.name}"
            create_system_event(plant.id, 'transplant', user_id, description=description)

    plant.location_id = target_location.id
    db.session.commit()
    return redirect(url_for('main.plant_detail', plant_id=plant.id))

@main_bp.route('/plants/<int:plant_id>/events', methods=['POST'])
@login_required
def add_event(plant_id):
    event_type = 'user_event'
    event_at_raw = request.form.get('event_at')
    event_at = datetime.strptime(event_at_raw, '%Y-%m-%d') if event_at_raw else datetime.utcnow()
    title = request.form.get('title', '').strip()
    description = request.form.get('description', '').strip()

    file = request.files.get('attachment')
    attachment_filename = save_uploaded_attachment(
        file,
        current_app.config['UPLOAD_FOLDER'],
        ALLOWED,
        ALLOWED_ATTACHMENT_MIME_TYPES,
        current_app.config.get('MAX_ATTACHMENT_SIZE_BYTES'),
    )
    attachment_kind = None
    if attachment_filename:
        ext = attachment_filename.rsplit('.', 1)[1].lower()
        attachment_kind = 'image' if ext in IMAGE_TYPES else 'pdf'

    if title or description or attachment_filename:
        create_timeline_entry(scope_type='plant', scope_id=plant_id, event_type=event_type, event_at=event_at, title=title, description=description or None, attachment_filename=attachment_filename, attachment_kind=attachment_kind, creator_id=current_user().id)
        db.session.commit()
    return redirect(url_for('main.plant_detail', plant_id=plant_id))


@main_bp.route('/plants/<int:plant_id>/events/<int:event_id>/set-title', methods=['POST'])
@login_required
def set_plant_event_title(plant_id, event_id):
    plant = Plant.query.get_or_404(plant_id)
    set_single_title_entry(
        model=TimelineEntry,
        owner_filter=(TimelineEntry.scope_type == 'plant', TimelineEntry.scope_id == plant.id),
        entry_id_field=TimelineEntry.id,
        entry_id_value=event_id,
    )
    db.session.commit()
    return redirect(url_for('main.plant_detail', plant_id=plant.id))


@main_bp.route('/plants/<int:plant_id>/events/<int:event_id>/delete', methods=['POST'])
@login_required
def delete_event(plant_id, event_id):
    event = TimelineEntry.query.filter_by(id=event_id, scope_type='plant', scope_id=plant_id).first_or_404()
    delete_timeline_entry(event, current_app.config['UPLOAD_FOLDER'], ('attachment_filename',))
    db.session.delete(event)
    db.session.commit()
    return redirect(url_for('main.plant_detail', plant_id=plant_id))


@main_bp.route('/plants/<int:plant_id>/events/system/<string:event_key>', methods=['POST'])
@login_required
def add_system_event(plant_id, event_key):
    if event_key not in {'planting', 'outplant', 'care_event', 'measurement'}:
        return redirect(url_for('main.plant_detail', plant_id=plant_id))
    if event_key in {'care_event', 'measurement'}:
        titles = {'care_event': 'Pflege', 'measurement': 'Messen'}
        create_timeline_entry(scope_type='plant', scope_id=plant_id, event_type=EVENT_TYPE_MAP[event_key], event_at=datetime.utcnow(), title=titles[event_key], description=None, creator_id=current_user().id)
    else:
        create_system_event(plant_id, event_key, current_user().id)
    db.session.commit()
    return redirect(url_for('main.plant_detail', plant_id=plant_id))
