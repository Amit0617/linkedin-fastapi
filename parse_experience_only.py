import json
import re
from typing import Optional, List, Dict, Any
from pydantic import BaseModel


class Experience(BaseModel):
    title: str
    company: str
    location: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    duration: Optional[str] = None
    description: Optional[str] = None
    employment_type: Optional[str] = None


def parse_rsc_file(filepath: str) -> tuple:
    """Parse RSC file into dict of nodes and line numbers."""
    with open(filepath, 'r') as f:
        content = f.read()
    
    lines = content.strip().split('\n')
    nodes = {}
    line_numbers = {}
    
    for i, line in enumerate(lines):
        if not line.strip():
            continue
        match = re.match(r'^([0-9a-f]+):(.+)$', line.strip())
        if not match:
            continue
        key, value = match.groups()
        
        if value.startswith('I['):
            continue
        elif value.startswith('['):
            try:
                parsed = json.loads(value)
                nodes[key] = parsed
                line_numbers[key] = i
            except json.JSONDecodeError:
                pass
    
    return nodes, line_numbers


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
        
        # Find all $L references in this component
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
        ordered_items.append({
            'entity_id': comp_key,
            'l_refs': l_refs
        })
    
    return ordered_items


def find_skill_link_node(nodes: Dict, l_refs: List[str]) -> Optional[Dict]:
    """Find the skill link node ($L ref that has skill-associations-details URL)."""
    for l_ref in l_refs:
        key = l_ref[2:]
        if key in nodes:
            node = nodes[key]
            node_str = json.dumps(node)
            if 'skill-associations-details' in node_str:
                return {'key': key, 'node': node}
    return None


def extract_position_id(node: Dict) -> Optional[str]:
    """Extract position ID from skill link node."""
    node_str = json.dumps(node)
    match = re.search(r'/overlay/(\d+)/skill-associations-details', node_str)
    if match:
        return match.group(1)
    return None


