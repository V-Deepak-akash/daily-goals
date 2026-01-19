from flask import Flask, render_template, redirect, request, jsonify, url_for
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from models import Notification, db, User, DayPlan, Task, Friend
from datetime import datetime, date, time as dtime, timedelta
import os
import csv
from flask import Response
from sqlalchemy.orm import joinedload
from flask_migrate import Migrate
from sqlalchemy.exc import IntegrityError
from flask_wtf import CSRFProtect
from sqlalchemy import func, or_
from flask_wtf.csrf import generate_csrf

def update_plan_final_score(plan_id):
    score = db.session.query(
        func.coalesce(func.sum(Task.points), 0)
    ).filter(
        Task.dayplan_id == plan_id,
        Task.status == "completed"
    ).scalar()

    DayPlan.query.filter_by(id=plan_id).update(
        {"final_score": score}
    )

def api_ok(**data):
    return jsonify({"ok": True, **data})

def api_error(message, status=400):
    return jsonify({"ok": False, "error": message}), status

def get_task_for_current_user(task_id):
    return (
        Task.query
        .join(DayPlan)
        .filter(
            Task.id == task_id,
            DayPlan.user_id == current_user.id
        )
        .first_or_404()
    )

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
app.config['SECRET_KEY'] = os.environ.get("SECRET_KEY", "dev-secret")
csrf = CSRFProtect(app)

@app.context_processor
def inject_csrf_token():
    return dict(csrf_token=generate_csrf)

app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
    "DATABASE_URL",
    f"sqlite:///{DB_PATH}"
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
migrate = Migrate(app, db)

login_manager = LoginManager(app)
login_manager.login_view = "login"

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ---------------- AUTH ----------------
@csrf.exempt
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

@csrf.exempt
@app.route('/auth/login', methods=['POST'])
def auth_login():
    data = request.form

    user = User.query.filter_by(username=data["username"]).first()
    if not user or not user.check_password(data["password"]):
        return api_error("Invalid credentials", 401)

    login_user(user)
    return api_ok(xp=calculate_xp(current_user.id))

@csrf.exempt
@app.route('/auth/register', methods=['POST'])
def auth_register():
    data = request.get_json()

    if User.query.filter_by(username=data["username"]).first():
        return api_error("Username exists")

    user = User(username=data["username"])
    user.set_password(data["password"])

    db.session.add(user)
    db.session.commit()

    login_user(user)
    return api_ok(xp=calculate_xp(current_user.id))

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
    friends = Friend.query.filter(
        Friend.status == "accepted",
        or_(
            Friend.user_id == current_user.id,
            Friend.friend_id == current_user.id
        )
    ).all()

    for f in friends:
        friend_user_id = (
            f.friend_id if f.user_id == current_user.id else f.user_id
        )
        friend_user = User.query.get(friend_user_id)


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

@app.route("/api/dashboard")
@login_required
def api_dashboard():
    today = date.today()

    # ---------- TODAY PLAN ----------
    plan = DayPlan.query.filter_by(
        user_id=current_user.id,
        date=today
    ).first()

    tasks = Task.query.filter_by(
        dayplan_id=plan.id
    ).all() if plan else []

    today_score = sum(t.points for t in tasks if t.status == "completed")

    # ---------- USER META ----------
    xp = calculate_xp(current_user.id)
    streak = calculate_streak(current_user.id)
    rank = get_rank(xp)

    # ---------- HEATMAP (last 30 days) ----------
    heatmap = []
    for i in range(30):
        d = today - timedelta(days=i)
        p = DayPlan.query.filter_by(
            user_id=current_user.id,
            date=d
        ).first()
        heatmap.append(p.final_score if p else 0)

    heatmap.reverse()

    # ---------- FRIENDS + LEADERBOARD ----------
    leaderboard = []

    # include self
    leaderboard.append({
        "name": current_user.username,
        "streak": streak,
        "score": today_score,
        "is_me": True
    })

    friends = Friend.query.filter(
        Friend.status == "accepted",
        or_(
            Friend.user_id == current_user.id,
            Friend.friend_id == current_user.id
        )
    ).all()

    for f in friends:
        friend_id = (
            f.friend_id if f.user_id == current_user.id else f.user_id
        )
        user = User.query.get(friend_id)

        friend_plan = DayPlan.query.filter_by(
            user_id=user.id,
            date=today
        ).first()

        friend_tasks = Task.query.filter_by(
            dayplan_id=friend_plan.id
        ).all() if friend_plan else []

        leaderboard.append({
            "name": user.username,
            "streak": calculate_streak(user.id),
            "score": sum(t.points for t in friend_tasks if t.status == "completed"),
            "is_me": False
        })

    leaderboard.sort(
        key=lambda x: (x["streak"], x["score"]),
        reverse=True
    )

    # ---------- RESPONSE ----------
    return jsonify({
        "user": {
            "username": current_user.username,
            "xp": xp,
            "rank": rank,
            "streak": streak,
            "today_score": today_score
        },
        "tasks": [
            {
                "id": t.id,
                "title": t.title,
                "desc": t.description,
                "start": t.expected_start.strftime("%H:%M"),
                "end": t.expected_end.strftime("%H:%M"),
                "status": t.status,
                "points": t.points
            } for t in tasks
        ],
        "heatmap": heatmap,
        "leaderboard": leaderboard
    })

