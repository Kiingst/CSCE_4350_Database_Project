"""Explicit demo initializer. Never runs automatically on application startup."""
import argparse
from pathlib import Path
from sqlalchemy import create_engine
from db import DATABASE_URL, engine, run
from operations import password_hash

def initialize():
    # Select a dedicated demo database in DATABASE_URL before invoking this command.
    url=engine.url
    if not url.database or not url.database.replace('_','').isalnum():
        raise SystemExit('Choose a simple, dedicated database name')
    admin=create_engine(url.set(database=''))
    with admin.connect() as c:
        c.exec_driver_sql(f'CREATE DATABASE IF NOT EXISTS `{url.database}`')
    with engine.connect() as c:
        if c.exec_driver_sql('SHOW TABLES').first():
            raise SystemExit('Database is not empty. Select a fresh dedicated database; initialization stopped.')
    scripts=['APschema.sql','APsample_data.sql','01_mvp_extensions.sql']
    with engine.connect() as c:
        for filename in scripts:
            source=(Path(__file__).parent/'sql'/filename).read_text()
            # Refuse existing tables before applying any DDL.
            # Original database-level DROP/CREATE/USE statements are deliberately skipped.
            for statement in source.split(';'):
                statement=statement.strip()
                if not statement or statement.startswith(('DROP DATABASE','CREATE DATABASE','USE ')):
                    continue
                c.exec_driver_sql(statement)
        for table in ('Customer','Employee'):
            accounts=c.exec_driver_sql(f'SELECT username FROM {table}').scalars().all()
            for username in accounts:
                run(c,f'UPDATE {table} SET password_hash=:p WHERE username=:u',p=password_hash('DemoPass123!'),u=username)
        c.commit()
    print('Demo initialized. Password for all seeded accounts: DemoPass123!')

if __name__=='__main__':
    parser=argparse.ArgumentParser(description='Initialize an EMPTY dedicated MySQL demo database; existing tables cause an error.')
    parser.parse_args()
    initialize()
