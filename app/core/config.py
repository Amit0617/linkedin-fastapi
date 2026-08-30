from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# app/core/config.py -> app/core -> app -> repo root
BASE_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_ignore_empty=True,
        extra="ignore",
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
    )

    PROJECT_NAME: str = "LinkedIn Profile API"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"

    # Optional: lets you skip live-resolving the internal LinkedIn member id
    LI_VIEWEE_PROFILE_ID: str | None = None

    # Rate limiting
    REQUEST_DELAY_SECONDS: float = 2.0
    MAX_RETRIES: int = 3

    # LinkedIn session cookies (these are the actual pydantic-settings fields
    # now - values come from env vars / .env file of the same name)
    LI_AT: str | None = None
    JSESSIONID: str | None = None
    BCOOKIE: str | None = None
    BSCOOKIE: str | None = None
    LIDC: str | None = None

    # Maps the cookie name LinkedIn expects -> the Settings field that holds it
    REQUIRED_COOKIE_FIELDS: dict = {
        "li_at": "LI_AT",
        "JSESSIONID": "JSESSIONID",
        "bcookie": "BCOOKIE",
        "bscookie": "BSCOOKIE",
        "lidc": "LIDC",
    }


settings = Settings()


class ConfigError(RuntimeError):
    pass


def get_cookies() -> dict:
    """Read the LinkedIn session cookies out of Settings.

    Raises ConfigError listing any missing variables so failures are
    actionable rather than a confusing downstream 401/403 from LinkedIn.
    """
    cookies = {}
    missing = []
    for cookie_name, field_name in settings.REQUIRED_COOKIE_FIELDS.items():
        value = getattr(settings, field_name, None)
        if not value:
            missing.append(field_name)
        else:
            cookies[cookie_name] = value

    if missing:
        raise ConfigError(
            "Missing required environment variable(s): " + ", ".join(missing)
        )
    return cookies


DEFAULT_VIEWEE_PROFILE_ID = settings.LI_VIEWEE_PROFILE_ID