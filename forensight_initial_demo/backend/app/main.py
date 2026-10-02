from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from .api.analysis import router as analysis_router
from .api.research import router as research_router
from .api.accounts import router as accounts_router
from .config import settings
from .db import Base, SessionLocal, engine, ensure_sqlite_schema
from .models import TokenPackage, TokenTransaction, User
from .security import hash_password
from uuid import uuid4

Base.metadata.create_all(bind=engine)
ensure_sqlite_schema()
settings.storage_path.mkdir(parents=True, exist_ok=True)


def seed_platform_defaults() -> None:
    """Create local demo defaults once; production values belong in environment settings."""
    db = SessionLocal()
    try:
        if settings.admin_password and db.scalar(select(User).where(User.email == settings.admin_email)) is None:
            db.add(User(
                id=str(uuid4()), email=settings.admin_email, name="ForenSight Administrator",
                password_hash=hash_password(settings.admin_password), role="admin", token_balance=0,
            ))
        # Accounts created before the referral feature need a code too.  Codes
        # are generated here rather than leaving old users unable to invite.
        for existing_user in db.scalars(select(User).where(User.referral_code.is_(None))).all():
            existing_user.referral_code = "FS-" + uuid4().hex[:8].upper()
        if not db.query(TokenPackage).count():
            for name, tokens, amount in (("Starter", 100, 100), ("Researcher", 500, 350), ("Professional", 1000, 700)):
                db.add(TokenPackage(id=str(uuid4()), name=name, tokens=tokens, amount_bdt=amount))
        db.commit()
    finally:
        db.close()


seed_platform_defaults()


def correct_legacy_verification_charges() -> None:
    """Refund the old 50-token charge above the new 10-token price once.

    The correction is tied to each source transaction ID, so it is idempotent:
    two old analyses give a one-time 80-token credit (eight new analyses).
    """
    old_cost = 50
    refund_per_analysis = old_cost - settings.verification_token_cost
    if refund_per_analysis <= 0:
        return

    db = SessionLocal()
    try:
        legacy_charges = db.scalars(select(TokenTransaction).where(
            TokenTransaction.kind == "verification",
            TokenTransaction.delta == -old_cost,
        )).all()
        for charge in legacy_charges:
            note = f"One-time price correction for verification {charge.id}"
            already_corrected = db.scalar(select(TokenTransaction.id).where(
                TokenTransaction.user_id == charge.user_id,
                TokenTransaction.kind == "verification_price_correction",
                TokenTransaction.note == note,
            ))
            if already_corrected is not None:
                continue
            user = db.get(User, charge.user_id)
            if user is None:
                continue
            user.token_balance += refund_per_analysis
            db.add(TokenTransaction(
                id=str(uuid4()), user_id=user.id, delta=refund_per_analysis,
                kind="verification_price_correction", note=note,
            ))
        db.commit()
    finally:
        db.close()


correct_legacy_verification_charges()


def correct_legacy_welcome_allocations() -> None:
    """Bring old registrations up to the current 1,000-token allocation once."""
    old_allocation = 100
    if settings.initial_token_balance <= old_allocation:
        return

    db = SessionLocal()
    try:
        old_welcome_transactions = db.scalars(select(TokenTransaction).where(
            TokenTransaction.kind == "welcome",
            TokenTransaction.delta == old_allocation,
        )).all()
        for welcome in old_welcome_transactions:
            note = f"One-time welcome allocation correction for registration {welcome.id}"
            already_corrected = db.scalar(select(TokenTransaction.id).where(
                TokenTransaction.user_id == welcome.user_id,
                TokenTransaction.kind == "welcome_allocation_correction",
                TokenTransaction.note == note,
            ))
            if already_corrected is not None:
                continue
            user = db.get(User, welcome.user_id)
            if user is None or user.role == "admin":
                continue
            top_up = max(0, settings.initial_token_balance - user.token_balance)
            if top_up == 0:
                continue
            user.token_balance += top_up
            db.add(TokenTransaction(
                id=str(uuid4()), user_id=user.id, delta=top_up,
                kind="welcome_allocation_correction", note=note,
            ))
            db.add(Notification(
                id=str(uuid4()), user_id=user.id, title="Welcome token allocation updated",
                body=f"Your initial token allocation was increased to {settings.initial_token_balance} tokens.",
            ))
        db.commit()
    finally:
        db.close()


correct_legacy_welcome_allocations()

app = FastAPI(
    title=settings.app_name,
    version="0.1.0-demo",
    description="ForenSight trained multimodal forgery-analysis API.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin, "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {
        "name": settings.app_name,
        "mode": "TRAINED MODEL",
        "docs": "/docs",
    }


@app.get(f"{settings.api_prefix}/health")
def health():
    return {
        "status": "ok",
        "demo_mode": settings.demo_mode,
        "model_status": "trained multimodal checkpoint loaded",
    }


app.include_router(analysis_router, prefix=settings.api_prefix)
app.include_router(research_router, prefix=settings.api_prefix)
app.include_router(accounts_router, prefix=settings.api_prefix)
