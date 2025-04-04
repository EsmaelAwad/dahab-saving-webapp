from sqlmodel import SQLModel, create_engine, Session
from app.models import User, AuthorizedUser

sqlite_file_name = "savings.db"
sqlite_url = f"sqlite:///{sqlite_file_name}"

engine = create_engine(sqlite_url, echo=False)

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)

def get_session():
    return Session(engine)
