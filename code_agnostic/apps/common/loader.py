_LOADED = False


def load_app_service_modules() -> None:
    global _LOADED
    if _LOADED:
        return

    from code_agnostic.apps.codex import service as _codex_service  # noqa: F401
    from code_agnostic.apps.cursor import service as _cursor_service  # noqa: F401
    from code_agnostic.apps.opencode import service as _opencode_service  # noqa: F401

    _LOADED = True
