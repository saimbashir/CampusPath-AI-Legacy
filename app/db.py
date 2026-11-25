from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from app.config import DATABASE_URL
class Base(DeclarativeBase):
    pass
if DATABASE_URL.startswith('sqlite'):
    engine = create_engine(DATABASE_URL, connect_args={'check_same_thread': False})
else:
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
if DATABASE_URL.startswith('sqlite'):
    @event.listens_for(engine, 'connect')
    def sqlite_settings(connection, record):
        connection.execute('PRAGMA foreign_keys=ON')
        connection.execute('PRAGMA journal_mode=WAL')
        connection.execute('PRAGMA busy_timeout=5000')
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
def get_db():
    with SessionLocal() as db:
        yield db
