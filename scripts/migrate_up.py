import os
import time
from alembic.config import Config
from alembic import command
from sqlalchemy import create_engine
from nad_ch.config import DATABASE_URL


def wait_for_db(db_url, timeout=30):
    """Wait for the database to be ready."""
    engine = create_engine(db_url)
    start_time = time.time()
    while True:
        try:
            with engine.connect():
                return True
        except Exception:
            if time.time() - start_time > timeout:
                return False
            time.sleep(1)


def main():
    if os.getenv("APP_ENV") != "dev_local":
        raise Exception("This script can only be run in a local dev environment.")

    # Wait for the database to respond before attempting migrations
    if not wait_for_db(DATABASE_URL):
        raise Exception("Database timed out or is not reachable.")

    current_script_path = os.path.abspath(__file__)
    project_root = os.path.dirname(os.path.dirname(current_script_path))
    alembic_cfg_path = os.path.join(project_root, "alembic.ini")

    # Alembic's command.upgrade(cfg, "head") is idempotent:
    # it only applies migrations that haven't been run yet.
    alembic_cfg = Config(alembic_cfg_path)
    command.upgrade(alembic_cfg, "head")


if __name__ == "__main__":
    main()
