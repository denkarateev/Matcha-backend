from __future__ import annotations

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

import app.core.container as container_module
from app.core.config import Settings
from app.main import create_app


@pytest.fixture
def client(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[TestClient, None, None]:
    monkeypatch.setattr(
        container_module,
        "STORE_PERSIST_PATH",
        str(tmp_path / "matcha-store.pickle"),
    )
    with TestClient(create_app()) as test_client:
        yield test_client


def _register_user(
    client: TestClient,
    *,
    email: str,
    role: str,
    full_name: str,
    primary_photo_url: str,
    category: str | None = None,
) -> tuple[str, str]:
    payload = {
        "email": email,
        "password": "supersecret",
        "role": role,
        "full_name": full_name,
        "primary_photo_url": primary_photo_url,
    }
    if category:
        payload["category"] = category

    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 200
    body = response.json()
    return body["access_token"], body["user"]["id"]


def _verify_user(
    client: TestClient,
    *,
    token: str,
    instagram_handle: str,
    audience_size: int,
) -> None:
    response = client.post(
        "/api/v1/auth/verify",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "instagram_handle": instagram_handle,
            "tiktok_handle": instagram_handle,
            "audience_size": audience_size,
        },
    )
    assert response.status_code == 200


def _register_and_verify_user(
    client: TestClient,
    *,
    email: str,
    role: str,
    full_name: str,
    primary_photo_url: str,
    instagram_handle: str,
    audience_size: int,
    category: str | None = None,
) -> tuple[str, str]:
    token, user_id = _register_user(
        client,
        email=email,
        role=role,
        full_name=full_name,
        primary_photo_url=primary_photo_url,
        category=category,
    )
    _verify_user(
        client,
        token=token,
        instagram_handle=instagram_handle,
        audience_size=audience_size,
    )
    return token, user_id


def test_health_endpoint(client: TestClient) -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["services"]["storage"] == "in-memory"


def test_register_verify_offer_flow(client: TestClient) -> None:
    business = client.post(
        "/api/v1/auth/register",
        json={
            "email": "biz@example.com",
            "password": "supersecret",
            "role": "business",
            "full_name": "Surf School",
            "primary_photo_url": "https://example.com/biz.jpg",
            "category": "Activity / Sport",
        },
    )
    assert business.status_code == 200
    business_token = business.json()["access_token"]

    verify_business = client.post(
        "/api/v1/auth/verify",
        headers={"Authorization": f"Bearer {business_token}"},
        json={
            "instagram_handle": "@surfschool",
            "tiktok_handle": "@surfschool",
            "audience_size": 12_000,
        },
    )
    assert verify_business.status_code == 200

    create_offer = client.post(
        "/api/v1/offers",
        headers={"Authorization": f"Bearer {business_token}"},
        json={
            "title": "Sunset surf collab",
            "type": "barter",
            "blogger_receives": "2 surf lessons and sunset dinner",
            "business_receives": "1 reel + 3 stories",
            "slots_total": 2,
            "photo_url": "https://example.com/offer.jpg",
        },
    )
    assert create_offer.status_code == 200
    offer_id = create_offer.json()["id"]

    blogger = client.post(
        "/api/v1/auth/register",
        json={
            "email": "blogger@example.com",
            "password": "supersecret",
            "role": "blogger",
            "full_name": "Anna",
            "primary_photo_url": "https://example.com/anna.jpg",
        },
    )
    assert blogger.status_code == 200
    blogger_token = blogger.json()["access_token"]

    verify_blogger = client.post(
        "/api/v1/auth/verify",
        headers={"Authorization": f"Bearer {blogger_token}"},
        json={
            "instagram_handle": "@anna",
            "tiktok_handle": "@anna",
            "audience_size": 25_000,
        },
    )
    assert verify_blogger.status_code == 200

    respond = client.post(
        f"/api/v1/offers/{offer_id}/responses",
        headers={"Authorization": f"Bearer {blogger_token}"},
        json={"message": "Would love to join this collab."},
    )
    assert respond.status_code == 200
    respond_body = respond.json()
    # Response is now wrapped: { response: {...}, remaining_responses: int }
    assert "response" in respond_body
    assert "remaining_responses" in respond_body
    response_id = respond_body["response"]["id"]

    accept = client.post(
        f"/api/v1/offers/responses/{response_id}/accept",
        headers={"Authorization": f"Bearer {business_token}"},
    )
    assert accept.status_code == 200
    assert accept.json()["status"] == "accepted"

    chats = client.get(
        "/api/v1/chats",
        headers={"Authorization": f"Bearer {business_token}"},
    )
    assert chats.status_code == 200
    assert len(chats.json()) == 1


