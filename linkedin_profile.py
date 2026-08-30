#!/usr/bin/env python3
import sys
import json
import re
import argparse
import requests


def load_cookies_from_har(har_path: str) -> dict:
    with open(har_path) as f:
        har = json.load(f)
    cookies = {}
    for cookie in har['log']['entries'][0]['request']['cookies']:
        cookies[cookie['name']] = cookie['value']
    return cookies


def extract_profile_from_html(html: str) -> dict:
    result = {
        "full_name": None,
        "headline": None,
        "location": None,
        "profile_canonical_url": None
    }

    # Extract firstName and lastName from the embedded JSON in HTML
    # Format: firstName\":\"Amit Kumar\",\"lastName\":\"Mishra\"
    fn_match = re.search(r'firstName\\":\\"([^"]+)\\"', html)
    ln_match = re.search(r'lastName\\":\\"([^"]+)\\"', html)
    if fn_match and ln_match:
        result["full_name"] = f"{fn_match.group(1)} {ln_match.group(1)}"

    # Extract profileCanonicalUrl
    url_match = re.search(r'profileCanonicalUrl\\":\\"([^"]+)\\"', html)
    if url_match:
        result["profile_canonical_url"] = url_match.group(1)

    # Extract headline from the profile top card - second p tag with headline classes
    headline_matches = list(re.finditer(
        r'<p class="[^"]*_02484ad3[^"]*_4e33f71b[^"]*">[^<]*<span[^>]*>([^<]{10,})</span>',
        html
    ))
    if len(headline_matches) >= 2:
        result["headline"] = headline_matches[1].group(1).strip()
    elif len(headline_matches) == 1:
        result["headline"] = headline_matches[0].group(1).strip()

    # Extract location from HTML
    for m in re.finditer(r'>([A-Za-z\s]+,\s*[A-Za-z\s]+,\s*[A-Za-z\s]+)<', html):
        text = m.group(1).strip()
        if re.search(r'[A-Za-z]+,\s*[A-Za-z\s]+,\s*[A-Za-z\s]+', candidate := text):
            result["location"] = candidate
            break

    return result


def main():
    parser = argparse.ArgumentParser(description="Fetch LinkedIn profile info")
    parser.add_argument("url", help="LinkedIn profile URL")
    parser.add_argument("--har", default="ProfileInfo.har", help="Path to HAR file for cookies")
    args = parser.parse_args()

    cookies = load_cookies_from_har(args.har)

    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:154.0) Gecko/20100101 Firefox/154.0",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }

    response = requests.get(args.url, cookies=cookies, headers=headers)
    response.raise_for_status()

    profile = extract_profile_from_html(response.text)
    print(json.dumps(profile, indent=2))


if __name__ == "__main__":
    main()