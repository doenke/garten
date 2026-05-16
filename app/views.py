import os
from functools import wraps
from datetime import datetime
from flask import Blueprint, current_app, render_template, request, redirect, url_for, session, jsonify, send_from_directory
from werkzeug.utils import secure_filename
from .models import db, User, Location, Plant, PlantPhoto, PlantNote

main_bp = Blueprint('main', __name__)
ALLOWED = {'png', 'jpg', 'jpeg', 'webp', 'gif'}

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
    return render_template(
        'index.html',
        user=user,
        locations=locations,
        creators={u.id: u for u in User.query.all()},
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
    months = ','.join(request.form.getlist('bloom_months'))
    planting_date = request.form.get('planting_date') or None
    p = Plant(
        location_id=location_id,
        name=request.form['name'],
        common_name=request.form.get('common_name'),
        planting_date=datetime.strptime(planting_date, '%Y-%m-%d').date() if planting_date else None,
        source=request.form.get('source'),
        light_need=request.form['light_need'],
        bloom_months=months,
        flower_color=request.form.get('flower_color'),
        info=request.form.get('info'),
        creator_id=current_user().id
    )
    db.session.add(p)
    db.session.commit()
    return redirect(url_for('main.location_detail', location_id=location_id))

@main_bp.route('/plants/<int:plant_id>')
@login_required
def plant_detail(plant_id):
    plant = Plant.query.get_or_404(plant_id)
    photos = PlantPhoto.query.filter_by(plant_id=plant.id).order_by(PlantPhoto.uploaded_at.desc()).all()
    notes = PlantNote.query.filter_by(plant_id=plant.id).order_by(PlantNote.created_at.desc()).all()
    return render_template('plant.html', plant=plant, photos=photos, notes=notes, user=current_user(), creators={u.id: u for u in User.query.all()})

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
