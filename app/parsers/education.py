"""Parses the 'education' section out of LinkedIn's
profileCardsBelowActivityPart1WithoutExp RSC response.

Light refactor of the original parse_education.py: same logic, adapted to
operate on an already-fetched response string (parse_education_content)
instead of a filepath. A file-based entrypoint is kept for convenience.
"""
import re
from typing import Optional, List, Dict, Any, Set
from pydantic import BaseModel

from .common import parse_rsc_content, extract_plain_text


class Education(BaseModel):
    school: str
    degree: Optional[str] = None
    field_of_study: Optional[str] = None
    duration: Optional[str] = None
    grade: Optional[str] = None
    activities_and_societies: Optional[str] = None


def find_education_collection(nodes: Dict) -> Optional[List]:
    """Find the top-level node whose collectionId/collectionKey refers to the
    Education section (e.g. 'profile_EducationTopLevelSection_...')."""
    import json

    for node in nodes.values():
        if not isinstance(node, list) or len(node) < 4:
            continue
        props = node[3] if isinstance(node[3], dict) else {}
        if 'initialItems' not in props:
            continue

        haystack = json.dumps(props.get('collectionId', '')) + json.dumps(props.get('collectionKey', ''))
        if 'educationtoplevelsection' in haystack.lower():
            return props['initialItems']

    return None


def walk_item(node: Any, nodes: Dict, visited: Set[str], output: List[Dict]):
    """Recursively walk a single education item's structure (resolving any
    '$Lxx' references against the top-level nodes dict) and collect every
    piece of visible text along with a rough classification of its role."""

    if isinstance(node, str):
        m = re.match(r'^\$L([0-9a-f]+)$', node)
        if m:
            key = m.group(1)
            if key in nodes and key not in visited:
                visited.add(key)
                walk_item(nodes[key], nodes, visited, output)
        return

    if isinstance(node, dict):
        for v in node.values():
            walk_item(v, nodes, visited, output)
        return

    if isinstance(node, list):
        if len(node) >= 4 and node[0] == '$':
            tag = node[1]
            props = node[3] if isinstance(node[3], dict) else {}

            if tag == 'p':
                text = extract_plain_text(props.get('children'))
                if text:
                    output.append({'kind': 'p', 'text': text})
                return

            if isinstance(tag, str) and tag.startswith('$L') and 'textProps' in props:
                text_props = props['textProps']
                text = extract_plain_text(text_props.get('children'))
                if text:
                    output.append({
                        'kind': 'text_component',
                        'color': props.get('textColorExpression'),
                        'text': text,
                    })
                return

            if tag == '$L30':  # image component -> capture alt text just in case
                alt = props.get('a11yText')
                if alt:
                    output.append({'kind': 'image_alt', 'text': alt})
                return

            for key, value in props.items():
                walk_item(value, nodes, visited, output)
            return

        for item in node:
            walk_item(item, nodes, visited, output)
        return


DATE_RE = re.compile(
    r'(present|(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)?[a-z]*\.?\s*\d{4})',
    re.IGNORECASE,
)


def looks_like_duration(text: str) -> bool:
    if ('\u2013' in text or '\u2014' in text or '-' in text) and DATE_RE.search(text):
        return True
    if re.fullmatch(r'\d{4}\s*[\u2013\u2014-]\s*(\d{4}|present)', text.strip(), re.IGNORECASE):
        return True
    return False


def looks_like_skills_line(text: str) -> bool:
    return bool(re.search(r'\bskills?\b', text, re.IGNORECASE)) and (
        re.search(r'\+\d+\s*skills?$', text, re.IGNORECASE) or 'see_details' in text.lower()
    )


def classify_item(entries: List[Dict]) -> Education:
    school = None
    degree_field_text = None
    duration = None
    grade = None
    activities = None

    plain_texts = []

    for e in entries:
        text = e['text'].strip()
        if not text:
            continue

        if e['kind'] == 'text_component':
            if duration is None and (e.get('color') == 179 or looks_like_duration(text)):
                duration = text
            continue

        if e['kind'] == 'image_alt':
            fallback = re.sub(r'\s*logo\s*$', '', text, flags=re.IGNORECASE).strip()
            if school is None and fallback:
                school = fallback
            continue

        if e['kind'] == 'p':
            if text.lower().startswith('grade:'):
                grade = text.split(':', 1)[1].strip()
                continue
            if text.lower().startswith('activities and societies:'):
                activities = text.split(':', 1)[1].strip()
                continue
            if looks_like_skills_line(text):
                continue
            if looks_like_duration(text):
                if duration is None:
                    duration = text
                continue
            plain_texts.append(text)

    if plain_texts:
        school = plain_texts[0]
        if len(plain_texts) > 1:
            degree_field_text = plain_texts[1]

    degree = None
    field_of_study = None
    if degree_field_text:
        if ',' in degree_field_text:
            degree, field_of_study = degree_field_text.split(',', 1)
            degree = degree.strip()
            field_of_study = field_of_study.strip()
        else:
            degree = degree_field_text.strip()

    return Education(
        school=school or "Unknown School",
        degree=degree,
        field_of_study=field_of_study,
        duration=duration,
        grade=grade,
        activities_and_societies=activities,
    )


def parse_education_content(content: str) -> List[Education]:
    """Parse education entries from a profileCardsBelowActivityPart1WithoutExp
    RSC response string."""
    nodes = parse_rsc_content(content)
    initial_items = find_education_collection(nodes)

    if not initial_items:
        return []

    educations = []
    for item in initial_items:
        entries: List[Dict] = []
        walk_item(item.get('item'), nodes, set(), entries)
        if entries:
            educations.append(classify_item(entries))

    return educations


# --- File-based entrypoint (kept for local testing / backwards compat) ---

def parse_education_file(filepath: str) -> List[Education]:
    with open(filepath, 'r') as f:
        return parse_education_content(f.read())
