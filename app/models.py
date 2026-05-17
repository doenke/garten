from flask_sqlalchemy import SQLAlchemy
from datetime import datetime


db = SQLAlchemy()


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sub = db.Column(db.String(255), unique=True, nullable=False)
    name = db.Column(db.String(255))
    email = db.Column(db.String(255))
    avatar_url = db.Column(db.String(1024))
    avatar_filename = db.Column(db.String(255))


class Location(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    creator_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)


class Plant(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    location_id = db.Column(db.Integer, db.ForeignKey('location.id'), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    common_name = db.Column(db.String(255))
    source = db.Column(db.String(255))
    light_need = db.Column(db.String(128), nullable=False)
    bloom_start_month = db.Column(db.Integer)
    bloom_end_month = db.Column(db.Integer)
    flower_color = db.Column(db.String(64))
    soil = db.Column(db.Text)
    height_without_bloom_cm = db.Column(db.Integer)
    height_with_bloom_cm = db.Column(db.Integer)
    info = db.Column(db.Text)
    creator_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)


class PlantPhoto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    plant_id = db.Column(db.Integer, db.ForeignKey('plant.id'), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    taken_on = db.Column(db.Date)
    comment = db.Column(db.Text)
    creator_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)


class PlantNote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    plant_id = db.Column(db.Integer, db.ForeignKey('plant.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    note_date = db.Column(db.Date, nullable=False)
    comment = db.Column(db.Text, nullable=False)
    creator_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)


class PlantEvent(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    plant_id = db.Column(db.Integer, db.ForeignKey('plant.id'), nullable=False)
    event_type = db.Column(db.String(32), nullable=False)
    event_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    attachment_filename = db.Column(db.String(255))
    attachment_kind = db.Column(db.String(16))
    creator_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
