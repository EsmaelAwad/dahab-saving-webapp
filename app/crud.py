from sqlmodel import select
from app.models import User, AuthorizedUser, Deposit
from app.database import get_session
from typing import Optional
from datetime import date 
def get_user_by_username(username: str):
    with get_session() as session:
        statement = select(User).where(User.username == username)
        result = session.exec(statement).first()
        return result

def create_user(username: str, password: str):
    with get_session() as session:
        user = User(username=username, password=password)
        session.add(user)
        session.commit()
        session.refresh(user)
        return user

def is_authorized(username: str):
    with get_session() as session:
        statement = select(AuthorizedUser).where(AuthorizedUser.username == username)
        return session.exec(statement).first() is not None

def update_user_password(username: str, new_password: str):
    with get_session() as session:
        statement = select(User).where(User.username == username)
        result = session.exec(statement)
        user = result.first()
        if user:
            user.password = new_password
            session.add(user)
            session.commit()

def get_all_users():
    with get_session() as session:
        statement = select(User)
        return session.exec(statement).all()

def authorize_user(username: str):
    with get_session() as session:
        # Check if already authorized
        statement = select(AuthorizedUser).where(AuthorizedUser.username == username)
        if session.exec(statement).first():
            return
        auth_user = AuthorizedUser(username=username)
        session.add(auth_user)
        session.commit()

def deauthorize_user(username: str):
    with get_session() as session:
        statement = select(AuthorizedUser).where(AuthorizedUser.username == username)
        user = session.exec(statement).first()
        if user:
            session.delete(user)
            session.commit()


def save_deposit(username: str, amount: float, week_date: Optional[date] = None):
    with get_session() as session:
        deposit = Deposit(username=username, amount=amount, week_date=week_date)
        session.add(deposit)
        session.commit()

def get_paid_week_dates(username: str):
    with get_session() as session:
        statement = select(Deposit).where(Deposit.username == username)
        deposits = session.exec(statement).all()
        return [d.week_date for d in deposits if d.week_date]
