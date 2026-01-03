from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

# ---------------- USER ----------------
class User(UserMixin, db.Model):
    __tablename__ = "user"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)

    show_global = db.Column(db.Boolean, default=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


# ---------------- DAY PLAN ----------------
class DayPlan(db.Model):
    __tablename__ = "day_plan"
    __table_args__ = (
        db.Index("idx_dayplan_user_date", "user_id", "date"),
    )

    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    final_score = db.Column(db.Integer, default=0)


# ---------------- TASK ----------------
class Task(db.Model):
    __tablename__ = "task"

    id = db.Column(db.Integer, primary_key=True)
    dayplan_id = db.Column(db.Integer, db.ForeignKey("day_plan.id"), nullable=False)

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

    cancel_reason = db.Column(db.String(1000))
    cancel_comment = db.Column(db.Text)

    incomplete_reason = db.Column(db.String(1000))


# ---------------- FRIEND ----------------
class Friend(db.Model):
    __tablename__ = "friend"
    __table_args__ = (
        db.Index("idx_friend_user_status", "user_id", "status"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)      # sender
    friend_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)    # receiver
    status = db.Column(db.String(20), default="pending")  # pending / accepted


# ---------------- NOTIFICATION ----------------
class Notification(db.Model):
    __tablename__ = "notification"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)

    message = db.Column(db.String(200))
    type = db.Column(db.String(50))          # friend_request, etc
    related_id = db.Column(db.Integer)       # Friend.id
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