# ---------------- PLAN DAY ----------------
@app.route('/plan', methods=['GET', 'POST'])
@login_required
def plan_day():
    if request.method == 'POST':
        plan_date = date.today() + timedelta(days=1)

        if is_plan_locked(plan_date):
            return jsonify({"error": "Planning is locked for today"}), 400

        # Check if plan already exists for the SAME date
        existing_plan = DayPlan.query.filter_by(
            user_id=current_user.id,
            date=plan_date
        ).first()

        if existing_plan:
            return jsonify({"error": "Plan already exists"}), 400

        data = request.get_json()
        if not data or 'tasks' not in data:
            return jsonify({"error": "Invalid request data"}), 400

        total_points = sum(t['points'] for t in data['tasks'])
        if total_points != 100:
            return jsonify({"error": "Total points must be 100"}), 400

        try:
            plan = DayPlan(
                user_id=current_user.id,
                date=plan_date
            )
            db.session.add(plan)
            db.session.flush()  # get plan.id without committing

            for t in data['tasks']:
                task = Task(
                    dayplan_id=plan.id,
                    title=t['title'],
                    description=t.get('description', ''),
                    expected_start=dtime.fromisoformat(t['start']),
                    expected_end=dtime.fromisoformat(t['end']),
                    points=t['points']
                )
                db.session.add(task)

            db.session.commit()
            return jsonify({"status": "saved"}), 201

        except IntegrityError:
            db.session.rollback()
            return jsonify({"error": "Plan already exists"}), 400

        except Exception as e:
            db.session.rollback()
            return jsonify({"error": str(e)}), 500

    return render_template('plan_day.html')

# ---------------- TASK ACTIONS ----------------
@app.route('/task/start/<int:id>', methods=['POST'])
@login_required
def start_task(id):
    task = get_task_for_current_user(id)

    t = request.json['time']
    h, m = map(int, t.split(':'))

    task.actual_start = datetime.combine(date.today(), dtime(h, m))
    task.status = "active"

    db.session.commit()
    return api_ok(xp=calculate_xp(current_user.id))

@app.route('/task/complete/<int:id>', methods=['POST'])
@login_required
def complete_task(id):
    task = get_task_for_current_user(id)

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
    update_plan_final_score(task.dayplan_id)
    db.session.commit()
    return api_ok(xp=calculate_xp(current_user.id))

