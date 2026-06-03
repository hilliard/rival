from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version


PACKAGE_NAME = "haynesworld-rival"
SERVICE_NAME = "rival-api"
FALLBACK_APP_VERSION = "1.0.0"


def get_app_version() -> str:
    try:
        return version(PACKAGE_NAME)
    except PackageNotFoundError:
        return FALLBACK_APP_VERSION


def get_api_version(app_version: str) -> str:
    major = app_version.split(".", 1)[0].strip()
    if not major.isdigit():
        return "v0"
    return f"v{major}"


APP_VERSION = get_app_version()
API_VERSION = get_api_version(APP_VERSION)