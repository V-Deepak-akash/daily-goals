from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

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

    planned_duration_minutes = db.Column(db.Integer)

    actual_start = db.Column(db.DateTime)
    actual_end = db.Column(db.DateTime)
    actual_duration_minutes = db.Column(db.Integer)

    points = db.Column(db.Integer)
    status = db.Column(db.String(20), default="pending")

    status = db.Column(db.String(20), default="pending")

    cancel_reason = db.Column(db.String(1000))
    cancel_comment = db.Column(db.Text)

    incomplete_reason = db.Column(db.String(1000))


class Friend(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    friend_id = db.Column(db.Integer, db.ForeignKey('user.id'))
