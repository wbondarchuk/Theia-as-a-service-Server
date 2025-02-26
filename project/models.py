# models.py

from datetime import datetime
from flask_login import UserMixin

from . import db


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(100))
    name = db.Column(db.String(100))
    cont = db.relationship("Container", backref="User")


class Container(db.Model):
    id = db.Column(db.String(100), primary_key=True)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    container_name = db.Column(db.String(100))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))

