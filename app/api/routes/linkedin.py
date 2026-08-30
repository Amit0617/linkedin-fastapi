from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, HttpUrl

from app.core.config import get_cookies, ConfigError, DEFAULT_VIEWEE_PROFILE_ID
from app.services.fetcher import (
    parse_vanity_name,
    fetch_profile_html,
    fetch_all_components,
    FetchError,
)
from app.parsers import (
    extract_profile_from_html,
    parse_about_content,
    parse_experience_content,
    parse_education_content,
)

router = APIRouter(prefix= "/linkedin", tags=["linkedin"])


class ProfileRequest(BaseModel):
    url: HttpUrl = "https://linkedin.com/in/amit0617"


@router.get("/health")
def health():
    return {"status": "ok"}


@router.post("/profile")
def get_profile(payload: ProfileRequest):
    url = str(payload.url)

    try:
        vanity_name = parse_vanity_name(url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    try:
        cookies = get_cookies()
    except ConfigError as e:
        raise HTTPException(status_code=500, detail=str(e))

    try:
        html = fetch_profile_html(vanity_name, cookies)
    except FetchError as e:
        raise HTTPException(status_code=502, detail=f"Could not fetch profile page: {e}")

    top_card = extract_profile_from_html(html)

    viewee_profile_id = DEFAULT_VIEWEE_PROFILE_ID

    try:
        components = fetch_all_components(vanity_name, viewee_profile_id, cookies)
    except FetchError as e:
        raise HTTPException(status_code=502, detail=f"Could not fetch profile components: {e}")

    about = parse_about_content(components["about"])
    experiences = parse_experience_content(components["experience"])
    education = parse_education_content(components["education"])

    return {
        # "input_url": url,
        "vanity_name": vanity_name,
        "profile": top_card.model_dump(),
        "about": about,
        "experiences": [e.model_dump() for e in experiences],
        "education": [e.model_dump() for e in education],
    }