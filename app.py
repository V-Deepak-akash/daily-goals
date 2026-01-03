from flask import Flask, render_template, redirect, request, jsonify, url_for
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from models import Notification, db, User, DayPlan, Task, Friend
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

def calculate_xp(user_id):
    plans = DayPlan.query.filter_by(user_id=user_id).all()

    xp = 0
    for p in plans:
        xp += sum(t.points for t in Task.query.filter_by(
            dayplan_id=p.id, status="completed"
        ).all()) // 10 * 10  # task XP

        if p.final_score >= 70:
            xp += 50

    xp += calculate_streak(user_id) * 5
    return xp

def get_rank(xp):
    if xp >= 3000:
        return "👑 Legend"
    if xp >= 1500:
        return "🔥 Elite"
    if xp >= 700:
        return "🧠 Strategist"
    if xp >= 300:
        return "⚔️ Warrior"
    return "🪴 Beginner"

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
    friends = Friend.query.filter_by(
        user_id=current_user.id,
        status="accepted"
    ).all()


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

        friends_data.append((f, friend_user, friend_tasks, friend_streak))

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
    for rel, friend_user, friend_tasks, friend_streak in friends_data:
        friend_score = sum(t.points for t in friend_tasks if t.status == "completed")
        leaderboard.append({
            "name": friend_user.username,
            "streak": friend_streak,
            "score": friend_score
        })


    leaderboard.sort(key=lambda x: (x["streak"], x["score"]), reverse=True)

    xp = calculate_xp(current_user.id)
    rank = get_rank(xp)
    notifications = Notification.query.filter_by(
        user_id=current_user.id,
        is_read=False
    ).all()

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
        leaderboard=leaderboard,
        xp=xp,
        rank=rank,
        notifications=notifications
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
    receiver = User.query.filter_by(username=username).first()

    if not receiver or receiver.id == current_user.id:
        return redirect(url_for("dashboard"))

    existing = Friend.query.filter_by(
        user_id=current_user.id,
        friend_id=receiver.id
    ).first()

    if existing:
        if existing.status == "pending":
            return redirect(url_for("dashboard", msg="requested"))
        if existing.status == "accepted":
            return redirect(url_for("dashboard", msg="following"))

    friend_req = Friend(
        user_id=current_user.id,
        friend_id=receiver.id,
        status="pending"
    )
    db.session.add(friend_req)
    db.session.flush()

    db.session.add(Notification(
        user_id=receiver.id,
        message=f"{current_user.username} sent you a friend request",
        type="friend_request",
        related_id=friend_req.id
    ))

    db.session.commit()
    return redirect(url_for("dashboard", msg="sent"))

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
    scope = request.args.get("scope", "friends")
    period = request.args.get("period", "week")

    today = date.today()

    # ---------------- PERIOD RANGE ----------------
    if period == "day":
        start = end = today
    elif period == "month":
        start = today - timedelta(days=30)
        end = today
    else:  # week
        start, end = get_week_range(today)

    # ---------------- USER SCOPE ----------------
    if scope == "global":
        users = User.query.filter_by(show_global=True).all()
    else:
        friends = Friend.query.filter_by(
            user_id=current_user.id,
            status="accepted"
        ).all()
        users = [current_user] + [
            User.query.get(f.friend_id) for f in friends
        ]

    board = []

    # ---------------- BUILD BOARD ----------------
    for u in users:
        stats = weekly_stats(u.id, start, end)
        streak = calculate_streak(u.id)
        xp = calculate_xp(u.id)
        rank = get_rank(xp)

        board.append({
            "user_id": u.id,
            "name": u.username,
            "score": stats["score"],
            "days": stats["days"],
            "streak": streak,
            "xp": xp,
            "rank": rank
        })

    # ---------------- SORT ----------------
    board.sort(
        key=lambda x: (x["score"], x["days"], x["streak"]),
        reverse=True
    )

    # ---------------- POSITION & SELF ENTRY ----------------
    my_entry = None
    for idx, row in enumerate(board):
        row["position"] = idx + 1
        if row["user_id"] == current_user.id:
            my_entry = row

    # ---------------- BADGES ----------------
    if board:
        if period == "day":
            board[0]["badge"] = "🥇 Daily Champion"
        elif period == "month":
            board[0]["badge"] = "🏆 Monthly Champion"
        else:
            board[0]["badge"] = "🥇 Weekly Champion"

    # ---------------- TOP 100 LOGIC (GLOBAL ONLY) ----------------
    if scope == "global":
        top_100 = board[:100]

        # user NOT in top 100 → show separately
        if my_entry and my_entry["position"] > 100:
            return render_template(
                "leaderboard.html",
                board=top_100,
                my_entry=my_entry,
                start=start,
                end=end,
                scope=scope,
                period=period
            )

        # user IN top 100 → mark for sticky UX
        for row in top_100:
            if row["user_id"] == current_user.id:
                row["is_me"] = True

        return render_template(
            "leaderboard.html",
            board=top_100,
            start=start,
            end=end,
            scope=scope,
            period=period
        )

    # ---------------- FRIENDS LEADERBOARD ----------------
    return render_template(
        "leaderboard.html",
        board=board,
        start=start,
        end=end,
        scope=scope,
        period=period
    )

