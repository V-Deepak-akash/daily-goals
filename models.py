from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True)

class DayPlan(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    final_score = db.Column(db.Integer, default=0)

class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    dayplan_id = db.Column(db.Integer, db.ForeignKey('day_plan.id'))
    title = db.Column(db.String(100))
    description = db.Column(db.Text)
    expected_start = db.Column(db.Time)
    expected_end = db.Column(db.Time)
    points = db.Column(db.Integer)
    actual_start = db.Column(db.DateTime)
    actual_end = db.Column(db.DateTime)
    status = db.Column(db.String(20), default="pending")
class Friend(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    friend_id = db.Column(db.Integer, db.ForeignKey('user.id'))