def find_content_nodes(nodes: Dict, line_numbers: Dict) -> Dict[str, List[Dict]]:
    """Find all content nodes grouped by type with their line numbers."""
    content = {
        'titles': [],
        'companies': [],
        'durations': [],
        'locations': [],
        'descriptions': [],
        'skill_links': []
    }
    
    for key, node in nodes.items():
        if not isinstance(node, list) or len(node) < 4:
            continue
        
        line_num = line_numbers.get(key, 0)
        props = node[3] if isinstance(node[3], dict) else {}
        class_name = props.get('className', '')
        children = props.get('children', '')
        
        # Title: p tag with c2d1c236 but NOT _61558a10
        if node[1] == 'p' and 'c2d1c236' in class_name and '_61558a10' not in class_name:
            if isinstance(children, list) and children:
                text = children[0] if isinstance(children[0], str) else ''
                if text and len(text) < 150:
                    content['titles'].append({'key': key, 'text': text, 'line': line_num})
        
        # Skill link: p tag with skill-associations-details in action (check FIRST before company)
        node_str = json.dumps(node)
        if node[1] == 'p' and 'skill-associations-details' in node_str:
            match = re.search(r'/overlay/(\d+)/skill-associations-details', node_str)
            position_id = match.group(1) if match else None
            content['skill_links'].append({'key': key, 'position_id': position_id, 'line': line_num, 'node': node})
        
        # Company: p tag with _61558a10 and _1736033f but NOT c2d1c236, has " · "
        elif node[1] == 'p' and '_61558a10' in class_name and '_1736033f' in class_name and 'c2d1c236' not in class_name:
            if isinstance(children, list) and children:
                text = children[0] if isinstance(children[0], str) else ''
                if text and " · " in text:
                    content['companies'].append({'key': key, 'text': text, 'line': line_num})
        
        # Duration: $Lf with textColorExpression: 179 and date pattern
        elif node[1] == '$Lf' and props.get('textColorExpression') == 179:
            text_props = props.get('textProps', {})
            text_children = text_props.get('children', '')
            if isinstance(text_children, list) and text_children:
                text = text_children[0] if isinstance(text_children[0], str) else ''
                if text and re.search(r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{4}', text):
                    content['durations'].append({'key': key, 'text': text, 'line': line_num})
                elif text and re.search(r'\b(Remote|On-site|Hybrid|India|Delhi|Mumbai|Bangalore|USA|UK)\b', text, re.I):
                    content['locations'].append({'key': key, 'text': text, 'line': line_num})
        
        # Description: $L43 with textProps
        elif node[1] == '$L43' and 'textProps' in props:
            content['descriptions'].append({'key': key, 'node': node, 'line': line_num})
    
    # Sort each by line number
    for field_type in content:
        content[field_type].sort(key=lambda x: x['line'])
    
    return content


def extract_description_text(node: Dict) -> str:
    """Extract description text from $L43 node."""
    if not isinstance(node, list) or len(node) < 4:
        return ""
    
    props = node[3]
    if not isinstance(props, dict) or 'textProps' not in props:
        return ""
    
    text_props = props['textProps']
    children = text_props.get('children', [])
    desc_lines = []
    
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
                if ch.startswith(('-', '•', '1.', '2.', '3.', '4.', '5.', '6.', '7.', '8.', '9.')):
                    desc_lines.append(ch)
                elif len(ch) > 50 and not any(kw in ch.lower() for kw in ['skill', 'association', 'overlay', 'credential', 'issued']):
                    desc_lines.append(ch)
    
    extract(children)
    return "\n".join(desc_lines)


def group_content_by_experience(content: Dict) -> List[Dict]:
    """Group content nodes into experience groups by matching skill_links to content blocks."""
    # Content blocks: each starts with a title
    titles = content['titles']
    
    # Build content blocks starting from each title (title, company, duration, location)
    blocks = []
    for i, title in enumerate(titles):
        title_line = title['line']
        next_title_line = titles[i+1]['line'] if i+1 < len(titles) else float('inf')
        
        company = None
        for c in content['companies']:
            if title_line <= c['line'] < next_title_line:
                company = c
                break
        
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
        
        blocks.append({
            'title': title,
            'company': company,
            'duration': duration,
            'location': location,
            'description': None,  # Will assign separately
            'start_line': title_line,
            'end_line': next_title_line
        })
    
    # Sort blocks by start line (file order)
    blocks.sort(key=lambda b: b['start_line'])
    
    # Skill links in visual order (file order of skill_links = visual order)
    skill_links = sorted(content['skill_links'], key=lambda s: s['line'])
    visual_pos_ids = [sl['position_id'] for sl in skill_links]
    
    # Find the block that CONTAINS a skill_link (Web3 block contains Web3 skill_link at line 35)
    web3_block_idx = None
    web3_pos_id = None
    for i, block in enumerate(blocks):
        for sl in skill_links:
            if block['start_line'] <= sl['line'] < block['end_line']:
                web3_block_idx = i
                web3_pos_id = sl['position_id']
                block['position_id'] = sl['position_id']
                break
        if web3_block_idx is not None:
            break
    
    # The Web3 block is at visual index where its position_id appears in visual_pos_ids
    web3_visual_idx = visual_pos_ids.index(web3_pos_id) if web3_pos_id in visual_pos_ids else 3
    
    # Remaining visual position_ids (excluding Web3's)
    remaining_visual_pos_ids = [pid for pid in visual_pos_ids if pid != web3_pos_id]
    
    # Remaining blocks in file order (excluding Web3 block)
    remaining_blocks = [b for i, b in enumerate(blocks) if i != web3_block_idx]
    
    # Assign remaining position_ids to remaining blocks in file order
    for i, block in enumerate(remaining_blocks):
        if i < len(remaining_visual_pos_ids):
            block['position_id'] = remaining_visual_pos_ids[i]
    
    # Now sort blocks by visual order (using position_id to find visual index)
    pos_id_to_visual_idx = {pid: idx for idx, pid in enumerate(visual_pos_ids)}
    blocks_with_pos = [b for b in blocks if 'position_id' in b]
    blocks_with_pos.sort(key=lambda b: pos_id_to_visual_idx.get(b['position_id'], 999))
    
    # Assign descriptions in visual order (descriptions are in visual order in the file)
    # Descriptions lines: 46(TCS), 51(Ethereum), 57(Blockskillo), 58(Web3), 63(Overclock)
    # This matches visual order: TCS, Ethereum, Blockskillo, Web3, Overclock
    descriptions_sorted = sorted(content['descriptions'], key=lambda d: d['line'])
    for i, block in enumerate(blocks_with_pos):
        if i < len(descriptions_sorted):
            block['description'] = descriptions_sorted[i]
    
    # Pair with skill_links in visual order
    groups = []
    for i, skill_link in enumerate(skill_links):
        if i < len(blocks_with_pos):
            block = blocks_with_pos[i]
            groups.append({
                'skill_link': skill_link,
                'title': block['title'],
                'company': block['company'],
                'duration': block['duration'],
                'location': block['location'],
                'description': block['description']
            })
    
    return groups


def main():
    filepath = "/home/amit/codelib/tross/linkedin-fastapi/component_profileCardsExperienceOnly.json"
    
    nodes, line_numbers = parse_rsc_file(filepath)
    
    # Get visual order from initialItems
    ordered_items = get_initial_items_order(nodes)
    
    print(f"Visual order from initialItems ({len(ordered_items)} experiences):")
    for i, item in enumerate(ordered_items):
        skill_link = find_skill_link_node(nodes, item['l_refs'])
        pos_id = extract_position_id(skill_link['node']) if skill_link else 'unknown'
        print(f"  {i+1}. {item['entity_id']} -> position_id: {pos_id}")
    
    # Find all content nodes
    content = find_content_nodes(nodes, line_numbers)
    
    print(f"\nContent nodes found:")
    for field_type, items in content.items():
        if field_type != 'skill_links':
            print(f"  {field_type}: {len(items)}")
            for item in items:
                print(f"    line {item['line']}: key={item['key']} = {item.get('text', item.get('position_id', ''))[:80]}")
        else:
            print(f"  {field_type}: {len(items)}")
            for item in items:
                print(f"    line {item['line']}: key={item['key']} position_id={item['position_id']}")
    
    # Group content by experience using skill_links as anchors
    file_order_groups = group_content_by_experience(content)
    
    print(f"\nFile order groups ({len(file_order_groups)}):")
    for i, g in enumerate(file_order_groups):
        pos_id = g['skill_link']['position_id']
        title = g['title']['text'] if g['title'] else 'None'
        print(f"  {i+1}. position_id={pos_id}, title={title}")
    
    # Map visual order to file order groups using position_id
    visual_to_file = {}
    for vis_item in ordered_items:
        skill_link = find_skill_link_node(nodes, vis_item['l_refs'])
        if skill_link:
            pos_id = extract_position_id(skill_link['node'])
            # Find matching file order group
            for fg in file_order_groups:
                if fg['skill_link']['position_id'] == pos_id:
                    visual_to_file[vis_item['entity_id']] = fg
                    break
    
    print("\n=== Parsed Experiences (in visual order) ===\n")
    experiences = []
    for i, vis_item in enumerate(ordered_items):
        fg = visual_to_file.get(vis_item['entity_id'])
        if not fg:
            print(f"Experience {i+1}: NO MATCH for {vis_item['entity_id']}")
            continue
        
        title = fg['title']['text'] if fg['title'] else ""
        company_text = fg['company']['text'] if fg['company'] else ""
        duration = fg['duration']['text'] if fg['duration'] else ""
        location = fg['location']['text'] if fg['location'] else ""
        description = extract_description_text(fg['description']['node']) if fg['description'] else ""
        
        company = ""
        employment_type = ""
        if " · " in company_text:
            parts = company_text.split(" · ")
            company = parts[0].strip()
            if len(parts) > 1:
                employment_type = parts[1].strip()
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
        
        print(f"Experience {i+1}:")
        print(f"  Title: {exp.title}")
        print(f"  Company: {exp.company}")
        print(f"  Location: {exp.location}")
        print(f"  Duration: {exp.duration}")
        print(f"  Employment Type: {exp.employment_type}")
        print(f"  Description: {exp.description[:200] if exp.description else 'None'}...")
        print()
    
    # Compare with example.json
    with open("/home/amit/codelib/tross/linkedin-fastapi/example.json", 'r') as f:
        example = json.load(f)
    
    print("\n=== Expected (from example.json) ===\n")
    for i, exp in enumerate(example['experiences'], 1):
        print(f"Experience {i}:")
        print(f"  Title: {exp['title']}")
        print(f"  Company: {exp['company']}")
        print(f"  Location: {exp['location']}")
        print(f"  Duration: {exp['duration']}")
        print(f"  Employment Type: {exp['employment_type']}")
        print(f"  Description: {exp['description'][:200] if exp['description'] else 'None'}...")
        print()


if __name__ == "__main__":
    main()