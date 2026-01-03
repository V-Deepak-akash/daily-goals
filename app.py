from flask import Flask, render_template, redirect, request, jsonify, url_for
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from models import db, User, DayPlan, Task, Friend
from datetime import datetime, date, time as dtime, timedelta
import os
import csv
from flask import Response

def is_plan_locked(plan_date):
    return plan_date <= date.today()

def calculate_streak(user_id):
    streak = 0
    d = date.today()

    while True:
        p = DayPlan.query.filter_by(user_id=user_id, date=d).first()
        if not p or p.final_score < 70:
            break
        streak += 1
        d -= timedelta(days=1)

    return streak

def get_week_range(ref=None):
    ref = ref or date.today()
    start = ref - timedelta(days=ref.weekday())  # Monday
    end = start + timedelta(days=6)
    return start, end

def weekly_stats(user_id, start, end):
    plans = DayPlan.query.filter(
        DayPlan.user_id == user_id,
        DayPlan.date >= start,
        DayPlan.date <= end
    ).all()

    total_score = sum(p.final_score for p in plans)
    completed_days = len([p for p in plans if p.final_score >= 70])

    return {
        "score": total_score,
        "days": completed_days
    }

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

    today_score = sum(t.points for t in tasks if t.status == "completed")

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

        friend_streak = calculate_streak(friend_user.id)

        friends_data.append((friend_user, friend_tasks, friend_streak))

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

    # ---------- HEATMAP ----------
    heatmap = []
    for i in range(30):
        d = today - timedelta(days=i)
        p = DayPlan.query.filter_by(user_id=current_user.id, date=d).first()
        heatmap.append(p.final_score if p else 0)

    heatmap.reverse()

    my_streak = calculate_streak(current_user.id)

    locked = is_plan_locked(today + timedelta(days=1))
    leaderboard = []

    # You
    leaderboard.append({
        "name": current_user.username,
        "streak": my_streak,
        "score": today_score
    })

    # Friends
    for friend_user, friend_tasks, friend_streak in friends_data:
        friend_score = sum(t.points for t in friend_tasks if t.status == "completed")
        leaderboard.append({
            "name": friend_user.username,
            "streak": friend_streak,
            "score": friend_score
        })

    leaderboard.sort(key=lambda x: (x["streak"], x["score"]), reverse=True)


    return render_template(
        'dashboard.html',
        tasks=tasks,
        friends_data=friends_data,
        plan_exists=bool(plan),
        locked=locked,
        summary=summary,
        today_score=today_score,
        heatmap=heatmap,
        my_streak=my_streak,
        leaderboard=leaderboard
    )

# ---------------- PLAN DAY ----------------
@app.route('/plan', methods=['GET', 'POST'])
@login_required
def plan_day():
    if request.method == 'POST':
        plan_date = date.today() + timedelta(days=1)
        if is_plan_locked(plan_date):
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

@app.route('/task/cancel/<int:id>', methods=['POST'])
@login_required
def cancel_task(id):
    task = Task.query.get_or_404(id)
    task.status = "cancelled"
    task.cancel_reason = request.json.get("reason")
    task.cancel_comment = request.json.get("comment")
    db.session.commit()
    return jsonify(ok=True)

@app.route('/task/incomplete/<int:id>', methods=['POST'])
@login_required
def incomplete_task(id):
    task = Task.query.get_or_404(id)
    task.status = "incomplete"
    task.incomplete_reason = request.json.get("reason")
    db.session.commit()
    return jsonify(ok=True)

@app.route('/history')
@login_required
def history():
    date_str = request.args.get("date")
    selected = date.fromisoformat(date_str) if date_str else date.today()

    plan = DayPlan.query.filter_by(user_id=current_user.id, date=selected).first()
    tasks = Task.query.filter_by(dayplan_id=plan.id).all() if plan else []

    return render_template("history.html", tasks=tasks, selected=selected)

@app.route('/analytics')
@login_required
def analytics():
    today = date.today()
    week_start = today - timedelta(days=7)
    month_start = today - timedelta(days=30)

    def stats(start):
        plans = DayPlan.query.filter(
            DayPlan.user_id == current_user.id,
            DayPlan.date >= start
        ).all()

        total = len(plans)
        completed = len([p for p in plans if p.final_score >= 70])
        avg = int(sum(p.final_score for p in plans) / total) if total else 0

        return total, completed, avg

    week = stats(week_start)
    month = stats(month_start)

    return render_template(
        "analytics.html",
        week=week,
        month=month
    )

@app.route('/export')
@login_required
def export():
    period = request.args.get("period", "day")
    today = date.today()

    if period == "week":
        start = today - timedelta(days=7)
    elif period == "month":
        start = today - timedelta(days=30)
    elif period == "year":
        start = today - timedelta(days=365)
    else:
        start = today

    plans = DayPlan.query.filter(
        DayPlan.user_id == current_user.id,
        DayPlan.date >= start
    ).all()

    def generate():
        yield "date,score\n"
        for p in plans:
            yield f"{p.date},{p.final_score}\n"

    return Response(
        generate(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={period}.csv"}
    )

@app.route('/leaderboard')
@login_required
def leaderboard():
    start, end = get_week_range()

    users = {current_user.id: current_user.username}

    friends = Friend.query.filter_by(user_id=current_user.id).all()
    for f in friends:
        u = User.query.get(f.friend_id)
        users[u.id] = u.username

    board = []

    for uid, name in users.items():
        stats = weekly_stats(uid, start, end)
        streak = calculate_streak(uid)

        board.append({
            "name": name,
            "score": stats["score"],
            "days": stats["days"],
            "streak": streak
        })

    # 🔹 SORT LEADERBOARD
    board.sort(
        key=lambda x: (x["score"], x["days"], x["streak"]),
        reverse=True
    )

    # ============================
    # 🏅 BADGES ENGINE (PLACE HERE)
    # ============================

    if board:
        # 🥇 Weekly Champion
        board[0]["badge"] = "🥇 Weekly Champion"

        # 🔥 Consistency King (highest streak)
        max_streak = max(b["streak"] for b in board)
        for b in board:
            if b["streak"] == max_streak and max_streak > 0:
                b["badge"] = b.get("badge", "") + " 🔥 Consistency King"

        # 🎯 Finisher (5+ good days)
        for b in board:
            if b["days"] >= 5:
                b["badge"] = b.get("badge", "") + " 🎯 Finisher"

    # ============================

    return render_template(
        "leaderboard.html",
        board=board,
        start=start,
        end=end
    )

# ---------------- RUN ----------------
if __name__ == '__main__':
    app.run(debug=True)