def test_deal_creation_adds_chat_card_and_declined_cancel_alias_works(
    client: TestClient,
) -> None:
    business_token, business_id = _register_and_verify_user(
        client,
        email="biz-deal@example.com",
        role="business",
        full_name="Deal Resort",
        primary_photo_url="https://example.com/deal-biz.jpg",
        instagram_handle="@dealresort",
        audience_size=18_000,
        category="Hospitality",
    )
    blogger_token, blogger_id = _register_and_verify_user(
        client,
        email="blogger-deal@example.com",
        role="blogger",
        full_name="Nika",
        primary_photo_url="https://example.com/nika.jpg",
        instagram_handle="@nika",
        audience_size=33_000,
    )

    create_offer = client.post(
        "/api/v1/offers",
        headers={"Authorization": f"Bearer {business_token}"},
        json={
            "title": "Beach brunch collab",
            "type": "barter",
            "blogger_receives": "Brunch for two",
            "business_receives": "1 reel + 2 stories",
            "slots_total": 1,
            "photo_url": "https://example.com/brunch.jpg",
        },
    )
    assert create_offer.status_code == 200
    offer_id = create_offer.json()["id"]

    respond = client.post(
        f"/api/v1/offers/{offer_id}/responses",
        headers={"Authorization": f"Bearer {blogger_token}"},
        json={"message": "This looks like a fit for my audience."},
    )
    assert respond.status_code == 200
    response_id = respond.json()["response"]["id"]

    accept = client.post(
        f"/api/v1/offers/responses/{response_id}/accept",
        headers={"Authorization": f"Bearer {business_token}"},
    )
    assert accept.status_code == 200

    chats = client.get(
        "/api/v1/chats",
        headers={"Authorization": f"Bearer {business_token}"},
    )
    assert chats.status_code == 200
    chat_id = chats.json()[0]["id"]

    create_deal = client.post(
        "/api/v1/deals",
        headers={"Authorization": f"Bearer {business_token}"},
        json={
            "partner_id": blogger_id,
            "type": "barter",
            "you_offer": "Sunset tasting menu for two",
            "you_receive": "1 reel + 3 story frames",
            "guests": "plus_one",
        },
    )
    assert create_deal.status_code == 201
    deal_body = create_deal.json()
    assert deal_body["chat_id"] == chat_id
    assert deal_body["participant_ids"] == [blogger_id, business_id]

    messages = client.get(
        f"/api/v1/chats/{chat_id}/messages",
        headers={"Authorization": f"Bearer {business_token}"},
    )
    assert messages.status_code == 200
    deal_message = next(
        message
        for message in messages.json()
        if message["deal_card_id"] == deal_body["id"]
    )
    assert deal_message["sender_id"] == business_id
    assert deal_message["text"] == "Great! Here's our deal offer 👇"

    decline = client.post(
        f"/api/v1/deals/{deal_body['id']}/cancel",
        headers={"Authorization": f"Bearer {blogger_token}"},
        json={"reason": "declined"},
    )
    assert decline.status_code == 200
    declined_body = decline.json()
    assert declined_body["status"] == "cancelled"
    assert declined_body["cancellation_reason"] == "declined"


def test_business_can_close_own_offer_and_it_disappears_from_active_feed(
    client: TestClient,
) -> None:
    business_token, _ = _register_and_verify_user(
        client,
        email="biz-close-offer@example.com",
        role="business",
        full_name="Close Resort",
        primary_photo_url="https://example.com/close-offer.jpg",
        instagram_handle="@closeresort",
        audience_size=22_000,
        category="Hospitality",
    )

    create_offer = client.post(
        "/api/v1/offers",
        headers={"Authorization": f"Bearer {business_token}"},
        json={
            "title": "Closing test offer",
            "type": "barter",
            "blogger_receives": "Dinner for two",
            "business_receives": "1 reel + 2 stories",
            "slots_total": 1,
            "photo_url": "https://example.com/close.jpg",
        },
    )
    assert create_offer.status_code == 200
    offer_id = create_offer.json()["id"]

    close_offer = client.post(
        f"/api/v1/offers/{offer_id}/close",
        headers={"Authorization": f"Bearer {business_token}"},
    )
    assert close_offer.status_code == 200
    assert close_offer.json()["status"] == "closed"

    active_offers = client.get("/api/v1/offers")
    assert active_offers.status_code == 200
    assert all(offer["id"] != offer_id for offer in active_offers.json())


