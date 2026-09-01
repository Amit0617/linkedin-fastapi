"""Parses the 'about' and 'experience' sections out of LinkedIn's
profileCardsAboveActivity / profileCardsExperienceOnly RSC responses.

This is a light refactor of the original parse_profile.py: the parsing
logic is unchanged, it's just been adapted to operate on an already-fetched
response string (parse_*_content) instead of reading a file from disk.
File-based entrypoints are kept for local testing / backwards compatibility.
"""
import re
from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel

from .common import parse_rsc_content, parse_rsc_file, extract_plain_text


class Experience(BaseModel):
    title: str
    company: str
    location: Optional[str] = None
    duration: Optional[str] = None
    description: Optional[str] = None
    employment_type: Optional[str] = None


class Profile(BaseModel):
    about: Optional[str] = None
    experiences: List[Experience] = []


def extract_start_date(duration: Optional[str]) -> datetime:
    """Extract start date from duration string for sorting."""
    if not duration:
        return datetime(1900, 1, 1)

    match = re.search(r'(\w+)\s+(\d{4})', duration)
    if match:
        month_str, year_str = match.groups()
        try:
            return datetime.strptime(f"{month_str} {year_str}", "%b %Y")
        except ValueError:
            pass

    return datetime(1900, 1, 1)


def extract_end_date(duration: Optional[str]) -> datetime:
    """Extract end date from duration string for sorting (most recent first)."""
    if not duration:
        return datetime(1900, 1, 1)

    if "Present" in duration:
        return datetime(2099, 12, 31)

    parts = duration.split(" - ")
    if len(parts) >= 2:
        end_part = parts[1]
        match = re.search(r'(\w+)\s+(\d{4})', end_part)
        if match:
            month_str, year_str = match.groups()
            try:
                return datetime.strptime(f"{month_str} {year_str}", "%b %Y")
            except ValueError:
                pass

    return datetime(1900, 1, 1)


def get_initial_items_order(nodes: Dict) -> List[Dict]:
    """Get the visual order of experiences from initialItems in node 'e'."""
    if 'e' not in nodes:
        return []

    node = nodes['e']
    if not isinstance(node, list) or len(node) < 4:
        return []

    initial_items = node[3].get('initialItems', [])
    ordered_items = []

    for item in initial_items:
        comp_key = item.get('key')
        comp = item.get('item', [])

        l_refs = []

        def find_lrefs(n):
            if isinstance(n, list):
                for x in n:
                    find_lrefs(x)
            elif isinstance(n, dict):
                for v in n.values():
                    find_lrefs(v)
            elif isinstance(n, str) and n.startswith('$L'):
                l_refs.append(n)

        find_lrefs(comp)
        ordered_items.append({'entity_id': comp_key, 'l_refs': l_refs})

    return ordered_items


