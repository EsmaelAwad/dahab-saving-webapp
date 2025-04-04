from collections import defaultdict
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from contextlib import asynccontextmanager
from app.database import get_session, engine
from app.models import User, AuthorizedUser, Deposit
from sqlmodel import Session, select
from app.database import create_db_and_tables
from app.crud import deauthorize_user, get_user_by_username, create_user, is_authorized, get_all_users, authorize_user, save_deposit, get_paid_week_dates

from app.crud import update_user_password
from typing import Optional , List 
from app.utils import get_all_saving_weeks, read_env_file, compute_streaks
from datetime import datetime, date 

import os
from dotenv import load_dotenv

# Try loading from .env in project root (for local dev)
load_dotenv()

# If running on Render, this will override with real secrets
load_dotenv("/etc/secrets/.env", override=True)

ADMIN_NAME = os.getenv('ADMIN_NAME')
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL")
ADMIN_GITHUB = os.getenv("ADMIN_GITHUB")
TARGET_SAVING_AMOUNT = read_env_file('global.env').get('TARGET_SAVING_AMOUNT', 4000)
START_DATE = datetime.strptime(read_env_file('global.env').get('START_DATE', '2025-04-07'), '%Y-%m-%d').date()
END_DATE = datetime.strptime(read_env_file('global.env').get('END_DATE', '2026-12-31'), '%Y-%m-%d').date()
DEADLINE = datetime.strptime(read_env_file('global.env').get('EXPECTED_DEADLINE_FOR_TRAVEL', '2025-10-18'), '%Y-%m-%d').date()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # ✅ Run this at startup
    create_db_and_tables()
    yield

app = FastAPI(lifespan=lifespan)

# Mount static folder to serve images, CSS, etc.
app.mount("/static", StaticFiles(directory="app/static"), name="static")


# Point to the templates folder
templates = Jinja2Templates(directory="app/templates")

def get_logged_in_user(request: Request) -> Optional[str]:
    return request.cookies.get("username")

@app.get("/", response_class=HTMLResponse)
def login_page(request: Request):
    message = request.cookies.get("message")
    response = templates.TemplateResponse("login.html", {
        "request": request,
        "message": message
    })
    response.delete_cookie("message")
    return response

@app.get("/admin-access", response_class=HTMLResponse)
def admin_panel(request: Request):
    current_user = get_logged_in_user(request)
    if current_user is None or current_user.lower() != os.getenv("ADMIN_PANEL_NAME", "").lower():
        return HTMLResponse("Access denied", status_code=403)

    users = get_all_users()
    authorized = [user.username for user in get_session().exec(select(AuthorizedUser)).all()]
    return templates.TemplateResponse("admin_panel.html", {
        "request": request,
        "users": users,
        "authorized": authorized
    })


# Adding the register page route
@app.get("/register", response_class=HTMLResponse)
def register_page(request: Request, username: str = ""):
    return templates.TemplateResponse("register.html", {
        "request": request,
        "username": username
    })
# Adding resetting password functionality and rendering page.
@app.get("/reset-password", response_class=HTMLResponse)
def reset_password_page(request: Request, username: str = ""):
    return templates.TemplateResponse("reset_password.html", {
        "request": request,
        "username": username
    })

@app.post("/login", response_class=HTMLResponse)
def login_user(
    request: Request,
    username: str = Form(...),
    password: str = Form(...)
):
    user = get_user_by_username(username)
    if not user:
        return RedirectResponse(url=f"/register?username={username}", status_code=302)
    if user.password != password:
        return templates.TemplateResponse("login.html", {
            "request": request,
            "message": (
                "Wrong password. Try again or "
                f"<a href='/reset-password?username={username}'>reset your password</a>."
            )
        })
    if not is_authorized(username):
        return templates.TemplateResponse("login.html", {
            "request": request,
            "message": (
                "You’re registered but not authorized to access the app yet. "
                "Please contact the admin to get access: "
                f"<a href='{ADMIN_GITHUB}' target='_blank'>{ADMIN_NAME} on GitHub</a>"
                " Or you can send an email to this address: "
                f"<a href='mailto:{ADMIN_EMAIL}'>{ADMIN_EMAIL}</a>"
            )
        })

    response = RedirectResponse(url="/dashboard", status_code=302)
    response.set_cookie("username", username,
                         httponly=True,
    secure=True,         # 🔐 Required for HTTPS
    samesite="Lax"       # 👈 Optional but recommended
    )
    return response

