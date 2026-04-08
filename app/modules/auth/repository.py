from __future__ import annotations

from typing import Protocol

from app.modules.auth.domain.models import User


class AuthRepository(Protocol):
    def add(self, user: User) -> User: ...

    def get_by_id(self, user_id: str) -> User | None: ...

    def get_by_email(self, email: str) -> User | None: ...

    def update(self, user: User) -> User: ...

    def delete(self, user_id: str) -> None: ...


class InMemoryAuthRepository:
    def __init__(self, store):
        self.store = store

    def add(self, user: User) -> User:
        self.store.users[user.id] = user
        self.store.persist()
        return user

    def get_by_id(self, user_id: str) -> User | None:
        return self.store.users.get(user_id)

    def get_by_email(self, email: str) -> User | None:
        return next(
            (user for user in self.store.users.values() if user.email == email),
            None,
        )

    def update(self, user: User) -> User:
        self.store.users[user.id] = user
        self.store.persist()
        return user

    def delete(self, user_id: str) -> None:
        self.store.users.pop(user_id, None)
        self.store.persist()
