import os
from functools import wraps
from datetime import datetime
from flask import Blueprint, current_app, render_template, request, redirect, url_for, session, jsonify, send_from_directory
from werkzeug.utils import secure_filename
from .models import db, User, Location, Plant, PlantPhoto, PlantNote

main_bp = Blueprint('main', __name__)
ALLOWED = {'png', 'jpg', 'jpeg', 'webp', 'gif'}
TRASH_LOCATION_NAME = "Papierkorb"

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

def get_or_create_trash_location(user_id):
    trash = Location.query.filter_by(user_id=user_id, name=TRASH_LOCATION_NAME).first()
    if trash:
        return trash
    trash = Location(
        name=TRASH_LOCATION_NAME,
        description="Automatisch erstellt. Gelöschte Pflanzen landen hier.",
        user_id=user_id,
        creator_id=user_id
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
    return render_template(
        'index.html',
        user=user,
        locations=locations,
        location_plant_counts=location_plant_counts,
    )

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
    planting_date = request.form.get('planting_date') or None
    light_needs = request.form.getlist('light_need')
    if not light_needs:
        light_needs = ['Unbekannt']
    p = Plant(
        location_id=location_id,
        name=request.form['name'],
        common_name=request.form.get('common_name'),
        planting_date=datetime.strptime(planting_date, '%Y-%m-%d').date() if planting_date else None,
        source=request.form.get('source'),
        light_need=', '.join(light_needs),
        bloom_start_month=request.form.get('bloom_start_month', type=int),
        bloom_end_month=request.form.get('bloom_end_month', type=int),
        flower_color=request.form.get('flower_color'),
        soil=request.form.get('soil'),
        height_without_bloom_cm=request.form.get('height_without_bloom_cm', type=int),
        height_with_bloom_cm=request.form.get('height_with_bloom_cm', type=int),
        info=request.form.get('info'),
        creator_id=current_user().id
    )
    db.session.add(p)
    db.session.commit()
    return redirect(url_for('main.location_detail', location_id=location_id))

@main_bp.route('/locations/<int:location_id>/delete', methods=['POST'])
@login_required
def delete_location(location_id):
    location = Location.query.get_or_404(location_id)
    if location.name == TRASH_LOCATION_NAME:
        return redirect(url_for('main.index'))
    trash = get_or_create_trash_location(location.user_id)
    plants = Plant.query.filter_by(location_id=location.id).all()
    for plant in plants:
        plant.location_id = trash.id
    db.session.delete(location)
    db.session.commit()
    return redirect(url_for('main.index'))

@main_bp.route('/plants/<int:plant_id>')
@login_required
def plant_detail(plant_id):
    plant = Plant.query.get_or_404(plant_id)
    photos = PlantPhoto.query.filter_by(plant_id=plant.id).order_by(PlantPhoto.uploaded_at.desc()).all()
    notes = PlantNote.query.filter_by(plant_id=plant.id).order_by(PlantNote.created_at.desc()).all()
    month_names = ['Jan', 'Feb', 'Mär', 'Apr', 'Mai', 'Jun', 'Jul', 'Aug', 'Sep', 'Okt', 'Nov', 'Dez']
    return render_template(
        'plant.html',
        plant=plant,
        photos=photos,
        notes=notes,
        user=current_user(),
        locations=Location.query.order_by(Location.name.asc()).all(),
        creators={u.id: u for u in User.query.all()},
        today_date=datetime.utcnow().date().isoformat(),
        month_names=month_names,
    )

@main_bp.route('/plants/<int:plant_id>/delete', methods=['POST'])
@login_required
def delete_plant(plant_id):
    plant = Plant.query.get_or_404(plant_id)
    trash = get_or_create_trash_location(current_user().id)
    plant.location_id = trash.id
    db.session.commit()
    return redirect(url_for('main.plant_detail', plant_id=plant.id))

@main_bp.route('/plants/<int:plant_id>/move', methods=['POST'])
@login_required
def move_plant(plant_id):
    plant = Plant.query.get_or_404(plant_id)
    target_location_id = request.form.get('location_id', type=int)
    target_location = Location.query.get_or_404(target_location_id)
    plant.location_id = target_location.id
    db.session.commit()
    return redirect(url_for('main.plant_detail', plant_id=plant.id))

@main_bp.route('/plants/<int:plant_id>/photos', methods=['POST'])
@login_required
def upload_photo(plant_id):
    file = request.files.get('photo')
    if file and allowed_file(file.filename):
        fn = secure_filename(file.filename)
        unique = f"{datetime.utcnow().timestamp()}_{fn}"
        file.save(os.path.join(current_app.config['UPLOAD_FOLDER'], unique))
        taken_on = request.form.get('taken_on') or None
        photo = PlantPhoto(plant_id=plant_id, filename=unique, taken_on=datetime.strptime(taken_on, '%Y-%m-%d').date() if taken_on else None, comment=request.form.get('comment'), creator_id=current_user().id)
        db.session.add(photo)
        db.session.commit()
    return redirect(url_for('main.plant_detail', plant_id=plant_id))

@main_bp.route('/plants/<int:plant_id>/notes', methods=['POST'])
@login_required
def add_note(plant_id):
    comment = request.form.get('comment', '').strip()
    if comment:
        note_date = request.form.get('note_date') or None
        note = PlantNote(plant_id=plant_id, comment=comment, note_date=datetime.strptime(note_date, '%Y-%m-%d').date() if note_date else datetime.utcnow().date(), creator_id=current_user().id)
        db.session.add(note)
        db.session.commit()
    return redirect(url_for('main.plant_detail', plant_id=plant_id))
