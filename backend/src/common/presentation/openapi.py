from fastapi.routing import APIRoute


def operation_id(route: APIRoute) -> str:
    """Readable, stable operationIds: `<first tag>-<endpoint function name>`, e.g. `auth-login`."""
    return f"{route.tags[0]}-{route.name}" if route.tags else route.name
