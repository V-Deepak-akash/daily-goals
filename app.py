from flask import Flask, render_template, redirect, request, jsonify, url_for
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from models import db, User, DayPlan, Task, Friend
from datetime import datetime, date, time
import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "instance", "app.db")

app = Flask(__name__)
app.config['SECRET_KEY'] = 'dev-secret'
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{DB_PATH}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

with app.app_context():
    db.create_all()

login_manager = LoginManager(app)
login_manager.login_view = "login"

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ---------------- AUTH ----------------
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']

        user = User.query.filter_by(username=username).first()
        if not user:
            user = User(username=username)
            db.session.add(user)
            db.session.commit()

        login_user(user)
        return redirect(url_for('dashboard'))

    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect('/login')

# ---------------- DASHBOARD ----------------
@app.route('/')
@login_required
def dashboard():
    today = date.today()

    plan = DayPlan.query.filter_by(
        user_id=current_user.id,
        date=today
    ).first()

    tasks = Task.query.filter_by(
        dayplan_id=plan.id
    ).all() if plan else []

    friends_data = []

    friends = Friend.query.filter_by(user_id=current_user.id).all()
    for f in friends:
        friend_user = User.query.get(f.friend_id)

        friend_plan = DayPlan.query.filter_by(
            user_id=friend_user.id,
            date=today
        ).first()

        friend_tasks = Task.query.filter_by(
            dayplan_id=friend_plan.id
        ).all() if friend_plan else []

        friends_data.append((friend_user, friend_tasks))

    return render_template(
        'dashboard.html',
        tasks=tasks,
        friends_data=friends_data
    )

# ---------------- PLAN DAY ----------------
@app.route('/plan', methods=['GET', 'POST'])
@login_required
def plan_day():
    if request.method == 'POST':
        if DayPlan.query.filter_by(user_id=current_user.id, date=date.today()).first():
            return jsonify({"error": "Plan already exists"})

        plan = DayPlan(user_id=current_user.id, date=date.today())
        db.session.add(plan)
        db.session.commit()

        total = 0
        for t in request.json['tasks']:
            total += t['points']
            task = Task(
                dayplan_id=plan.id,
                title=t['title'],
                description=t['description'],
                expected_start=time.fromisoformat(t['start']),
                expected_end=time.fromisoformat(t['end']),
                points=t['points']
            )
            db.session.add(task)

        if total != 100:
            return jsonify({"error": "Total points must be 100"})

        db.session.commit()
        return jsonify({"status": "saved"})

    return render_template('plan_day.html')

# ---------------- TASK ACTIONS ----------------
@app.route('/task/start/<int:id>', methods=['POST'])
@login_required
def start_task(id):
    task = Task.query.get_or_404(id)
    task.actual_start = datetime.now()
    task.status = "active"
    db.session.commit()
    return jsonify(ok=True)

@app.route('/task/complete/<int:id>', methods=['POST'])
@login_required
def complete_task(id):
    task = Task.query.get_or_404(id)
    task.actual_end = datetime.now()
    task.status = "completed"

    expected_end = datetime.combine(date.today(), task.expected_end)
    delta = task.actual_end - expected_end

    if delta.total_seconds() < 0:
        task.points += int(task.points * 0.1)
    elif delta.total_seconds() > 0:
        task.points -= int(task.points * 0.1)

    db.session.commit()
    return jsonify(points=task.points)

@app.route('/add-friend', methods=['POST'])
@login_required
def add_friend():
    username = request.form['username']

    friend = User.query.filter_by(username=username).first()
    if not friend or friend.id == current_user.id:
        return redirect('/')

    exists = Friend.query.filter_by(
        user_id=current_user.id,
        friend_id=friend.id
    ).first()

    if not exists:
        db.session.add(Friend(
            user_id=current_user.id,
            friend_id=friend.id
        ))
        db.session.commit()

    return redirect('/')

# ---------------- RUN ----------------
if __name__ == '__main__':
    app.run(debug=True)
