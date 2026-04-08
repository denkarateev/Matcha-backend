from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import HTMLResponse

from app.core.config import get_settings
from app.core.container import AppContainer, InMemoryStore
from app.core.dependencies import get_container
from app.core.time import utc_now
from app.modules.admin.schemas import (
    AdminDealBrief,
    AdminDealRead,
    AdminDealStatusUpdate,
    AdminUserDetail,
    AdminUserRead,
    BanUserRequest,
    DashboardStats,
    DealListResponse,
    ReportItem,
    ReportListResponse,
    SetAudienceRequest,
    SetVerificationRequest,
    UserListResponse,
    VerificationActionRequest,
    VerificationListResponse,
    VerificationSubmission,
)
from app.modules.auth.domain.models import VerificationLevel

router = APIRouter(tags=["admin"])


# ---------------------------------------------------------------------------
# Admin auth dependency
# ---------------------------------------------------------------------------

async def verify_admin_token(authorization: str = Header(...)) -> str:
    """Validate the admin bearer token from the Authorization header."""
    settings = get_settings()
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or token != settings.admin_token:
        raise HTTPException(status_code=403, detail="Invalid admin token.")
    return token


# ---------------------------------------------------------------------------
# Static admin panel
# ---------------------------------------------------------------------------

@router.get("/admin", response_class=HTMLResponse)
async def admin_panel():
    html = (Path(__file__).parent / "static" / "index.html").read_text()
    return HTMLResponse(content=html)


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@router.get("/admin/dashboard", response_model=DashboardStats)
async def dashboard(
    _token: str = Depends(verify_admin_token),
    container: AppContainer = Depends(get_container),
) -> DashboardStats:
    store = _get_store(container)
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    active_today = 0
    for user in store.users.values():
        if hasattr(user, "updated_at") and user.updated_at >= today_start:
            active_today += 1

    return DashboardStats(
        total_users=len(store.users),
        total_matches=len(store.matches),
        total_deals=len(store.deals),
        total_offers=len(store.offers),
        active_today=active_today,
    )


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------

@router.get("/admin/users", response_model=UserListResponse)
async def list_users(
    _token: str = Depends(verify_admin_token),
    container: AppContainer = Depends(get_container),
    role: str | None = Query(None),
    verified: bool | None = Query(None),
    search: str | None = Query(None),
) -> UserListResponse:
    store = _get_store(container)
    users = list(store.users.values())

    if role:
        users = [u for u in users if u.role.value == role]
    if verified is not None:
        users = [u for u in users if u.is_verified == verified]
    if search:
        q = search.lower()
        users = [
            u for u in users
            if q in u.full_name.lower() or q in u.email.lower()
        ]

    admin_users = []
    for user in users:
        profile = store.profiles.get(user.id)
        admin_users.append(_user_to_admin_read(user, profile))

    return UserListResponse(users=admin_users, total=len(admin_users))


