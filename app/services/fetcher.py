"""Fetches data from LinkedIn for a given profile URL:

1. The plain profile page HTML (top-card info: name, headline, location).
2. Three RSC ("React Server Component") action-endpoint responses that back
   the profile's About / Experience / Education-and-below cards.

Adapted from linkedin_profile.py and fetch_component_fixed.py, restructured
to be called from a request handler (returns data in memory) instead of a
CLI script (which wrote files to disk).
"""
import base64
import codecs
import json
import os
import re
from typing import Optional, Dict, Any

import requests
from curl_cffi import requests as curl_requests

USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64; rv:154.0) Gecko/20100101 Firefox/154.0"


def _cp1252_fallback(exc: UnicodeDecodeError):
    """Error handler for decode('utf-8', errors='cp1252_fallback').

    LinkedIn's RSC action-endpoint responses are UTF-8, but certain
    punctuation (notably the middle-dot separator in "Company · Full-time"
    and "Jan 2004 - Jul 2010 · 6 yrs 7 mos") sometimes comes through as a
    single raw CP-1252/Latin-1 byte (0xB7) instead of the correct 2-byte
    UTF-8 sequence (0xC2 0xB7). Plain `errors="ignore"` drops that byte
    entirely, which silently deletes the "·" and breaks every downstream
    " · " split (company vs employment type, duration parsing, etc).
    This handler recovers the intended character instead of discarding it.
    """
    bad_byte = exc.object[exc.start:exc.start + 1]
    return bad_byte.decode("cp1252", errors="replace"), exc.start + 1


codecs.register_error("cp1252_fallback", _cp1252_fallback)

# The three profile cards we need, and the internal SDUI component ids that
# back them (see fetch_component_fixed.py for how these were captured).
COMPONENTS = {
    "about": {
        "component_id": "com.linkedin.sdui.generated.profile.dsl.impl.profileCardsAboveActivity",
    },
    "experience": {
        "component_id": "com.linkedin.sdui.generated.profile.dsl.impl.profileCardsExperienceOnly",
    },
    "education": {
        "component_id": "com.linkedin.sdui.generated.profile.dsl.impl.profileCardsBelowActivityPart1WithoutExp",
    },
}


class FetchError(RuntimeError):
    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code


def parse_vanity_name(url: str) -> str:
    match = re.search(r'linkedin\.com/in/([^/?#]+)', url)
    if not match:
        raise ValueError("Invalid LinkedIn profile URL")
    return match.group(1).rstrip('/')


def _random_b64(n_bytes: int = 8) -> str:
    return base64.b64encode(os.urandom(n_bytes)).decode()


def _random_hex(n_bytes: int = 16) -> str:
    return os.urandom(n_bytes).hex()


def fetch_profile_html(vanity_name: str, cookies: Dict[str, str]) -> str:
    """Fetch the plain profile page HTML (used for top-card info)."""
    url = f"https://www.linkedin.com/in/{vanity_name}/"
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }
    response = requests.get(url, cookies=cookies, headers=headers, timeout=20)
    if response.status_code != 200:
        raise FetchError(f"Failed to fetch profile page ({response.status_code})", response.status_code)
    return response.text


