from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Request, Response, UploadFile

from app.core.dependencies import get_container, get_current_user_id
from app.core.container import AppContainer
from app.modules.auth.schemas import (
    AuthTokenRead,
    LoginRequest,
    PhotoUploadRead,
    RegisterRequest,
    UserRead,
    VerifyUserRequest,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/upload-photo", response_model=PhotoUploadRead)
async def upload_signup_photo(
    request: Request,
    file: UploadFile = File(...),
) -> PhotoUploadRead:
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Only image uploads are supported.")

    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    if len(data) > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Image is too large. Max 10 MB.")

    suffix = {
        "image/jpeg": ".jpg",
        "image/jpg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
        "image/heic": ".heic",
        "image/heif": ".heif",
    }.get(file.content_type, Path(file.filename or "").suffix.lower() or ".jpg")

    filename = f"{uuid4()}{suffix}"
    base_url = str(request.base_url).rstrip("/")

    from app.core.storage import get_storage
    storage = get_storage()
    url = await storage.upload(data, filename, file.content_type or "image/jpeg", base_url)

    return PhotoUploadRead(url=url)


@router.post("/register", response_model=AuthTokenRead)
def register(
    payload: RegisterRequest,
    container: AppContainer = Depends(get_container),
) -> AuthTokenRead:
    user, token = container.auth_service.register(payload)
    return AuthTokenRead(access_token=token, user=UserRead.model_validate(user))


@router.post("/login", response_model=AuthTokenRead)
def login(
    payload: LoginRequest,
    container: AppContainer = Depends(get_container),
) -> AuthTokenRead:
    user, token = container.auth_service.login(payload)
    return AuthTokenRead(access_token=token, user=UserRead.model_validate(user))


@router.get("/me", response_model=UserRead)
def me(
    current_user_id: str = Depends(get_current_user_id),
    container: AppContainer = Depends(get_container),
) -> UserRead:
    return UserRead.model_validate(container.auth_service.get_user(current_user_id))


@router.post("/verify", response_model=UserRead)
def verify(
    payload: VerifyUserRequest,
    current_user_id: str = Depends(get_current_user_id),
    container: AppContainer = Depends(get_container),
) -> UserRead:
    user = container.auth_service.verify_user(current_user_id, payload)
    container.match_service.activate_pending_likes(current_user_id)
    return UserRead.model_validate(user)


@router.delete("/me", status_code=204)
def delete_account(
    current_user_id: str = Depends(get_current_user_id),
    container: AppContainer = Depends(get_container),
) -> Response:
    """Delete the authenticated user and all associated data."""
    # 1. Delete all matches where user is a participant
    matches = container.match_service.match_repo.list_matches_for_user(current_user_id)
    for match in matches:
        container.match_service.match_repo.delete_match(match.id)

    # 2. Delete all chats where user is a participant
    chats = container.chat_service.chat_repo.list_for_user(current_user_id)
    for chat in chats:
        container.chat_service.chat_repo.delete_chat(chat.id)

    # 3. Delete all deals where user is a participant
    deals = container.deal_service.deal_repo.list_for_user(current_user_id)
    for deal in deals:
        container.deal_service.deal_repo.store.deals.pop(deal.id, None)
    if deals:
        container.deal_service.deal_repo.store.persist()

    # 4. Delete all offer responses by user and offers owned by user
    store = container.offer_service.offer_repo.store
    response_ids = [
        rid for rid, resp in store.offer_responses.items()
        if resp.blogger_id == current_user_id or resp.business_id == current_user_id
    ]
    for rid in response_ids:
        del store.offer_responses[rid]

    offer_ids = [
        oid for oid, offer in store.offers.items()
        if offer.business_id == current_user_id
    ]
    for oid in offer_ids:
        del store.offers[oid]

    if response_ids or offer_ids:
        store.persist()

    # 5. Delete swipes involving the user
    swipe_ids = [
        sid for sid, swipe in container.match_service.match_repo.store.swipes.items()
        if swipe.actor_id == current_user_id or swipe.target_id == current_user_id
    ]
    for sid in swipe_ids:
        del container.match_service.match_repo.store.swipes[sid]
    if swipe_ids:
        container.match_service.match_repo.store.persist()

    # 6. Delete user and profile
    container.auth_service.delete_user(current_user_id)

    return Response(status_code=204)