@app.route('/add-friend', methods=['POST'])
@login_required
def add_friend():
    username = request.form['username']
    receiver = User.query.filter_by(username=username).first()

    if not receiver or receiver.id == current_user.id:
        return api_error("Invalid user")

    a, b = sorted([current_user.id, receiver.id])

    existing = Friend.query.filter_by(
        user_id=a,
        friend_id=b
    ).first()

    if existing:
        if existing.status == "pending":
            return api_error("requested")
        if existing.status == "accepted":
            return api_error("following")

    friend_req = Friend(
        user_id=a,
        friend_id=b,
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
    return api_ok(message="sent",xp=calculate_xp(current_user.id))

@app.route('/task/delete/<int:id>', methods=['POST'])
@login_required
def delete_task(id):
    task = get_task_for_current_user(id)
    if task.status != "pending":
        return api_error("Cannot delete started task", 400)
    plan_id = task.dayplan_id
    db.session.delete(task)
    update_plan_final_score(plan_id)
    db.session.commit()
    return api_ok(xp=calculate_xp(current_user.id))

@app.route('/task/cancel/<int:id>', methods=['POST'])
@login_required
def cancel_task(id):
    task = get_task_for_current_user(id)
    task.status = "cancelled"
    task.cancel_reason = request.json.get("reason")
    task.cancel_comment = request.json.get("comment")
    update_plan_final_score(task.dayplan_id)
    db.session.commit()
    return api_ok(xp=calculate_xp(current_user.id))

@app.route('/task/incomplete/<int:id>', methods=['POST'])
@login_required
def incomplete_task(id):
    task = get_task_for_current_user(id)
    task.status = "incomplete"
    task.incomplete_reason = request.json.get("reason")
    update_plan_final_score(task.dayplan_id)
    db.session.commit()
    return api_ok(xp=calculate_xp(current_user.id))

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
        friends = Friend.query.filter(
            Friend.status == "accepted",
            or_(
                Friend.user_id == current_user.id,
                Friend.friend_id == current_user.id
            )
        ).all()

        users = [current_user]

        for f in friends:
            other_id = (
                f.friend_id if f.user_id == current_user.id else f.user_id
            )
            users.append(User.query.get(other_id))

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
    req = Friend.query.filter(
        Friend.id == id,
        or_(
            Friend.user_id == current_user.id,
            Friend.friend_id == current_user.id
        ),
        Friend.status == "pending"
    ).first_or_404()

    # Accept
    req.status = "accepted"

    # Mark ALL related notifications as read
    Notification.query.filter_by(
        related_id=req.id
    ).update({"is_read": True})

    db.session.commit()
    return api_ok(xp=calculate_xp(current_user.id))

@app.route('/friend/decline/<int:id>', methods=['POST'])
@login_required
def decline_friend(id):
    req = Friend.query.filter(
        Friend.id == id,
        or_(
            Friend.user_id == current_user.id,
            Friend.friend_id == current_user.id
        ),
        Friend.status == "pending"
    ).first_or_404()

    Notification.query.filter_by(
        related_id=req.id
    ).update({"is_read": True})

    db.session.delete(req)
    db.session.commit()
    return api_ok(xp=calculate_xp(current_user.id))

@app.route('/friend/delete/<int:id>', methods=['POST'])
@login_required
def delete_friend(id):
    f = Friend.query.get_or_404(id)

    if current_user.id not in (f.user_id, f.friend_id):
        return api_error("Unauthorized", 403)

    db.session.delete(f)
    db.session.commit()
    return api_ok(xp=calculate_xp(current_user.id))

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
    relations = Friend.query.filter(
        Friend.status == "accepted",
        or_(
            Friend.user_id == current_user.id,
            Friend.friend_id == current_user.id
        )
    ).all()

    followers = []
    for rel in relations:
        user_id = rel.user_id if rel.friend_id == current_user.id else rel.friend_id
        user = User.query.get(user_id)

        # check if I also follow them
        following_back = Friend.query.filter(
            Friend.status == "accepted",
            or_(
                Friend.user_id == current_user.id,
                Friend.friend_id == current_user.id
            )
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
        return api_error("Unauthorized", 403)

    db.session.delete(rel)
    db.session.commit()
    return api_ok(xp=calculate_xp(current_user.id))

@app.route("/service-worker.js")
def sw():
    return app.send_static_file("service-worker.js")

@app.route("/manifest.json")
def manifest():
    return app.send_static_file("manifest.json")

@app.after_request
def add_no_cache_headers(response):
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, private"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

# ---------------- RUN ----------------
if __name__ == '__main__':
    app.run(debug=True)
