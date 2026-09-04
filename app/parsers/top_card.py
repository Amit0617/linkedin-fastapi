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

    # The page embeds its hydration data as a JSON string inside a JS string
    # inside HTML, so every real quote/backslash in the payload shows up
    # backslash-escaped -- and escaped more than once, with the exact depth
    # varying by where in the page it's nested. Rather than hardcode a
    # specific number of backslashes (which is what broke the previous
    # firstName/lastName regexes the moment the escaping depth shifted),
    # strip all backslashes up front. None of the fields we're after
    # (names, headlines, locations, vanity names) can legitimately contain a
    # literal backslash, so this is safe and makes the rest of the regexes
    # simple and robust to escaping-depth changes.
    clean = re.sub(r'\\+', '', html)

    # LinkedIn renamed the profile-identity fields at some point: what used
    # to be "firstName"/"lastName" is now "givenName"/"familyName". They
    # always appear together with the profile's own "vanityName" in one
    # object, e.g. {"vanityName":"amit0617","givenName":"Amit
    # Kumar","familyName":"Mishra",...} -- anchoring on that whole triple
    # (rather than a bare "givenName" search) avoids accidentally matching a
    # *different* person's name if a similarly-shaped object ever appears
    # elsewhere on the page (e.g. a "People also viewed" suggestion).
    identity_match = re.search(
        r'"vanityName":"([^"]+)","givenName":"([^"]+)","familyName":"([^"]+)"',
        clean,
    )
    vanity_name = None
    if identity_match:
        vanity_name, given_name, family_name = identity_match.groups()
        result.full_name = f"{given_name} {family_name}"
    else:
        # Fall back to the older field names in case an older response
        # format is ever encountered.
        fn_match = re.search(r'"firstName":"([^"]+)"', clean)
        ln_match = re.search(r'"lastName":"([^"]+)"', clean)
        if fn_match and ln_match:
            result.full_name = f"{fn_match.group(1)} {ln_match.group(1)}"

    # "profileCanonicalUrl" no longer appears in the page at all; rebuild the
    # canonical profile URL from the vanity name we already have instead.
    if vanity_name:
        result.profile_canonical_url = f"https://www.linkedin.com/in/{vanity_name}/"
    else:
        url_match = re.search(r'"profileCanonicalUrl":"([^"]+)"', clean)
        if url_match:
            result.profile_canonical_url = url_match.group(1)

    # The headline renders as plain text in a <span> inside the very next
    # sibling <p> after the name's own <p>...</p> in the real (server-
    # rendered) markup. We anchor on the name text itself (which we've
    # already extracted) rather than on class-hash selectors like the old
    # '_02484ad3'/'_4e33f71b' ones, which rot every time LinkedIn's atomic-
    # CSS build regenerates its hashes -- see the experience-section
    # parser's notes on the same class of problem.
    if result.full_name:
        name_idx = html.find(f'>{result.full_name}</p>')
        if name_idx != -1:
            window = html[name_idx:name_idx + 600]
            headline_match = re.search(r'<span[^>]*>([^<]{5,300})</span>', window)
            if headline_match:
                result.headline = headline_match.group(1).strip()

    if result.headline is None:
        # Fall back to the older className-based markup shape, in case this
        # page was served without the name showing up in plain rendered
        # markup at all.
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