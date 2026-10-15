"""Atomic shared quota reservation for every cloud assistant route."""
from fastapi import Request
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models import User
from app.rate_limit import enforce, record


def reserve_cloud_call(db: Session, user: User, request: Request) -> None:
    # Same user lock as plan replacement; held through enforce+record's commit.
    db.execute(select(User.id).where(User.id==user.id).with_for_update()).scalar_one()
    enforce(db,request,'cloud_assist',user.id,account_limit=20,source_limit=1000,minutes=60)
    record(db,request,'cloud_assist',user.id)