@app.route('/friend/accept/<int:id>', methods=['POST'])
@login_required
def accept_friend(id):
    req = Friend.query.get_or_404(id)

    if req.friend_id != current_user.id:
        return jsonify(error="Unauthorized")

    req.status = "accepted"

    # ✅ mark notification as read
    Notification.query.filter_by(
        related_id=req.id,
        user_id=current_user.id
    ).update({"is_read": True})

    db.session.commit()
    return jsonify(ok=True)

@app.route('/friend/decline/<int:id>', methods=['POST'])
@login_required
def decline_friend(id):
    req = Friend.query.get_or_404(id)

    if req.friend_id != current_user.id:
        return jsonify(error="Unauthorized")

    # delete request
    db.session.delete(req)

    # ✅ mark notification as read
    Notification.query.filter_by(
        related_id=id,
        user_id=current_user.id
    ).update({"is_read": True})

    db.session.commit()
    return jsonify(ok=True)

@app.route('/friend/delete/<int:id>', methods=['POST'])
@login_required
def delete_friend(id):
    f = Friend.query.get_or_404(id)

    if f.user_id != current_user.id:
        return jsonify(error="Unauthorized")

    db.session.delete(f)
    db.session.commit()
    return jsonify(ok=True)

@app.route('/privacy/global', methods=['POST'])
@login_required
def toggle_global_privacy():
    data = request.get_json()
    value = data.get("show_global")

    if value is None:
        return jsonify(error="Invalid request"), 400

    current_user.show_global = bool(value)
    db.session.commit()

    return jsonify(ok=True, show_global=current_user.show_global)

@app.route('/followers')
@login_required
def followers():
    # users who follow ME
    relations = Friend.query.filter_by(
        friend_id=current_user.id,
        status="accepted"
    ).all()

    followers = []
    for rel in relations:
        user = User.query.get(rel.user_id)

        # check if I also follow them
        following_back = Friend.query.filter_by(
            user_id=current_user.id,
            friend_id=user.id,
            status="accepted"
        ).first() is not None

        followers.append({
            "rel_id": rel.id,
            "id": user.id,
            "username": user.username,
            "following_back": following_back
        })

    return jsonify(followers)

@app.route('/follower/remove/<int:rel_id>', methods=['POST'])
@login_required
def remove_follower(rel_id):
    rel = Friend.query.get_or_404(rel_id)

    # only YOU can remove someone who follows YOU
    if rel.friend_id != current_user.id:
        return jsonify(error="Unauthorized"), 403

    db.session.delete(rel)
    db.session.commit()
    return jsonify(ok=True)

# ---------------- RUN ----------------
if __name__ == '__main__':
    app.run(debug=True)