@app.post("/register", response_class=HTMLResponse)
def register_user(
    request: Request,
    username: str = Form(...),
    password: str = Form(...)
):
    existing = get_user_by_username(username)
    if existing:
        return templates.TemplateResponse("register.html", {
            "request": request,
            "message": "User already exists. Please log in instead.",
            "username": username
        })

    create_user(username, password)

    # Redirect to login page with success message
    response = RedirectResponse(url="/", status_code=302)
    response.set_cookie("message", "Account created! You can log in now.",
                         httponly=True,
                        secure=True,         # 🔐 Required for HTTPS
                        samesite="Lax"       # 👈 Optional but recommended
                        )
    return response

@app.post("/reset-password", response_class=HTMLResponse)
def reset_password(
    request: Request,
    username: str = Form(...),
    new_password: str = Form(...),
    confirm_password: str = Form(...)
):
    if new_password != confirm_password:
        return templates.TemplateResponse("reset_password.html", {
            "request": request,
            "username": username,
            "message": "Passwords do not match. Try again!"
        })

    user = get_user_by_username(username)
    if not user:
        return templates.TemplateResponse("reset_password.html", {
            "request": request,
            "message": "User not found. Try again."
        })

    update_user_password(username, new_password)
    response = RedirectResponse(url="/", status_code=302)
    response.set_cookie("message", "Password reset! You can now log in.",
                         httponly=True,
                            secure=True,         # 🔐 Required for HTTPS
                            samesite="Lax"       # 👈 Optional but recommended
                        )
    return response

