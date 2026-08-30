"""Extracts basic top-card profile info (name, headline, location, canonical
URL) from the raw HTML of a LinkedIn profile page.

Adapted directly from linkedin_profile.py's extract_profile_from_html.
"""
import re
from typing import Optional
from pydantic import BaseModel


class TopCard(BaseModel):
    full_name: Optional[str] = None
    headline: Optional[str] = None
    location: Optional[str] = None
    profile_canonical_url: Optional[str] = None


def extract_profile_from_html(html: str) -> TopCard:
    result = TopCard()

    # firstName / lastName embedded in the page's inline JSON.
    fn_match = re.search(r'firstName\\":\\"([^"]+)\\"', html)
    ln_match = re.search(r'lastName\\":\\"([^"]+)\\"', html)
    if fn_match and ln_match:
        result.full_name = f"{fn_match.group(1)} {ln_match.group(1)}"

    url_match = re.search(r'profileCanonicalUrl\\":\\"([^"]+)\\"', html)
    if url_match:
        result.profile_canonical_url = url_match.group(1)

    headline_matches = list(re.finditer(
        r'<p class="[^"]*_02484ad3[^"]*_4e33f71b[^"]*">[^<]*<span[^>]*>([^<]{10,})</span>',
        html
    ))
    if len(headline_matches) >= 2:
        result.headline = headline_matches[1].group(1).strip()
    elif len(headline_matches) == 1:
        result.headline = headline_matches[0].group(1).strip()

    for m in re.finditer(r'>([A-Za-z\s]+,\s*[A-Za-z\s]+,\s*[A-Za-z\s]+)<', html):
        text = m.group(1).strip()
        if re.search(r'[A-Za-z]+,\s*[A-Za-z\s]+,\s*[A-Za-z\s]+', text):
            result.location = text
            break

    return result
