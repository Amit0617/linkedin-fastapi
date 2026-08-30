"""Shared helpers for parsing LinkedIn's RSC ("React Server Components")
action-endpoint responses.

The responses look like a series of lines:

    a:["$","div",null,{...}]
    b:I["chunk-id",[],"default"]
    c:["$","p",null,{"children":["some text"]}]
    ...

Each line is `<hex-id>:<json-or-import-directive>`. Real content lines start
with `[` and are valid JSON; `I[...]` lines are webpack import directives we
don't care about. Elements reference each other by id via strings shaped
like `"$L<hex-id>"`.
"""
import json
import re
from typing import Any, Dict


def parse_rsc_content(content: str) -> Dict[str, Any]:
    """Parse raw RSC response text into a dict of nodes keyed by hex id."""
    lines = content.strip().split('\n')
    nodes: Dict[str, Any] = {}

    for line in lines:
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
                nodes[key] = json.loads(value)
            except json.JSONDecodeError:
                pass

    return nodes


def parse_rsc_file(filepath: str) -> Dict[str, Any]:
    """Convenience wrapper: parse an RSC response saved on disk."""
    with open(filepath, 'r') as f:
        content = f.read()
    return parse_rsc_content(content)


def extract_plain_text(children: Any) -> str:
    """Flatten a 'children' structure down to its plain-text content."""
    texts = []

    def rec(c):
        if isinstance(c, list):
            for x in c:
                rec(x)
        elif isinstance(c, str):
            if c and not c.startswith('$'):
                texts.append(c)

    rec(children)
    return ' '.join(t.strip() for t in texts if t.strip()).strip()
