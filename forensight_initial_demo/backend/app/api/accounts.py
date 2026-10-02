"""Persistent user, case-management, and administrator workflows.

Payment is intentionally excluded. Token changes are retained in an auditable
ledger and may only be adjusted by an administrator with an audit record.
"""
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Header, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..models import (
    AccountDeletionRequest, AdminAudit, Analysis, Case, CaseAnalysis, Feedback,
    Notification, PlatformSetting, TokenTransaction, User, UserSession,
)
from ..security import hash_password, new_session_token, token_hash, verify_password

router = APIRouter(tags=["accounts"])
AVATAR_TYPES = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}


class Credentials(BaseModel):
    email: str
    password: str = Field(min_length=8, max_length=128)
    name: str = Field(min_length=2, max_length=120)
    referral_code: str = Field(default="", max_length=24)


class LoginCredentials(BaseModel):
    email: str
    password: str = Field(min_length=8, max_length=128)


class PasswordChange(BaseModel):
    current_password: str = Field(min_length=8, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


class CaseInput(BaseModel):
    title: str = Field(min_length=2, max_length=180)
    description: str = Field(default="", max_length=5000)


class FeedbackInput(BaseModel):
    subject: str = Field(default="Feedback", min_length=2, max_length=200)
    message: str = Field(min_length=2, max_length=5000)


class AdminUserUpdate(BaseModel):
    active: Optional[bool] = None
    token_delta: int = Field(default=0, ge=-100000, le=100000)
    reason: str = Field(default="", max_length=500)


class AdminReviewUpdate(BaseModel):
    review_status: str = Field(pattern="^(unreviewed|reviewed|reported|resolved)$")
    review_note: str = Field(default="", max_length=3000)


class AnnouncementInput(BaseModel):
    title: str = Field(min_length=2, max_length=160)
    body: str = Field(min_length=2, max_length=5000)
    user_id: Optional[str] = None


def avatar_url(user: User) -> Optional[str]:
    return settings.api_prefix + "/account/avatar/" + user.id if user.avatar_filename else None


def public_user(user: User) -> dict:
    return {
        "id": user.id, "email": user.email, "name": user.name, "role": user.role,
        "token_balance": user.token_balance, "language": user.language, "theme": user.theme,
        "avatar_url": avatar_url(user), "referral_code": user.referral_code,
        "active": user.active, "created_at": user.created_at,
    }


def current_user(authorization: Optional[str] = Header(default=None), db: Session = Depends(get_db)) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Sign in is required")
    session = db.scalar(select(UserSession).where(
        UserSession.token_hash == token_hash(authorization[7:]), UserSession.expires_at > datetime.utcnow()
    ))
    if not session:
        raise HTTPException(401, "Session expired or invalid")
    user = db.get(User, session.user_id)
    if not user or not user.active:
        raise HTTPException(403, "Account is unavailable")
    # Demo allocation policy: ordinary user accounts are kept at the configured
    # allocation for repeat demonstrations. Administrators are intentionally
    # excluded, and balances above the allocation (for example referral credit)
    # are never removed.
    if user.role != "admin" and user.token_balance < settings.initial_token_balance:
        renewal = settings.initial_token_balance - user.token_balance
        user.token_balance = settings.initial_token_balance
        db.add(TokenTransaction(
            id=str(uuid4()), user_id=user.id, delta=renewal,
            kind="automatic_allocation_renewal",
            note=f"Automatic renewal to {settings.initial_token_balance} tokens",
        ))
        db.commit()
    return user


def optional_user(authorization: Optional[str] = Header(default=None), db: Session = Depends(get_db)) -> Optional[User]:
    if not authorization or not authorization.startswith("Bearer "):
        return None
    return current_user(authorization, db)


def admin_user(user: User = Depends(current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(403, "Administrator access is required")
    return user


def audit(db: Session, admin: User, action: str, target_type: str, target_id: str, detail: str = "") -> None:
    db.add(AdminAudit(id=str(uuid4()), admin_id=admin.id, action=action, target_type=target_type,
                      target_id=target_id, detail=detail[:3000]))


def create_session(user: User, db: Session) -> dict:
    raw = new_session_token()
    db.add(UserSession(id=str(uuid4()), user_id=user.id, token_hash=token_hash(raw),
                       expires_at=datetime.utcnow() + timedelta(days=settings.auth_session_days)))
    db.commit()
    return {"access_token": raw, "user": public_user(user)}


def new_referral_code(db: Session) -> str:
    while True:
        candidate = "FS-" + uuid4().hex[:8].upper()
        if not db.scalar(select(User.id).where(User.referral_code == candidate)):
            return candidate


@router.post("/auth/register")
def register(body: Credentials, db: Session = Depends(get_db)):
    email = body.email.strip().lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(409, "An account with this email already exists")
    submitted_code = body.referral_code.strip().upper()
    inviter = db.scalar(select(User).where(User.referral_code == submitted_code, User.active.is_(True))) if submitted_code else None
    if submitted_code and not inviter:
        raise HTTPException(400, "Referral code was not found")
    user = User(id=str(uuid4()), email=email, name=body.name.strip(), password_hash=hash_password(body.password),
                token_balance=settings.initial_token_balance, referral_code=new_referral_code(db), referred_by_id=inviter.id if inviter else None)
    db.add(user)
    db.add(TokenTransaction(id=str(uuid4()), user_id=user.id, delta=settings.initial_token_balance,
                            kind="welcome", note="Initial account tokens"))
    db.add(Notification(id=str(uuid4()), user_id=user.id, title="Welcome to ForenSight",
                        body=f"Your account received {settings.initial_token_balance} welcome tokens."))
    if inviter:
        inviter.token_balance += 25
        user.token_balance += 25
        db.add(TokenTransaction(id=str(uuid4()), user_id=inviter.id, delta=25, kind="referral",
                                note="Reward for a successful referral"))
        db.add(TokenTransaction(id=str(uuid4()), user_id=user.id, delta=25, kind="referral",
                                note="Welcome referral reward"))
        db.add(Notification(id=str(uuid4()), user_id=inviter.id, title="Referral reward received",
                            body="25 tokens were added after an invited user registered."))
    db.commit()
    return create_session(user, db)


@router.post("/auth/login")
def login(body: LoginCredentials, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == body.email.strip().lower()))
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "Invalid email or password")
    if not user.active:
        raise HTTPException(403, "Account is unavailable")
    if user.role == "admin":
        raise HTTPException(403, "Use the separate administrator sign-in page")
    return create_session(user, db)


@router.post("/admin/auth/login")
def admin_login(body: LoginCredentials, db: Session = Depends(get_db)):
    """Dedicated administrator sign-in; ordinary accounts cannot use it."""
    user = db.scalar(select(User).where(User.email == body.email.strip().lower()))
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "Invalid administrator email or password")
    if not user.active or user.role != "admin":
        raise HTTPException(403, "This account is not an active administrator")
    return create_session(user, db)