def find_content_nodes(nodes: Dict, line_numbers: Dict) -> Dict[str, List[Dict]]:
    """Find all content nodes grouped by type with their line numbers."""
    content = {
        'titles': [],
        'companies': [],
        'employment_types': [],
        'durations': [],
        'locations': [],
        'descriptions': [],
        'skill_links': [],
    }

    for key, node in nodes.items():
        if not isinstance(node, list) or len(node) < 4:
            continue

        line_num = line_numbers.get(key, 0)
        props = node[3] if isinstance(node[3], dict) else {}
        class_name = props.get('className', '')
        children = props.get('children', '')

        node_str = json_dumps_safe(node)

        if node[1] == 'p' and 'skill-associations-details' in node_str:
            match = re.search(r'/overlay/(\d+)/skill-associations-details', node_str)
            position_id = match.group(1) if match else None
            content['skill_links'].append({'key': key, 'position_id': position_id, 'line': line_num, 'node': node})

        elif node[1] == 'p':
            # NOTE: we intentionally don't match on specific className hashes
            # here (e.g. the old 'c2d1c236' / '_61558a10' selectors). Those are
            # atomic-CSS classes that LinkedIn regenerates on every deploy, so
            # any hardcoded hash rots the next time their frontend rebuilds.
            #
            # Instead we use a structural signal that's stable across builds:
            # the position *title* <p> always carries an inline `style` dict
            # (for line-clamp/truncation), while the *company* <p> never does.
            if isinstance(children, list) and children:
                text = children[0] if isinstance(children[0], str) else ''
                if text and len(text) < 150:
                    if 'style' in props:
                        content['titles'].append({'key': key, 'text': text, 'line': line_num})
                    else:
                        content['companies'].append({'key': key, 'text': text, 'line': line_num})

        elif node[1] == '$Lf' and props.get('textColorExpression') == 176:
            text_props = props.get('textProps', {})
            text_children = text_props.get('children', '')
            if isinstance(text_children, list) and text_children:
                text = text_children[0] if isinstance(text_children[0], str) else ''
                if text and text.strip():
                    content['employment_types'].append({'key': key, 'text': text.strip(), 'line': line_num})

        elif node[1] == '$Lf' and props.get('textColorExpression') == 179:
            text_props = props.get('textProps', {})
            text_children = text_props.get('children', '')
            if isinstance(text_children, list) and text_children:
                text = text_children[0] if isinstance(text_children[0], str) else ''
                if text and re.search(r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{4}', text):
                    content['durations'].append({'key': key, 'text': text, 'line': line_num})
                else:
                    content['locations'].append({'key': key, 'text': text, 'line': line_num})

        elif node[1] in ('$L43', '$L51', '$L42', '$L44', '$L3c') and 'textProps' in props:
            content['descriptions'].append({'key': key, 'node': node, 'line': line_num})

    for field_type in content:
        content[field_type].sort(key=lambda x: x['line'])

    return content


def json_dumps_safe(node: Any) -> str:
    import json
    return json.dumps(node)


def extract_description_text(node: Dict) -> str:
    """Extract description text from expandable text node ($L43, $L51, etc)."""
    if not isinstance(node, list) or len(node) < 4:
        return ""

    props = node[3]
    if not isinstance(props, dict) or 'textProps' not in props:
        return ""

    text_props = props['textProps']
    children = text_props.get('children', [])
    desc_lines = []
    seen = set()

    def extract(ch):
        if isinstance(ch, list):
            for item in ch:
                extract(item)
        elif isinstance(ch, dict):
            if 'children' in ch:
                extract(ch['children'])
            for v in ch.values():
                extract(v)
        elif isinstance(ch, str):
            if ch and not ch.startswith('$') and len(ch) > 10:
                normalized = ch.strip()
                if normalized and normalized not in seen:
                    if ch.startswith(('-', '•', '1.', '2.', '3.', '4.', '5.', '6.', '7.', '8.', '9.')):
                        desc_lines.append(normalized)
                        seen.add(normalized)
                    elif len(ch) > 30 and not any(kw in ch.lower() for kw in ['skill', 'association', 'overlay', 'credential', 'issued', 'text-attr']):
                        desc_lines.append(normalized)
                        seen.add(normalized)

    extract(children)
    return "\n".join(desc_lines)


def group_content_by_experience(content: Dict) -> List[Dict]:
    """Group content nodes into experience groups by matching skill_links to content blocks."""
    titles = content['titles']
    companies = content['companies']
    employment_types = content['employment_types']
    skill_links = sorted(content['skill_links'], key=lambda s: s['line'])
    blocks = []
    current_company_name = None

    for i, title in enumerate(titles):
        title_line = title['line']
        next_title_line = titles[i + 1]['line'] if i + 1 < len(titles) else float('inf')

        company = None
        for c in companies:
            if title_line <= c['line'] < next_title_line:
                company = c
                if " · " in c['text']:
                    current_company_name = c['text'].split(" · ")[0].strip()
                else:
                    current_company_name = c['text']
                break

        if company and title['text'].strip() == company['text'].strip():
            current_company_name = company['text'].strip()
            continue

        has_duration = any(title_line <= d['line'] < next_title_line for d in content['durations'])
        has_employment = any(title_line <= et['line'] < next_title_line for et in employment_types)

        is_company_header = (
            len(title['text'].split()) <= 2 and
            not re.search(r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)', title['text'], flags=re.I) and
            not re.search(r'\b(engineer|developer|manager|intern|analyst|specialist|lead|architect)\b', title['text'], flags=re.I) and
            i + 1 < len(titles)
        )

        if not company and i + 1 < len(titles):
            next_title = titles[i + 1]
            next_next_line = titles[i + 2]['line'] if i + 2 < len(titles) else float('inf')
            next_has_duration = any(next_title['line'] <= d['line'] < next_next_line for d in content['durations'])
            next_has_employment = any(next_title['line'] <= et['line'] < next_next_line for et in employment_types)
            next_has_location = any(next_title['line'] <= l['line'] < next_next_line for l in content['locations'])
            next_has_role_metadata = next_has_duration or next_has_employment or next_has_location
            if (not has_duration and not has_employment and next_has_role_metadata) or is_company_header:
                current_company_name = title['text'].strip()
                continue

        if not company and current_company_name:
            company = {'text': current_company_name, 'line': title_line, 'key': title['key']}
        elif company and company.get('text') and not current_company_name:
            current_company_name = company['text'].strip()

        duration = None
        for d in content['durations']:
            if title_line <= d['line'] < next_title_line:
                duration = d
                break

        location = None
        for l in content['locations']:
            if title_line <= l['line'] < next_title_line:
                location = l
                break

        employment_type = None
        for et in employment_types:
            if title_line <= et['line'] < next_title_line:
                employment_type = et
                break

        blocks.append({
            'title': title,
            'company': company,
            'employment_type': employment_type,
            'duration': duration,
            'location': location,
            'description': None,
            'start_line': title_line,
            'end_line': next_title_line
        })

    blocks.sort(key=lambda b: b['start_line'])

    visual_pos_ids = [sl['position_id'] for sl in skill_links]
    if not skill_links:
        for i, block in enumerate(blocks):
            block['position_id'] = f'pos_{i}'
    elif not blocks:
        for i, block in enumerate(blocks):
            block['position_id'] = f'pos_{i}'
    elif skill_links[0]['line'] < blocks[0]['start_line']:
        for i, block in enumerate(blocks):
            if i < len(skill_links):
                block['position_id'] = skill_links[i]['position_id']
            else:
                block['position_id'] = f'pos_{i}'
    else:
        assigned = set()
        for sl in skill_links:
            for i, block in enumerate(blocks):
                if i in assigned:
                    continue
                if block['start_line'] <= sl['line'] < block['end_line']:
                    block['position_id'] = sl['position_id']
                    assigned.add(i)
                    break
        for i, block in enumerate(blocks):
            if i not in assigned:
                block['position_id'] = f'pos_{i}'

    pos_id_to_visual_idx = {pid: idx for idx, pid in enumerate(visual_pos_ids)}

    blocks_with_pos = [b for b in blocks if 'position_id' in b]
    blocks_with_pos.sort(key=lambda b: pos_id_to_visual_idx.get(b['position_id'], 999))

    block_descs = {i: [] for i in range(len(blocks_with_pos))}
    for desc in content['descriptions']:
        for i, block in enumerate(blocks_with_pos):
            if block['start_line'] <= desc['line'] < block['end_line']:
                block_descs[i].append(desc)
                break

    for i in range(len(blocks_with_pos)):
        while len(block_descs[i]) > 1:
            extra = block_descs[i].pop()
            for j in range(i - 1, -1, -1):
                if len(block_descs[j]) == 0:
                    block_descs[j].append(extra)
                    break

    for i, block in enumerate(blocks_with_pos):
        if block_descs[i]:
            block['description'] = block_descs[i][0]

    groups = []
    for i, block in enumerate(blocks_with_pos):
        if i < len(skill_links):
            skill_link = skill_links[i]
        else:
            skill_link = {'position_id': block.get('position_id', f'pos_{i}')}
        groups.append({
            'skill_link': skill_link,
            'title': block['title'],
            'company': block['company'],
            'employment_type': block.get('employment_type'),
            'duration': block['duration'],
            'location': block['location'],
            'description': block['description']
        })

    return groups


def extract_about_section(nodes: Dict, line_numbers: Dict) -> Optional[str]:
    """Extract the About section text from profile cards above activity."""
    about_text_parts = []
    seen = set()

    about_header_line = None
    for key, node in nodes.items():
        if not isinstance(node, list) or len(node) < 4:
            continue
        props = node[3] if isinstance(node[3], dict) else {}
        text_props = props.get('textProps', {})
        children = text_props.get('children', [])
        if (node[1] in ('h2', '$L20', '$L16') or text_props.get('tagName') == 'h2') and children:
            child_texts = []

            def get_texts(ch):
                if isinstance(ch, list):
                    for item in ch:
                        get_texts(item)
                elif isinstance(ch, str):
                    child_texts.append(ch)

            get_texts(children)
            if any('About' in t for t in child_texts):
                about_header_line = line_numbers.get(key, 0)
                break

    if about_header_line is None:
        return None

    candidate_nodes = []
    for key, node in nodes.items():
        if not isinstance(node, list) or len(node) < 4:
            continue
        line_num = line_numbers.get(key, 0)
        if line_num <= about_header_line:
            continue
        props = node[3] if isinstance(node[3], dict) else {}
        if node[1] in ('$L51', '$L43', '$L17', '$L16', '$Lb', '$L19') and 'textProps' in props:
            text_props = props['textProps']
            children = text_props.get('children', [])
            if children:
                if 'lineClamp' in str(props) or 'expandable_text_block' in str(props):
                    candidate_nodes.append((line_num, key, node))

    candidate_nodes.sort(key=lambda x: x[0])

    for _, key, node in candidate_nodes[:1]:
        props = node[3] if isinstance(node[3], dict) else {}
        text_props = props.get('textProps', {})
        children = text_props.get('children', [])

        def extract_text(ch):
            if isinstance(ch, list):
                for item in ch:
                    extract_text(item)
            elif isinstance(ch, dict):
                if 'children' in ch:
                    extract_text(ch['children'])
                for v in ch.values():
                    extract_text(v)
            elif isinstance(ch, str):
                if ch and not ch.startswith('$') and not ch.startswith('http') and ch not in ('br', '0', '1', '2', 'text-attr-0', 'text-attr-1'):
                    normalized = ch.strip()
                    if normalized and len(normalized) > 3 and normalized not in seen:
                        seen.add(normalized)
                        about_text_parts.append(normalized)

        extract_text(children)

    if about_text_parts:
        text = " ".join(about_text_parts)
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    return None


def _line_numbers_from_content(content: str) -> Dict[str, int]:
    """Rebuild the key -> line-number map alongside parse_rsc_content."""
    line_numbers = {}
    lines = content.strip().split('\n')
    for i, line in enumerate(lines):
        if not line.strip():
            continue
        match = re.match(r'^([0-9a-f]+):(.+)$', line.strip())
        if not match:
            continue
        key, value = match.groups()
        if value.startswith('['):
            line_numbers[key] = i
    return line_numbers


def parse_experience_content(content: str) -> List[Experience]:
    """Parse experiences from a profileCardsExperienceOnly RSC response string."""
    nodes = parse_rsc_content(content)
    line_numbers = _line_numbers_from_content(content)
    content_nodes = find_content_nodes(nodes, line_numbers)
    groups = group_content_by_experience(content_nodes)

    experiences = []
    for g in groups:
        title = (g['title']['text'] if g['title'] else "").strip()
        company_text = (g['company']['text'] if g['company'] else "").strip()
        duration = g['duration']['text'] if g['duration'] else ""
        location = g['location']['text'] if g['location'] else ""
        employment_type = g['employment_type']['text'] if g.get('employment_type') else ""
        description = extract_description_text(g['description']['node']) if g['description'] else ""

        if " · " in company_text and not employment_type:
            parts = company_text.split(" · ")
            if len(parts) == 2:
                company_text = parts[0].strip()
                employment_type = parts[1].strip()

        if title and company_text and title.strip().lower() == company_text.strip().lower():
            continue

        if " · " in company_text:
            company = company_text.split(" · ")[0].strip()
        else:
            company = company_text

        exp = Experience(
            title=title or "Unknown Title",
            company=company or "Unknown Company",
            location=location or None,
            duration=duration or None,
            description=description.strip() or None,
            employment_type=employment_type or None
        )
        experiences.append(exp)

    experiences.sort(key=lambda e: extract_end_date(e.duration), reverse=True)
    return experiences


def parse_about_content(content: str) -> Optional[str]:
    """Parse the About section from a profileCardsAboveActivity RSC response string."""
    nodes = parse_rsc_content(content)
    line_numbers = _line_numbers_from_content(content)
    return extract_about_section(nodes, line_numbers)


# --- File-based entrypoints (kept for local testing / backwards compat) ---

def parse_experience_file(filepath: str) -> List[Experience]:
    with open(filepath, 'r') as f:
        return parse_experience_content(f.read())


def parse_about_file(filepath: str) -> Optional[str]:
    with open(filepath, 'r') as f:
        return parse_about_content(f.read())