@router.get("/admin/users/{user_id}", response_model=AdminUserDetail)
async def get_user_detail(
    user_id: str,
    _token: str = Depends(verify_admin_token),
    container: AppContainer = Depends(get_container),
) -> AdminUserDetail:
    store = _get_store(container)
    user = store.users.get(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    profile = store.profiles.get(user_id)
    base = _user_to_admin_read(user, profile)

    # Deals
    deal_briefs = []
    for deal in store.deals.values():
        if user_id in deal.participant_ids:
            partner_id = deal.participant_ids[0] if deal.participant_ids[1] == user_id else deal.participant_ids[1]
            partner = store.users.get(partner_id)
            deal_briefs.append(AdminDealBrief(
                id=deal.id,
                status=deal.status.value if hasattr(deal.status, "value") else str(deal.status),
                type=deal.type.value if hasattr(deal.type, "value") else str(deal.type),
                partner_name=partner.full_name if partner else None,
                created_at=deal.created_at,
            ))

    # Matches count (in-memory Match uses user_ids tuple)
    matches_count = sum(
        1 for m in store.matches.values()
        if user_id in getattr(m, "user_ids", ())
    )

    return AdminUserDetail(
        **base.model_dump(),
        bio=getattr(profile, "bio", None) if profile else None,
        description=getattr(profile, "description", None) if profile else None,
        niches=getattr(profile, "niches", []) if profile else [],
        languages=getattr(profile, "languages", []) if profile else [],
        photo_urls=getattr(profile, "photo_urls", []) if profile else [],
        badges=getattr(profile, "badges", []) if profile else [],
        verified_visits=getattr(profile, "verified_visits", 0) if profile else 0,
        district=getattr(profile, "district", None) if profile else None,
        country=getattr(profile, "country", None) if profile else None,
        deals=deal_briefs,
        matches_count=matches_count,
    )


@router.post("/admin/users/{user_id}/verify", response_model=AdminUserRead)
async def set_verification(
    user_id: str,
    payload: SetVerificationRequest,
    _token: str = Depends(verify_admin_token),
    container: AppContainer = Depends(get_container),
) -> AdminUserRead:
    store = _get_store(container)
    user = store.users.get(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    updated = replace(
        user,
        verification_level=VerificationLevel(payload.verification_level),
        updated_at=utc_now(),
    )
    store.users[user_id] = updated
    _sync_to_container(container, store)
    profile = store.profiles.get(user_id)
    return _user_to_admin_read(updated, profile)


@router.post("/admin/users/{user_id}/set-audience", response_model=AdminUserRead)
async def set_audience(
    user_id: str,
    payload: SetAudienceRequest,
    _token: str = Depends(verify_admin_token),
    container: AppContainer = Depends(get_container),
) -> AdminUserRead:
    store = _get_store(container)
    user = store.users.get(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    profile = store.profiles.get(user_id)
    if profile:
        updated_profile = replace(
            profile,
            audience_size=payload.audience_size,
            updated_at=utc_now(),
        )
        store.profiles[user_id] = updated_profile
        _sync_to_container(container, store)
        profile = updated_profile

    return _user_to_admin_read(user, profile)


@router.post("/admin/users/{user_id}/ban", response_model=AdminUserRead)
async def ban_user(
    user_id: str,
    payload: BanUserRequest | None = None,
    _token: str = Depends(verify_admin_token),
    container: AppContainer = Depends(get_container),
) -> AdminUserRead:
    store = _get_store(container)
    user = store.users.get(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    updated = replace(user, is_active=False, updated_at=utc_now())
    store.users[user_id] = updated
    _sync_to_container(container, store)
    profile = store.profiles.get(user_id)
    return _user_to_admin_read(updated, profile)


@router.post("/admin/fix-photo-urls", response_model=dict)
async def fix_placeholder_photo_urls(
    _token: str = Depends(verify_admin_token),
    container: AppContainer = Depends(get_container),
) -> dict:
    """Replace all placeholder.matcha.app URLs with actual media URLs."""
    import os
    store = _get_store(container)
    media_dir = "/opt/matcha-backend/data/media/profile-photos"
    base_url = "http://188.253.19.166:8842/media/profile-photos"
    fixed = 0

    # Map existing media files by creation time
    media_files = []
    if os.path.isdir(media_dir):
        for f in os.listdir(media_dir):
            path = os.path.join(media_dir, f)
            media_files.append((os.path.getmtime(path), f))
        media_files.sort()

    file_idx = 0
    for profile in store.profiles.values():
        urls = getattr(profile, "photo_urls", [])
        primary = getattr(profile, "primary_photo_url", "")
        if "placeholder.matcha.app" in primary and file_idx < len(media_files):
            new_url = f"{base_url}/{media_files[file_idx][1]}"
            profile.photo_urls = [new_url]
            profile.primary_photo_url = new_url
            profile.updated_at = utc_now()
            file_idx += 1
            fixed += 1

    _sync_to_container(container, store)
    return {"fixed": fixed, "total_profiles": len(store.profiles)}


# ---------------------------------------------------------------------------
# Verifications
# ---------------------------------------------------------------------------

# In-memory verification queue (persists within app lifetime).
# In production this would be backed by a DB table.
_verification_queue: dict[str, dict] = {}


@router.get("/admin/verifications/pending", response_model=VerificationListResponse)
async def pending_verifications(
    _token: str = Depends(verify_admin_token),
    container: AppContainer = Depends(get_container),
) -> VerificationListResponse:
    store = _get_store(container)

    # Build from users who are unverified (SHADOW) but have instagram_handle set
    submissions: list[VerificationSubmission] = []

    # Check in-memory queue first
    for vid, v in _verification_queue.items():
        if v["status"] == "pending":
            submissions.append(VerificationSubmission(**v))

    # Also scan for users who self-verified but are still SHADOW
    # (they submitted via /auth/verify which sets level=1 directly;
    #  for the admin flow, check SHADOW users with instagram set on profile)
    seen_user_ids = {s.user_id for s in submissions}
    for user in store.users.values():
        if user.id in seen_user_ids:
            continue
        if user.verification_level.value == 0:
            profile = store.profiles.get(user.id)
            if profile and getattr(profile, "instagram_handle", None):
                sub = VerificationSubmission(
                    id=f"auto-{user.id}",
                    user_id=user.id,
                    user_name=user.full_name,
                    user_email=user.email,
                    instagram_handle=getattr(profile, "instagram_handle", None),
                    tiktok_handle=getattr(profile, "tiktok_handle", None),
                    audience_size=getattr(profile, "audience_size", None),
                    screenshot_url=None,
                    submitted_at=user.created_at,
                    status="pending",
                )
                submissions.append(sub)

    return VerificationListResponse(submissions=submissions, total=len(submissions))


@router.post("/admin/verifications/{verification_id}/approve", response_model=dict)
async def approve_verification(
    verification_id: str,
    _token: str = Depends(verify_admin_token),
    container: AppContainer = Depends(get_container),
) -> dict:
    store = _get_store(container)
    user_id = _resolve_verification_user(verification_id)

    user = store.users.get(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    updated = replace(
        user,
        verification_level=VerificationLevel.VERIFIED,
        updated_at=utc_now(),
    )
    store.users[user_id] = updated
    _sync_to_container(container, store)

    if verification_id in _verification_queue:
        _verification_queue[verification_id]["status"] = "approved"

    return {"status": "approved", "user_id": user_id}


@router.post("/admin/verifications/{verification_id}/reject", response_model=dict)
async def reject_verification(
    verification_id: str,
    payload: VerificationActionRequest | None = None,
    _token: str = Depends(verify_admin_token),
    container: AppContainer = Depends(get_container),
) -> dict:
    user_id = _resolve_verification_user(verification_id)

    if verification_id in _verification_queue:
        _verification_queue[verification_id]["status"] = "rejected"

    return {
        "status": "rejected",
        "user_id": user_id,
        "reason": payload.reason if payload else None,
    }


# ---------------------------------------------------------------------------
# Deals CRM
# ---------------------------------------------------------------------------

@router.get("/admin/deals", response_model=DealListResponse)
async def list_deals(
    _token: str = Depends(verify_admin_token),
    container: AppContainer = Depends(get_container),
    status: str | None = Query(None),
    type: str | None = Query(None),
    user_id: str | None = Query(None),
    sort: str = Query("newest"),
) -> DealListResponse:
    """List all deals with optional filters. CRM endpoint."""
    store = _get_store(container)
    deals = list(store.deals.values())

    # Filters
    if status:
        deals = [d for d in deals if (d.status.value if hasattr(d.status, "value") else str(d.status)) == status]
    if type:
        deals = [d for d in deals if (d.type.value if hasattr(d.type, "value") else str(d.type)) == type]
    if user_id:
        deals = [d for d in deals if user_id in d.participant_ids]

    # Sort
    if sort == "newest":
        deals.sort(key=lambda d: d.created_at, reverse=True)
    elif sort == "oldest":
        deals.sort(key=lambda d: d.created_at)
    elif sort == "scheduled":
        deals.sort(key=lambda d: d.scheduled_for or d.created_at, reverse=True)

    # Status counts (unfiltered)
    all_deals = list(store.deals.values())
    status_counts: dict[str, int] = {}
    for d in all_deals:
        s = d.status.value if hasattr(d.status, "value") else str(d.status)
        status_counts[s] = status_counts.get(s, 0) + 1

    admin_deals = [_deal_to_admin_read(d, store) for d in deals]
    return DealListResponse(deals=admin_deals, total=len(admin_deals), status_counts=status_counts)


@router.get("/admin/deals/{deal_id}", response_model=AdminDealRead)
async def get_deal_detail(
    deal_id: str,
    _token: str = Depends(verify_admin_token),
    container: AppContainer = Depends(get_container),
) -> AdminDealRead:
    store = _get_store(container)
    deal = store.deals.get(deal_id)
    if not deal:
        raise HTTPException(status_code=404, detail="Deal not found.")
    return _deal_to_admin_read(deal, store)


@router.post("/admin/deals/{deal_id}/status", response_model=AdminDealRead)
async def update_deal_status(
    deal_id: str,
    payload: AdminDealStatusUpdate,
    _token: str = Depends(verify_admin_token),
    container: AppContainer = Depends(get_container),
) -> AdminDealRead:
    """Admin force-update deal status (for moderation)."""
    store = _get_store(container)
    deal = store.deals.get(deal_id)
    if not deal:
        raise HTTPException(status_code=404, detail="Deal not found.")

    from app.modules.deals.domain.models import DealStatus
    try:
        new_status = DealStatus(payload.status)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid status: {payload.status}")

    updated = replace(deal, status=new_status, updated_at=utc_now())
    if payload.reason and new_status.value == "cancelled":
        updated = replace(updated, cancellation_reason=payload.reason)
    store.deals[deal_id] = updated
    _sync_to_container(container, store)
    return _deal_to_admin_read(updated, store)


# ---------------------------------------------------------------------------
# Reports (stub: no report model exists yet, return from in-memory store)
# ---------------------------------------------------------------------------

_reports_store: list[dict] = []


@router.get("/admin/reports", response_model=ReportListResponse)
async def list_reports(
    _token: str = Depends(verify_admin_token),
    container: AppContainer = Depends(get_container),
) -> ReportListResponse:
    store = _get_store(container)
    items = []
    for r in _reports_store:
        reporter = store.users.get(r.get("reporter_id", ""))
        reported = store.users.get(r.get("reported_user_id", ""))
        items.append(ReportItem(
            id=r["id"],
            reporter_id=r["reporter_id"],
            reporter_name=reporter.full_name if reporter else None,
            reported_user_id=r["reported_user_id"],
            reported_user_name=reported.full_name if reported else None,
            reason=r.get("reason"),
            created_at=r["created_at"],
        ))
    return ReportListResponse(reports=items, total=len(items))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_store(container: AppContainer):
    """Return the live container store — single source of truth for all endpoints."""
    return container.auth_service.auth_repo.store


def _sync_to_container(container: AppContainer, store):
    """Sync admin changes back to the live container store so auth/me etc. see them immediately."""
    live = container.auth_service.auth_repo.store
    if live is not store:
        live.users = store.users
        live.profiles = store.profiles
        live.deals = store.deals
        live.matches = store.matches
        live.offers = store.offers
        live.chats = store.chats
        live.messages = store.messages
    store.persist()


def _user_to_admin_read(user, profile) -> AdminUserRead:
    return AdminUserRead(
        id=user.id,
        email=user.email,
        role=user.role,
        full_name=user.full_name,
        is_active=user.is_active,
        verification_level=user.verification_level,
        plan_tier=user.plan_tier,
        offer_credits=user.offer_credits,
        created_at=user.created_at,
        updated_at=user.updated_at,
        display_name=getattr(profile, "display_name", None) if profile else None,
        instagram_handle=getattr(profile, "instagram_handle", None) if profile else None,
        tiktok_handle=getattr(profile, "tiktok_handle", None) if profile else None,
        audience_size=getattr(profile, "audience_size", None) if profile else None,
        category=getattr(profile, "category", None) if profile else None,
        rating=getattr(profile, "rating", None) if profile else None,
        review_count=getattr(profile, "review_count", 0) if profile else 0,
        primary_photo_url=getattr(profile, "primary_photo_url", None) if profile else None,
    )


def _deal_to_admin_read(deal, store) -> AdminDealRead:
    """Convert a Deal domain object to AdminDealRead with resolved names."""
    initiator = store.users.get(deal.initiator_id)
    partner_id = deal.participant_ids[0] if deal.participant_ids[1] == deal.initiator_id else deal.participant_ids[1]
    partner = store.users.get(partner_id)
    return AdminDealRead(
        id=deal.id,
        chat_id=deal.chat_id,
        participant_ids=deal.participant_ids,
        initiator_id=deal.initiator_id,
        initiator_name=initiator.full_name if initiator else None,
        partner_name=partner.full_name if partner else None,
        type=deal.type.value if hasattr(deal.type, "value") else str(deal.type),
        offered_text=deal.offered_text,
        requested_text=deal.requested_text,
        place_name=deal.place_name,
        guests=deal.guests,
        scheduled_for=deal.scheduled_for,
        content_deadline=deal.content_deadline,
        status=deal.status.value if hasattr(deal.status, "value") else str(deal.status),
        checked_in_user_ids=list(deal.checked_in_user_ids),
        reviews_count=len(deal.reviews),
        content_proofs_count=len(deal.content_proofs),
        cancellation_reason=deal.cancellation_reason,
        repeated_from_deal_id=deal.repeated_from_deal_id,
        created_at=deal.created_at,
        updated_at=deal.updated_at,
    )


def _resolve_verification_user(verification_id: str) -> str:
    """Extract user_id from a verification ID."""
    if verification_id.startswith("auto-"):
        return verification_id[5:]
    entry = _verification_queue.get(verification_id)
    if entry:
        return entry["user_id"]
    raise HTTPException(status_code=404, detail="Verification not found.")
