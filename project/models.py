# models.py

from datetime import datetime
from flask_login import UserMixin
from enum import Enum

from . import db

class Role(str, Enum):
    USER = "User"
    ADMIN = "Administrator"

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(100))
    name = db.Column(db.String(100))
    role = db.Column(db.String(20), default=Role.USER)
    cont = db.relationship("Container", backref="User")


class Container(db.Model):
    id = db.Column(db.String(100), primary_key=True)
    port = db.Column(db.Integer)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    container_name = db.Column(db.String(100))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))

