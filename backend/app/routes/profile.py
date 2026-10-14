from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth import AuthContext, get_current_user, require_csrf
from app.db import get_db
from app.models import User


router = APIRouter(prefix="/api/profile", tags=["profile"])


class ProfileUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=80)
    timezone: str = Field(max_length=64)


Section = Literal["personal", "sport", "nutrition", "education", "work", "finance", "other"]


class SectionPreferences(BaseModel):
    hidden_sections: list[Section] = Field(max_length=7)


Sphere = Literal["health", "education", "profession", "languages", "finance", "personal"]


class SpherePreferences(BaseModel):
    hidden_spheres: list[Sphere] = Field(max_length=6)


def profile_info(user: User) -> dict[str, str | None]:
    return {"id": user.id, "email": user.email, "name": user.name, "timezone": user.timezone,
            "onboarding_complete": user.onboarding_completed_at is not None}


@router.get("")
def get_profile(user: User = Depends(get_current_user)):
    return profile_info(user)


@router.patch("")
def update_profile(payload: ProfileUpdate, context: AuthContext = Depends(require_csrf), db: Session = Depends(get_db)):
    try:
        ZoneInfo(payload.timezone)
    except ZoneInfoNotFoundError:
        raise HTTPException(status_code=422, detail="Неизвестный часовой пояс") from None
    context.user.name = payload.name.strip() or None if payload.name is not None else None
    context.user.timezone = payload.timezone
    db.commit()
    return profile_info(context.user)


@router.get("/sections")
def get_section_preferences(user: User = Depends(get_current_user)):
    return {"hidden_sections": user.hidden_sections or []}


@router.patch("/sections")
def update_section_preferences(payload: SectionPreferences, context: AuthContext = Depends(require_csrf), db: Session = Depends(get_db)):
    if len(set(payload.hidden_sections)) != len(payload.hidden_sections):
        raise HTTPException(status_code=422, detail="Разделы не должны повторяться")
    context.user.hidden_sections = list(payload.hidden_sections)
    db.commit()
    return {"hidden_sections": context.user.hidden_sections}


@router.get("/spheres")
def get_sphere_preferences(user: User = Depends(get_current_user)):
    return {"hidden_spheres": user.hidden_spheres or []}


@router.patch("/spheres")
def update_sphere_preferences(payload: SpherePreferences, context: AuthContext = Depends(require_csrf), db: Session = Depends(get_db)):
    if len(set(payload.hidden_spheres)) != len(payload.hidden_spheres):
        raise HTTPException(status_code=422, detail="Сферы не должны повторяться")
    context.user.hidden_spheres = list(payload.hidden_spheres)
    db.commit()
    return {"hidden_spheres": context.user.hidden_spheres}
