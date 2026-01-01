from flask import Flask, render_template, redirect, request, jsonify, url_for
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from models import db, User, DayPlan, Task, Friend
from datetime import datetime, date, time as dtime, timedelta
import os

def is_plan_locked():
    now = datetime.now().time()
    return now >= dtime(0, 0)  # after midnight

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
        password = request.form['password']
        mode = request.form['mode']

        user = User.query.filter_by(username=username).first()

        if mode == "register":
            if user:
                return render_template("login.html", error="Username already exists")
            user = User(username=username)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            login_user(user)
            return redirect('/')

        # LOGIN MODE
        if not user or not user.check_password(password):
            return render_template("login.html", error="Invalid username or password")

        login_user(user)
        return redirect('/')

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

    # ---------- TODAY ----------
    plan = DayPlan.query.filter_by(
        user_id=current_user.id,
        date=today
    ).first()

    tasks = Task.query.filter_by(
        dayplan_id=plan.id
    ).all() if plan else []

    # ---------- FRIENDS ----------
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

    # ---------- YESTERDAY SUMMARY ----------
    yesterday = today - timedelta(days=1)
    summary = None

    y_plan = DayPlan.query.filter_by(
        user_id=current_user.id,
        date=yesterday
    ).first()

    if y_plan:
        y_tasks = Task.query.filter_by(dayplan_id=y_plan.id).all()

        done = len([t for t in y_tasks if t.status == "completed"])
        total = len(y_tasks)

        planned_time = sum(t.planned_duration_minutes or 0 for t in y_tasks)
        actual_time = sum(t.actual_duration_minutes or 0 for t in y_tasks)

        summary = {
            "percent": int((done / total) * 100) if total else 0,
            "planned": planned_time,
            "actual": actual_time,
            "saved": planned_time - actual_time
        }

    locked = is_plan_locked()

    return render_template(
        'dashboard.html',
        tasks=tasks,
        friends_data=friends_data,
        plan_exists=bool(plan),
        locked=locked,
        summary=summary
    )


# ---------------- PLAN DAY ----------------
@app.route('/plan', methods=['GET', 'POST'])
@login_required
def plan_day():
    if request.method == 'POST':
        if is_plan_locked():
            return jsonify({"error": "Planning is locked for today"})

        if DayPlan.query.filter_by(
        user_id=current_user.id,
        date=date.today()
        ).first():
            return jsonify({"error": "Plan already exists"})


        plan_date = date.today() + timedelta(days=1)
        plan = DayPlan(user_id=current_user.id, date=plan_date)
        db.session.add(plan)
        db.session.commit()

        total = 0
        for t in request.json['tasks']:
            total += t['points']
            task = Task(
                dayplan_id=plan.id,
                title=t['title'],
                description=t['description'],
                expected_start=dtime.fromisoformat(t['start']),
                expected_end=dtime.fromisoformat(t['end']),
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

    t = request.json['time']
    h, m = map(int, t.split(':'))

    task.actual_start = datetime.combine(date.today(), dtime(h, m))
    task.status = "active"

    db.session.commit()
    return jsonify(ok=True)

@app.route('/task/complete/<int:id>', methods=['POST'])
@login_required
def complete_task(id):
    task = Task.query.get_or_404(id)

    t = request.json['time']
    h, m = map(int, t.split(':'))

    task.actual_end = datetime.combine(date.today(), dtime(h, m))
    task.status = "completed"

    planned = (
        datetime.combine(date.today(), task.expected_end) -
        datetime.combine(date.today(), task.expected_start)
    ).seconds // 60

    actual = (task.actual_end - task.actual_start).seconds // 60

    task.planned_duration_minutes = planned
    task.actual_duration_minutes = actual

    db.session.commit()
    return jsonify(ok=True)

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

@app.route('/task/delete/<int:id>', methods=['POST'])
@login_required
def delete_task(id):
    task = Task.query.get_or_404(id)
    if task.status != "pending":
        return jsonify(error="Cannot delete started task")
    db.session.delete(task)
    db.session.commit()
    return jsonify(ok=True)

# ---------------- RUN ----------------
if __name__ == '__main__':
    app.run(debug=True)
