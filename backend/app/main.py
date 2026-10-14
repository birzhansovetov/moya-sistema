from fastapi import FastAPI
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import Settings
from app.backup_upload_limit import BackupUploadLimit
from app.db import sqlalchemy_url
from app.mail import GmailMailer, Mailer
from app.local_ai import PreviewAdvisor
from app.book_storage import S3BookStore
from app.routes import auth, backup, calendar, finance, library, nutrition, onboarding, personal, personal_books, profile, reading, sport, study, study_assist, tasks


def create_app(settings: Settings | None = None, mailer: Mailer | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    app = FastAPI(title="Моя система API")
    app.add_middleware(BackupUploadLimit)
    app.state.settings = settings
    app.state.mailer = mailer if mailer is not None else GmailMailer.from_env()
    app.state.preview_advisor = PreviewAdvisor()
    app.state.book_store = S3BookStore.from_env()
    app.state.engine = create_engine(sqlalchemy_url(settings.database_url), pool_pre_ping=True)
    app.state.sessionmaker = sessionmaker(app.state.engine, expire_on_commit=False)
    app.include_router(auth.router)
    app.include_router(profile.router)
    app.include_router(backup.router)
    app.include_router(tasks.router)
    app.include_router(calendar.router)
    app.include_router(sport.router)
    app.include_router(nutrition.router)
    app.include_router(finance.router)
    app.include_router(personal.router)
    app.include_router(personal_books.router)
    app.include_router(reading.router)
    app.include_router(library.router)
    app.include_router(study.router)
    app.include_router(study_assist.router)
    app.include_router(onboarding.router)

    @app.get("/healthz")
    def healthz():
        return {"status": "ok"}

    return app


def get_app() -> FastAPI:
    return create_app()