def _build_payload(vanity_name: str, viewee_profile_id: str) -> Dict[str, Any]:
    def binding(key: str) -> Dict[str, Any]:
        return {
            "type": "com.linkedin.sdui.components.core.BindingImpl",
            "value": {"key": key, "namespace": "MemoryNamespace"},
        }

    return {
        "clientArguments": {
            "payload": {
                "isSelfView": False,
                "vanityName": vanity_name,
                "replaceableSectionArgs": {
                    "vanityName": vanity_name,
                    "hideCardsForGoldenGate": False,
                    "shouldSetupReplaceableComponent": True,
                    "vieweeProfileId": viewee_profile_id,
                    "isSelfView": False,
                    "isSelfViewResolved": False,
                },
                "profileComponentState": {
                    "profileId": vanity_name,
                    "shouldRefreshScreenOnReappear": binding(f"ProfileComponentStateShouldRefreshScreen{vanity_name}ProfileComponentState"),
                    "shouldFetchFromCache": binding(f"ProfileComponentStateFetchFromCache{vanity_name}ProfileComponentState"),
                    "shouldDisplayTabAnchors": binding(f"ProfileComponentStateShouldDisplayTabAnchors{vanity_name}ProfileComponentState"),
                    "shouldReloadTopCardOnReappear": binding(f"ProfileComponentStateShouldReloadTopCardOnReappear{vanity_name}ProfileComponentState"),
                    "deferredTopCardReloadProfileId": binding(f"ProfileComponentStateDeferredTopCardReloadProfileId{vanity_name}ProfileComponentState"),
                    "shouldDisplayStickyHeader": binding(f"ProfileComponentStateShouldDisplayStickyHeader{vanity_name}ProfileComponentState"),
                    "shouldRefreshLanguageDetailScreen": binding(f"ProfileComponentStateShouldRefreshLanguageDetails{vanity_name}ProfileComponentState"),
                    "lastPerformedActionRef": binding(f"ProfileComponentStateLastPerformedActionRef{vanity_name}ProfileComponentState"),
                    "shouldFocusOnReappear": binding(f"ProfileComponentStateShouldFocusOnReappear{vanity_name}ProfileComponentState"),
                    "shouldFocusFeaturedOnReappear": binding(f"ProfileComponentStateShouldFocusFeaturedOnReappear{vanity_name}ProfileComponentState"),
                    "lastFeaturedActionRef": binding(f"ProfileComponentStateLastFeaturedActionRef{vanity_name}ProfileComponentState"),
                    "shouldHideProfileCards": binding(f"ProfileComponentStateProfileHideCards{vanity_name}ProfileComponentState"),
                },
            },
            "states": [],
            "requestMetadata": {"$type": "proto.sdui.common.RequestMetadata"},
            "screenId": "com.linkedin.sdui.flagshipnav.profile.Profile",
            "knownTemplateIds": [],
        }
    }


def fetch_component(
    vanity_name: str,
    viewee_profile_id: str,
    component_id: str,
    cookies: Dict[str, str],
) -> str:
    """Fetch a single SDUI/RSC component's raw response text."""
    csrf_token = cookies["JSESSIONID"]
    trace_id = _random_hex(16)
    span_id = _random_hex(8)
    page_instance_tracking_id = _random_b64(16)
    application_instance = _random_b64(16)
    page_forest_id = _random_hex(16)

    headers = {
        "accept": "*/*",
        "accept-encoding": "gzip, deflate, br, zstd",
        "accept-language": "en-US,en;q=0.9",
        "content-type": "application/json",
        "origin": "https://www.linkedin.com",
        "referer": f"https://www.linkedin.com/in/{vanity_name}/",
        "user-agent": USER_AGENT,
        "x-li-rsc-stream": "true",
        "x-li-anchor-page-key": "d_flagship3_profile_view_base",
        "x-li-application-version": "0.2.7003",
        "x-li-track": json.dumps({
            "clientVersion": "0.2.7003",
            "mpVersion": "0.2.7003",
            "osName": "web",
            "timezoneOffset": 5.5,
            "timezone": "Asia/Kolkata",
            "deviceFormFactor": "DESKTOP",
            "mpName": "web",
            "displayDensity": 1,
            "displayWidth": 1920,
            "displayHeight": 1080,
        }),
        "priority": "u=4",
        "te": "trailers",
        "csrf-token": csrf_token,
        "x-li-page-instance-tracking-id": page_instance_tracking_id,
        "x-li-application-instance": application_instance,
        "x-li-page-instance": f"urn:li:page:d_flagship3_profile_view_base;{page_instance_tracking_id}",
        "x-li-traceparent": f"00-{trace_id}-{span_id}-00",
        "x-li-tracestate": f"LinkedIn={span_id}",
        "x-li-pageforestid": page_forest_id,
    }

    url = "https://www.linkedin.com/flagship-web/rsc-action/actions/component"
    params = {
        "componentId": component_id,
        "sduiid": component_id,
        "parentSpanId": _random_b64(8),
    }

    payload = _build_payload(vanity_name, viewee_profile_id)

    response = curl_requests.post(
        url,
        headers=headers,
        cookies=cookies,
        json=payload,
        params=params,
        impersonate="firefox133",
        timeout=20,
    )

    if response.status_code != 200:
        raise FetchError(
            f"Failed to fetch component '{component_id}' ({response.status_code}): {response.text[:300]}",
            response.status_code,
        )

    return response.content.decode("utf-8", errors="cp1252_fallback")


def fetch_all_components(vanity_name: str, viewee_profile_id: str, cookies: Dict[str, str]) -> Dict[str, str]:
    """Fetch all three profile cards' raw RSC content, keyed by section name."""
    results = {}
    for section, meta in COMPONENTS.items():
        results[section] = fetch_component(vanity_name, viewee_profile_id, meta["component_id"], cookies)
    return results