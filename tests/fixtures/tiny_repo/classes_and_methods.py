"""Classes with methods, including a nested class."""


class UserStore:
    """In-memory store of users."""

    def __init__(self) -> None:
        self._users: dict[str, str] = {}

    def add_user(self, username: str, email: str) -> None:
        """Register a new user."""
        self._users[username] = email

    def get_user(self, username: str) -> str | None:
        return self._users.get(username)

    class Config:
        """Nested configuration class."""

        max_users: int = 100

        def is_full(self, current_count: int) -> bool:
            return current_count >= self.max_users