@router.post("/auth/logout")
def logout(authorization: Optional[str] = Header(default=None), db: Session = Depends(get_db)):
    if authorization and authorization.startswith("Bearer "):
        session = db.scalar(select(UserSession).where(UserSession.token_hash == token_hash(authorization[7:])))
        if session:
            db.delete(session)
            db.commit()
    return {"status": "signed_out"}


@router.get("/account/me")
def me(user: User = Depends(current_user)):
    return public_user(user)


@router.patch("/account/preferences")
def preferences(body: dict, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if body.get("name"):
        user.name = str(body["name"]).strip()[:120]
    if body.get("language") in {"en", "bn"}:
        user.language = body["language"]
    if body.get("theme") in {"dark", "light"}:
        user.theme = body["theme"]
    db.commit()
    return public_user(user)


@router.post("/account/avatar")
async def upload_avatar(avatar: UploadFile = File(...), user: User = Depends(current_user), db: Session = Depends(get_db)):
    if avatar.content_type not in AVATAR_TYPES:
        raise HTTPException(415, "Avatar must be JPG, PNG, or WEBP")
    data = await avatar.read()
    if not data or len(data) > 3 * 1024 * 1024:
        raise HTTPException(400, "Avatar must be between 1 byte and 3 MB")
    avatar_dir = settings.storage_path / "avatars"
    avatar_dir.mkdir(parents=True, exist_ok=True)
    filename = user.id + AVATAR_TYPES[avatar.content_type]
    (avatar_dir / filename).write_bytes(data)
    user.avatar_filename = filename
    db.commit()
    return {"avatar_url": avatar_url(user)}


@router.get("/account/avatar/{user_id}")
def get_avatar(user_id: str, db: Session = Depends(get_db)):
    from fastapi.responses import FileResponse
    user = db.get(User, user_id)
    if not user or not user.avatar_filename:
        raise HTTPException(404, "Avatar not found")
    path = settings.storage_path / "avatars" / Path(user.avatar_filename).name
    if not path.exists():
        raise HTTPException(404, "Avatar not found")
    return FileResponse(path)


@router.post("/account/password")
def change_password(body: PasswordChange, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(400, "Current password is incorrect")
    user.password_hash = hash_password(body.new_password)
    db.add(Notification(id=str(uuid4()), user_id=user.id, title="Password changed",
                        body="Your account password was changed successfully."))
    db.commit()
    return {"status": "changed"}


@router.post("/account/deletion-request")
def deletion_request(body: dict, user: User = Depends(current_user), db: Session = Depends(get_db)):
    existing = db.scalar(select(AccountDeletionRequest).where(
        AccountDeletionRequest.user_id == user.id, AccountDeletionRequest.status == "requested"
    ))
    if existing:
        raise HTTPException(409, "A deletion request is already awaiting review")
    request = AccountDeletionRequest(id=str(uuid4()), user_id=user.id, reason=str(body.get("reason", ""))[:2000])
    db.add(request)
    db.add(Notification(id=str(uuid4()), user_id=user.id, title="Deletion request received",
                        body="Your account-deletion request is awaiting administrator review."))
    db.commit()
    return {"id": request.id, "status": request.status}


@router.get("/tokens/transactions")
def transactions(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return [{"id": x.id, "delta": x.delta, "kind": x.kind, "note": x.note, "created_at": x.created_at}
            for x in db.scalars(select(TokenTransaction).where(TokenTransaction.user_id == user.id)
                                .order_by(TokenTransaction.created_at.desc())).all()]


@router.post("/feedback")
def feedback(body: FeedbackInput, user: User = Depends(current_user), db: Session = Depends(get_db)):
    item = Feedback(id=str(uuid4()), user_id=user.id, subject=body.subject.strip(), message=body.message.strip())
    db.add(item)
    db.add(Notification(id=str(uuid4()), user_id=user.id, title="Feedback received",
                        body="Thank you. Your report was sent to the review queue."))
    db.commit()
    return {"id": item.id, "status": item.status}


@router.get("/notifications")
def notifications(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return [{"id": x.id, "title": x.title, "body": x.body, "read": x.read, "created_at": x.created_at}
            for x in db.scalars(select(Notification).where(
                or_(Notification.user_id == user.id, Notification.user_id.is_(None))
            ).order_by(Notification.created_at.desc()).limit(100)).all()]


@router.post("/notifications/{notification_id}/read")
def read_notification(notification_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    item = db.get(Notification, notification_id)
    if not item or (item.user_id is not None and item.user_id != user.id):
        raise HTTPException(404, "Notification not found")
    item.read = True
    db.commit()
    return {"status": "read"}


def case_payload(case: Case, db: Session) -> dict:
    links = db.scalars(select(CaseAnalysis).where(CaseAnalysis.case_id == case.id)).all()
    analyses = []
    for link in links:
        analysis = db.get(Analysis, link.analysis_id)
        if analysis:
            analyses.append({"id": analysis.id, "filename": analysis.filename, "verdict": analysis.verdict,
                             "score": analysis.preliminary_score, "created_at": analysis.created_at})
    return {"id": case.id, "title": case.title, "description": case.description, "status": case.status,
            "created_at": case.created_at, "analyses": analyses}


@router.get("/cases")
def list_cases(user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(Case).where(Case.user_id == user.id).order_by(Case.created_at.desc())).all()
    return [case_payload(case, db) for case in rows]


@router.post("/cases")
def create_case(body: CaseInput, user: User = Depends(current_user), db: Session = Depends(get_db)):
    case = Case(id=str(uuid4()), user_id=user.id, title=body.title.strip(), description=body.description.strip())
    db.add(case)
    db.commit()
    return case_payload(case, db)


@router.patch("/cases/{case_id}")
def update_case(case_id: str, body: dict, user: User = Depends(current_user), db: Session = Depends(get_db)):
    case = db.get(Case, case_id)
    if not case or case.user_id != user.id:
        raise HTTPException(404, "Case not found")
    if "title" in body and str(body["title"]).strip():
        case.title = str(body["title"]).strip()[:180]
    if "description" in body:
        case.description = str(body["description"])[:5000]
    if body.get("status") in {"open", "closed", "archived"}:
        case.status = body["status"]
    db.commit()
    return case_payload(case, db)


@router.post("/cases/{case_id}/analyses/{analysis_id}")
def add_case_analysis(case_id: str, analysis_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    case, analysis = db.get(Case, case_id), db.get(Analysis, analysis_id)
    if not case or case.user_id != user.id:
        raise HTTPException(404, "Case not found")
    if not analysis or (analysis.user_id and analysis.user_id != user.id):
        raise HTTPException(404, "Analysis not available")
    existing = db.scalar(select(CaseAnalysis).where(CaseAnalysis.case_id == case_id, CaseAnalysis.analysis_id == analysis_id))
    if not existing:
        db.add(CaseAnalysis(id=str(uuid4()), case_id=case_id, analysis_id=analysis_id))
        db.commit()
    return case_payload(case, db)


@router.get("/admin/stats")
def stats(_: User = Depends(admin_user), db: Session = Depends(get_db)):
    per_day = db.execute(select(func.date(Analysis.created_at), func.count(Analysis.id)).group_by(func.date(Analysis.created_at))
                         .order_by(func.date(Analysis.created_at).desc()).limit(14)).all()
    return {
        "users": db.scalar(select(func.count()).select_from(User)),
        "active_users": db.scalar(select(func.count()).select_from(User).where(User.active.is_(True))),
        "analyses": db.scalar(select(func.count()).select_from(Analysis)),
        "reported_analyses": db.scalar(select(func.count()).select_from(Analysis).where(Analysis.review_status == "reported")),
        "feedback_open": db.scalar(select(func.count()).select_from(Feedback).where(Feedback.status == "open")),
        "deletion_requests": db.scalar(select(func.count()).select_from(AccountDeletionRequest).where(AccountDeletionRequest.status == "requested")),
        "tokens_spent": abs(db.scalar(select(func.coalesce(func.sum(TokenTransaction.delta), 0)).where(TokenTransaction.delta < 0)) or 0),
        "activity": [{"date": str(day), "analyses": count} for day, count in per_day],
    }


@router.get("/admin/users")
def admin_users(query: str = "", _: User = Depends(admin_user), db: Session = Depends(get_db)):
    statement = select(User)
    if query.strip():
        needle = "%" + query.strip() + "%"
        statement = statement.where(or_(User.name.ilike(needle), User.email.ilike(needle), User.referral_code.ilike(needle)))
    rows = db.scalars(statement.order_by(User.created_at.desc()).limit(250)).all()
    return [public_user(row) for row in rows]


@router.patch("/admin/users/{user_id}")
def admin_update_user(user_id: str, body: AdminUserUpdate, admin: User = Depends(admin_user), db: Session = Depends(get_db)):
    target = db.get(User, user_id)
    if not target:
        raise HTTPException(404, "User not found")
    if target.id == admin.id and body.active is False:
        raise HTTPException(400, "You cannot deactivate your own administrator account")
    if body.active is not None:
        target.active = body.active
    if body.token_delta:
        target.token_balance = max(0, target.token_balance + body.token_delta)
        db.add(TokenTransaction(id=str(uuid4()), user_id=target.id, delta=body.token_delta, kind="admin_adjustment",
                                note=body.reason or "Administrator token adjustment"))
        db.add(Notification(id=str(uuid4()), user_id=target.id, title="Token balance adjusted",
                            body=("%+d tokens: " % body.token_delta) + (body.reason or "Administrator adjustment")))
    audit(db, admin, "user_update", "user", target.id, body.reason)
    db.commit()
    return public_user(target)


@router.get("/admin/analyses")
def admin_analyses(query: str = "", review_status: str = "", _: User = Depends(admin_user), db: Session = Depends(get_db)):
    statement = select(Analysis)
    if query.strip():
        needle = "%" + query.strip() + "%"
        statement = statement.where(or_(Analysis.filename.ilike(needle), Analysis.sha256.ilike(needle)))
    if review_status.strip():
        statement = statement.where(Analysis.review_status == review_status)
    rows = db.scalars(statement.order_by(Analysis.created_at.desc()).limit(250)).all()
    return [{"id": row.id, "filename": row.filename, "verdict": row.verdict, "score": row.preliminary_score,
             "created_at": row.created_at, "review_status": row.review_status, "review_note": row.review_note,
             "user": public_user(db.get(User, row.user_id)) if row.user_id and db.get(User, row.user_id) else None}
            for row in rows]


@router.patch("/admin/analyses/{analysis_id}/review")
def admin_review_analysis(analysis_id: str, body: AdminReviewUpdate, admin: User = Depends(admin_user), db: Session = Depends(get_db)):
    analysis = db.get(Analysis, analysis_id)
    if not analysis:
        raise HTTPException(404, "Analysis not found")
    analysis.review_status, analysis.review_note = body.review_status, body.review_note.strip()
    audit(db, admin, "analysis_review", "analysis", analysis.id, body.review_note)
    if analysis.user_id:
        db.add(Notification(id=str(uuid4()), user_id=analysis.user_id, title="Analysis review updated",
                            body="A reviewer marked your analysis as " + body.review_status + "."))
    db.commit()
    return {"id": analysis.id, "review_status": analysis.review_status, "review_note": analysis.review_note}


@router.get("/admin/feedback")
def admin_feedback(_: User = Depends(admin_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(Feedback).order_by(Feedback.created_at.desc()).limit(250)).all()
    return [{"id": row.id, "subject": row.subject, "message": row.message, "status": row.status,
             "created_at": row.created_at, "user": public_user(db.get(User, row.user_id)) if row.user_id and db.get(User, row.user_id) else None}
            for row in rows]


@router.patch("/admin/feedback/{feedback_id}")
def admin_feedback_status(feedback_id: str, body: dict, admin: User = Depends(admin_user), db: Session = Depends(get_db)):
    item = db.get(Feedback, feedback_id)
    status = str(body.get("status", ""))
    if not item or status not in {"open", "reviewing", "resolved", "closed"}:
        raise HTTPException(400, "Valid feedback item and status are required")
    item.status = status
    audit(db, admin, "feedback_status", "feedback", item.id, status)
    if item.user_id:
        db.add(Notification(id=str(uuid4()), user_id=item.user_id, title="Feedback status updated",
                            body="Your feedback is now " + status + "."))
    db.commit()
    return {"id": item.id, "status": item.status}


@router.get("/admin/deletion-requests")
def admin_deletion_requests(_: User = Depends(admin_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(AccountDeletionRequest).order_by(AccountDeletionRequest.created_at.desc()).limit(250)).all()
    return [{"id": row.id, "reason": row.reason, "status": row.status, "created_at": row.created_at,
             "user": public_user(db.get(User, row.user_id)) if db.get(User, row.user_id) else None} for row in rows]


@router.patch("/admin/deletion-requests/{request_id}")
def admin_deletion_status(request_id: str, body: dict, admin: User = Depends(admin_user), db: Session = Depends(get_db)):
    request = db.get(AccountDeletionRequest, request_id)
    status = str(body.get("status", ""))
    if not request or status not in {"approved", "rejected", "cancelled"}:
        raise HTTPException(400, "Valid deletion request and status are required")
    request.status = status
    target = db.get(User, request.user_id)
    if status == "approved" and target:
        target.active = False
        for session in db.scalars(select(UserSession).where(UserSession.user_id == target.id)).all():
            db.delete(session)
    if target:
        db.add(Notification(id=str(uuid4()), user_id=target.id, title="Deletion request " + status,
                            body="Your deletion request was " + status + "."))
    audit(db, admin, "deletion_request", "deletion_request", request.id, status)
    db.commit()
    return {"id": request.id, "status": request.status}


@router.post("/admin/notifications")
def admin_announcement(body: AnnouncementInput, admin: User = Depends(admin_user), db: Session = Depends(get_db)):
    if body.user_id and not db.get(User, body.user_id):
        raise HTTPException(404, "Target user not found")
    notice = Notification(id=str(uuid4()), user_id=body.user_id, title=body.title.strip(), body=body.body.strip())
    db.add(notice)
    audit(db, admin, "notification_create", "notification", notice.id, "targeted" if body.user_id else "announcement")
    db.commit()
    return {"id": notice.id, "audience": "user" if body.user_id else "all_users"}


@router.get("/admin/settings")
def admin_settings(_: User = Depends(admin_user), db: Session = Depends(get_db)):
    return {item.key: item.value for item in db.scalars(select(PlatformSetting)).all()}


@router.put("/admin/settings")
def update_admin_settings(body: dict, admin: User = Depends(admin_user), db: Session = Depends(get_db)):
    allowed = {"announcement_banner", "support_email", "retention_policy"}
    for key, value in body.items():
        if key not in allowed or not isinstance(value, str) or len(value) > 5000:
            raise HTTPException(400, "Unsupported system setting")
        setting = db.get(PlatformSetting, key)
        if not setting:
            db.add(PlatformSetting(key=key, value=value))
        else:
            setting.value = value
    audit(db, admin, "settings_update", "platform", "settings", ", ".join(body.keys()))
    db.commit()
    return {"status": "saved"}
