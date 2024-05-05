# models.py

from flask_login import UserMixin
from . import db

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True) # primary keys are required by SQLAlchemy
    email = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(100))
    name = db.Column(db.String(100))
    decisions = db.relationship('Decision', backref='user', lazy='dynamic')

class Decision(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    main_problem = db.Column(db.String(100), nullable=False)
    choice_1 = db.Column(db.String(100), nullable=False)
    choice_2 = db.Column(db.String(100), nullable=False)
    emoji = db.Column(db.String(2), nullable=False)

    num_responses = db.Column(db.Integer, default=0)

    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    evidences = db.relationship('Evidence', backref='decision', lazy='dynamic')
    
    
class Evidence(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.Text, nullable=False)
    decision_id = db.Column(db.Integer, db.ForeignKey('decision.id'), nullable=False)

class Response(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    value = db.Column(db.Float, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    evidence_id = db.Column(db.Integer, db.ForeignKey('evidence.id'), nullable=False)
    decision_id = db.Column(db.Integer, db.ForeignKey('decision.id'), nullable=False)