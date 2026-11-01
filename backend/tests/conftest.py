import os

os.environ.setdefault("APP_SECRET_KEY", "test-secret-test-secret-test-secret")
os.environ.setdefault("POSTGRES_DB", "strava_automation")
os.environ.setdefault("POSTGRES_USER", "postgres")
os.environ.setdefault("POSTGRES_PASSWORD", "postgres")
os.environ.setdefault("POSTGRES_HOST", "localhost")
os.environ.setdefault("POSTGRES_PORT", "5432")
