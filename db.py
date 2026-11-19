"""SQLAlchemy Core connection helpers; writes use one explicit transaction."""
import os
from sqlalchemy import create_engine, text

DATABASE_URL = os.getenv('DATABASE_URL', 'mysql+mysqlconnector://autoparts:local-demo-only@127.0.0.1:3307/autoparts')
engine = create_engine(DATABASE_URL, pool_pre_ping=True, isolation_level='READ COMMITTED')

def run(conn, sql, **params):
    return conn.execute(text(sql), params)

def rows(conn, sql, **params):
    return list(run(conn, sql, **params).mappings())

def one(conn, sql, **params):
    return run(conn, sql, **params).mappings().first()
