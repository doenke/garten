import os
from functools import wraps
from datetime import datetime
from flask import Blueprint, current_app, render_template, request, redirect, url_for, session, jsonify, send_from_directory
from werkzeug.utils import secure_filename
from .models import db, User, Location, Plant, PlantPhoto, PlantNote, PlantEvent

main_bp = Blueprint('main', __name__)
ALLOWED = {'png', 'jpg', 'jpeg', 'webp', 'gif', 'pdf'}
IMAGE_TYPES = {'png', 'jpg', 'jpeg', 'webp', 'gif'}

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

def current_user():
    uid = session.get('user_id')
    return User.query.get(uid) if uid else None

def login_required(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        if not current_user():
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return wrapped

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED

@main_bp.route('/healthz')
def healthz():
    try:
        db.session.execute(db.text('SELECT 1'))
        return jsonify({'status': 'ok'}), 200
    except Exception:
        return jsonify({'status': 'error'}), 500

@main_bp.route('/manifest.webmanifest')
def manifest():
    return send_from_directory(current_app.static_folder, 'manifest.webmanifest', mimetype='application/manifest+json')

@main_bp.route('/sw.js')
def sw():
    return send_from_directory(current_app.static_folder, 'sw.js', mimetype='application/javascript')

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
    locations = Location.query.all()
    location_plant_counts = {
        location_id: count
        for location_id, count in db.session.query(Plant.location_id, db.func.count(Plant.id)).group_by(Plant.location_id).all()
    }
    return render_template('index.html', user=user, locations=locations, location_plant_counts=location_plant_counts)

@main_bp.route('/locations/new', methods=['POST'])
@login_required
def new_location():
    user = current_user()
    loc = Location(name=request.form['name'], description=request.form.get('description'), user_id=user.id, creator_id=user.id)
    db.session.add(loc)
    db.session.commit()
    return redirect(url_for('main.index'))

@main_bp.route('/locations/<int:location_id>')
@login_required
def location_detail(location_id):
    loc = Location.query.get_or_404(location_id)
    plants = Plant.query.filter_by(location_id=loc.id).all()
    return render_template('location.html', location=loc, plants=plants, user=current_user(), creators={u.id: u for u in User.query.all()})

@main_bp.route('/locations/<int:location_id>/plants/new', methods=['POST'])
@login_required
def new_plant(location_id):
    months = ','.join(request.form.getlist('bloom_months'))
    p = Plant(
        location_id=location_id,
        name=request.form['name'],
        common_name=request.form.get('common_name'),
        source=request.form.get('source'),
        light_need=request.form['light_need'],
        bloom_months=months,
        flower_color=request.form.get('flower_color'),
        info=request.form.get('info'),
        creator_id=current_user().id
    )
    db.session.add(p)
    db.session.flush()
    event_date = request.form.get('planting_date')
    event_at = datetime.strptime(event_date, '%Y-%m-%d') if event_date else datetime.utcnow()
    tpl = SYSTEM_EVENT_TEMPLATES['planting']
    db.session.add(PlantEvent(plant_id=p.id, event_type='plant_event', event_at=event_at, title=tpl['title'], description=tpl['description'], creator_id=current_user().id))
    db.session.commit()
    return redirect(url_for('main.location_detail', location_id=location_id))

@main_bp.route('/locations/<int:location_id>/delete', methods=['POST'])
@login_required
def delete_location(location_id):
    location = Location.query.get_or_404(location_id)
    plants = Plant.query.filter_by(location_id=location.id).all()
    for plant in plants:
        PlantPhoto.query.filter_by(plant_id=plant.id).delete()
        PlantNote.query.filter_by(plant_id=plant.id).delete()
        PlantEvent.query.filter_by(plant_id=plant.id).delete()
        db.session.delete(plant)
    db.session.delete(location)
    db.session.commit()
    return redirect(url_for('main.index'))

@main_bp.route('/plants/<int:plant_id>')
@login_required
def plant_detail(plant_id):
    plant = Plant.query.get_or_404(plant_id)
    events = PlantEvent.query.filter_by(plant_id=plant.id).order_by(PlantEvent.event_at.desc()).all()
    return render_template('plant.html', plant=plant, events=events, user=current_user(), creators={u.id: u for u in User.query.all()}, today_date=datetime.utcnow().date().isoformat())

@main_bp.route('/plants/<int:plant_id>/delete', methods=['POST'])
@login_required
def delete_plant(plant_id):
    plant = Plant.query.get_or_404(plant_id)
    location_id = plant.location_id
    PlantPhoto.query.filter_by(plant_id=plant.id).delete()
    PlantNote.query.filter_by(plant_id=plant.id).delete()
    PlantEvent.query.filter_by(plant_id=plant.id).delete()
    db.session.delete(plant)
    db.session.commit()
    return redirect(url_for('main.location_detail', location_id=location_id))

@main_bp.route('/plants/<int:plant_id>/events', methods=['POST'])
@login_required
def add_event(plant_id):
    selected_type = request.form.get('event_type')
    event_type = EVENT_TYPE_MAP.get(selected_type, 'user_event')
    event_at_raw = request.form.get('event_at')
    event_at = datetime.strptime(event_at_raw, '%Y-%m-%d') if event_at_raw else datetime.utcnow()
    title = request.form.get('title', '').strip()
    description = request.form.get('description', '').strip()

    if selected_type in SYSTEM_EVENT_TEMPLATES:
        title = SYSTEM_EVENT_TEMPLATES[selected_type]['title']
        if not description:
            description = SYSTEM_EVENT_TEMPLATES[selected_type]['description']

    file = request.files.get('attachment')
    attachment_filename = None
    attachment_kind = None
    if file and file.filename and allowed_file(file.filename):
        fn = secure_filename(file.filename)
        unique = f"{datetime.utcnow().timestamp()}_{fn}"
        file.save(os.path.join(current_app.config['UPLOAD_FOLDER'], unique))
        attachment_filename = unique
        ext = fn.rsplit('.', 1)[1].lower()
        attachment_kind = 'image' if ext in IMAGE_TYPES else 'pdf'

    if title or description or attachment_filename:
        db.session.add(PlantEvent(plant_id=plant_id, event_type=event_type, event_at=event_at, title=title or 'Kommentar', description=description or None, attachment_filename=attachment_filename, attachment_kind=attachment_kind, creator_id=current_user().id))
        db.session.commit()
    return redirect(url_for('main.plant_detail', plant_id=plant_id))
