"""Decorated functions and methods, mimicking a web framework's routing style."""


def route(path: str):
    def decorator(func):
        func.__route__ = path
        return func

    return decorator


@route("/health")
def health_check():
    """Return service health status."""
    return {"status": "ok"}


class Handlers:
    @staticmethod
    def static_helper(x: int) -> int:
        return x + 1

    @property
    def name(self) -> str:
        """The handler's display name."""
        return "handlers"

    @route("/users/<id>")
    def get_user(self, id: str):
        return {"id": id}