@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request):
    username = request.cookies.get("username")
    if not username:
        return RedirectResponse(url="/", status_code=302)

    # Load message from cookie
    message = request.cookies.get("message")
    
    # Weeks logic
    all_weeks = get_all_saving_weeks()
    paid_weeks = get_paid_week_dates(username)
    unpaid_weeks = [w for w in all_weeks if w not in paid_weeks and w < date.today()]
    next_unpaid = unpaid_weeks[0] if unpaid_weeks else None

    # Total saved
    with get_session() as session:
        statement = select(Deposit).where(Deposit.username == username)
        deposits = session.exec(statement).all()

    total_saved = sum(d.amount for d in deposits)
    recent_deposits = sorted(deposits, key=lambda d: d.timestamp, reverse=True)[:5]

    # Progress logic
    progress_percent = round(min(total_saved / TARGET_SAVING_AMOUNT * 100, 100))
    if progress_percent >= 90:
        progress_color = "green"
    elif progress_percent >= 75:
        progress_color = "gold"
    elif progress_percent >= 50:
        progress_color = "orange"
    else:
        progress_color = "red"

    # Weekly needed logic
    today = date.today()
    deadline = DEADLINE
    weeks_remaining = max((deadline - today).days // 7, 1)
    weekly_needed = round((TARGET_SAVING_AMOUNT - total_saved) / weeks_remaining, 2) if total_saved < 4000 else 0

    response = templates.TemplateResponse("dashboard.html", {
        "request": request,
        "logged_in_user": username,
        "total_saved": total_saved,
        "progress_percent": progress_percent,
        "progress_color": progress_color,
        "weeks_remaining": weeks_remaining,
        "weekly_needed": weekly_needed,
        "recent_deposits": recent_deposits,
        "next_unpaid": next_unpaid,
        "unpaid_weeks": [w.strftime("%B %d, %Y") for w in unpaid_weeks],
        "saving_weeks": all_weeks,
        "message": message,
    })

    response.delete_cookie("message")
    return response

@app.post("/deposit", response_class=HTMLResponse)
def submit_deposit(
    request: Request,
    username: str = Form(...),
    amount: float = Form(...),
    selected_weeks: List[str] = Form([])  # Dates as strings like '2025-04-07'
):
    all_weeks = get_all_saving_weeks()
    paid_weeks = get_paid_week_dates(username)
    today = datetime.now().date()
    unpaid_weeks = [w for w in all_weeks if w not in paid_weeks and w < today]

    deposit_summary = ""
    unpaid_status = ""

    # Build unpaid weeks status
    if unpaid_weeks:
        unpaid_status = f"You currently have {len(unpaid_weeks)} unpaid week(s): " + \
                        ", ".join([w.strftime('%b %d') for w in unpaid_weeks])
    else:
        unpaid_status = "You're fully up-to-date! No unpaid weeks."

    deposits = []

    if selected_weeks:
        # Parse the selected week dates
        parsed_weeks = [datetime.strptime(w, "%Y-%m-%d").date() for w in selected_weeks]
        parsed_weeks.sort()
        per_week = round(amount / len(parsed_weeks), 2)

        for week_date in parsed_weeks:
            save_deposit(username, per_week, week_date=week_date)
            deposits.append((week_date, per_week))

        deposit_summary = f"You paid {amount:.2f} EGP for {len(parsed_weeks)} week(s): " + \
                          ", ".join([f"{d[0].strftime('%b %d')} ({d[1]} EGP)" for d in deposits])

    else:
        # No weeks selected → auto-assign to first unpaid week
        if not unpaid_weeks:
            deposit_summary = "You didn't pick a week, and you've already paid for all weeks."
        else:
            auto_week = unpaid_weeks[0]
            save_deposit(username, amount, week_date=auto_week)
            deposit_summary = f"You didn't pick a week, so we assigned your deposit to {auto_week.strftime('%B %d')}."

    # Combine both into final message
    full_message = f"{deposit_summary}<br><br>{unpaid_status}"

    response = response = RedirectResponse(url="/leaderboard", status_code=302)
    response.set_cookie("message", full_message,
                         httponly=True,
                        secure=True,         # 🔐 Required for HTTPS
                        samesite="Lax"       # 👈 Optional but recommended
                    )
    return response

@app.post("/authorize/{username}", response_class=HTMLResponse)
def do_authorize_user(username: str, request: Request):
    # Again, hardcoded for now
    current_user = get_logged_in_user(request)
    if current_user.lower() != os.getenv("ADMIN_PANEL_NAME", "").lower():
        return HTMLResponse("Access denied", status_code=403)

    authorize_user(username)
    return RedirectResponse("/admin-access", status_code=302)

@app.post("/deauthorize/{username}", response_class=HTMLResponse)
def do_deauthorize_user(username: str, request: Request):
    current_user = get_logged_in_user(request)
    if current_user is None or current_user.lower() != os.getenv("ADMIN_PANEL_NAME", "").lower():
        return HTMLResponse("Access denied", status_code=403)

    deauthorize_user(username)
    return RedirectResponse("/admin-access", status_code=302)

@app.get('/leaderboard', response_class=HTMLResponse)
def leaderboard(request: Request):
    with Session(engine) as session:
        # Fetch all deposit data
        deposits = session.exec(select(Deposit)).all()

        user_totals = defaultdict(float)
        user_deposits = defaultdict(list)
        
        for dep in deposits:
            user_totals[dep.username] += dep.amount
            if dep.week_date:
                user_deposits[dep.username].append({
                    "date": dep.week_date.isoformat(),
                    "amount": dep.amount
                })
        print(user_deposits)
        # Sort by most saved
        sorted_users = sorted(user_totals.items(), key=lambda x: x[1], reverse=True)
        usernames = [u for u, _ in sorted_users]
        saved_amounts = [round(s, 2) for _, s in sorted_users]

        # Add current user’s data
        current_user = get_logged_in_user(request)
        # Build full heatmap for user
        all_weeks = get_all_saving_weeks()
        deposits_by_week = defaultdict(float)
        for d in user_deposits.get(current_user, []):
            deposits_by_week[d["date"]] += d["amount"]

        heatmap_data = []
        for week in all_weeks:
            iso = week.isoformat()
            heatmap_data.append({
                "date": iso,
                "amount": round(deposits_by_week.get(iso, 0), 2)
            })
        user_streaks = {
            username: compute_streaks(deps, saving_weeks=all_weeks)
            for username, deps in user_deposits.items()
        }
        # Sort by streak descending
        sorted_streaks = sorted(user_streaks.items(), key=lambda x: x[1], reverse=True)
        streak_usernames = [u for u, _ in sorted_streaks]
        streak_scores = [s for _, s in sorted_streaks]

    print(streak_scores, streak_usernames)
    return templates.TemplateResponse("leaderboard.html", {
        "request": request,
        "usernames": usernames,
        "saved_amounts": saved_amounts,
        "goal": TARGET_SAVING_AMOUNT,
        "current_user": current_user,
        "user_deposits": user_deposits.get(current_user, []),  # Only show chart for logged-in user
        "heatmap_data": heatmap_data,
        'start_date': START_DATE.strftime('%Y-%m-%d'),
        'end_date': END_DATE.strftime('%Y-%m-%d'),
        "streak_usernames": streak_usernames,
        "streak_scores": streak_scores,
    })