def test_deals_require_business_and_blogger_pair(client: TestClient) -> None:
    first_token, _ = _register_and_verify_user(
        client,
        email="blogger-one@example.com",
        role="blogger",
        full_name="Blogger One",
        primary_photo_url="https://example.com/blogger-one.jpg",
        instagram_handle="@bloggerone",
        audience_size=12_000,
    )
    _, second_user_id = _register_and_verify_user(
        client,
        email="blogger-two@example.com",
        role="blogger",
        full_name="Blogger Two",
        primary_photo_url="https://example.com/blogger-two.jpg",
        instagram_handle="@bloggertwo",
        audience_size=14_000,
    )

    create_deal = client.post(
        "/api/v1/deals",
        headers={"Authorization": f"Bearer {first_token}"},
        json={
            "partner_id": second_user_id,
            "type": "paid",
            "you_offer": "A paid post",
            "you_receive": "A hotel stay",
        },
    )
    assert create_deal.status_code == 409
    assert "blogger and a business" in create_deal.json()["error"]["message"]


def test_swipes_require_business_and_blogger_pair(client: TestClient) -> None:
    first_token, _ = _register_and_verify_user(
        client,
        email="blogger-swipe-one@example.com",
        role="blogger",
        full_name="Swipe One",
        primary_photo_url="https://example.com/swipe-one.jpg",
        instagram_handle="@swipeone",
        audience_size=9_000,
    )
    _, second_user_id = _register_and_verify_user(
        client,
        email="blogger-swipe-two@example.com",
        role="blogger",
        full_name="Swipe Two",
        primary_photo_url="https://example.com/swipe-two.jpg",
        instagram_handle="@swipetwo",
        audience_size=11_000,
    )

    swipe = client.post(
        "/api/v1/matches/swipe",
        headers={"Authorization": f"Bearer {first_token}"},
        json={"target_id": second_user_id, "direction": "right"},
    )
    assert swipe.status_code == 409
    assert "blogger and a business" in swipe.json()["error"]["message"]


def test_blogger_feed_only_returns_business_profiles(client: TestClient) -> None:
    blogger_token, _ = _register_and_verify_user(
        client,
        email="feed-blogger@example.com",
        role="blogger",
        full_name="Feed Blogger",
        primary_photo_url="https://example.com/feed-blogger.jpg",
        instagram_handle="@feedblogger",
        audience_size=17_000,
    )

    feed = client.get(
        "/api/v1/matches/feed",
        headers={"Authorization": f"Bearer {blogger_token}"},
    )
    assert feed.status_code == 200
    profiles = feed.json()
    assert profiles
    assert all(profile["role"] == "business" for profile in profiles)


def test_admin_users_reflect_new_registrations_without_restart(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store_path = str(tmp_path / "matcha-store.pickle")
    monkeypatch.setattr(container_module, "STORE_PERSIST_PATH", store_path)

    settings = Settings(media_root=str(tmp_path / "media"))
    with TestClient(create_app(settings=settings)) as api_client, TestClient(create_app(settings=settings)) as admin_client:
        _register_user(
            api_client,
            email="fresh-admin-user@example.com",
            role="blogger",
            full_name="Fresh Admin User",
            primary_photo_url="https://example.com/fresh-admin.jpg",
        )

        response = admin_client.get(
            "/api/v1/admin/users",
            headers={"Authorization": "Bearer matcha-admin-2026"},
        )
        assert response.status_code == 200
        emails = [user["email"] for user in response.json()["users"]]
        assert "fresh-admin-user@example.com" in emails


def test_signup_photo_upload_returns_media_url(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        container_module,
        "STORE_PERSIST_PATH",
        str(tmp_path / "upload-store.pickle"),
    )
    media_root = tmp_path / "media"
    settings = Settings(media_root=str(media_root))

    with TestClient(create_app(settings=settings)) as test_client:
        response = test_client.post(
            "/api/v1/auth/upload-photo",
            files={"file": ("avatar.jpg", b"fake-image-bytes", "image/jpeg")},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["url"].startswith("http://testserver/media/profile-photos/")

    stored_files = list((media_root / "profile-photos").glob("*"))
    assert len(stored_files) == 1
