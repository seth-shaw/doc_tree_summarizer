import html
from pathlib import Path

from markdown_it import MarkdownIt

# Model output is untrusted. Escape raw HTML and prevent embedded remote assets.
MARKDOWN = MarkdownIt('js-default', {'breaks': True}).disable('image')

def _format_size(size: int) -> str:
    if size < 1000:
        return f'{size:,} bytes'
    value = float(size)
    for unit in ('KB', 'MB', 'GB', 'TB'):
        value /= 1000
        if value < 1000 or unit == 'TB':
            return f'{value:.1f} {unit}'

STYLE = '''
:root {color-scheme:light dark;font-family:system-ui,-apple-system,sans-serif;line-height:1.5}
body {max-width:1100px;margin:2rem auto;padding:0 1rem} header{display:flex;align-items:center;gap:1rem;flex-wrap:wrap}
button {padding:.45rem .8rem;cursor:pointer} details {border-left:2px solid #8c969e;margin:.7rem 0 .7rem .5rem;padding:.35rem 0 .35rem 1rem}
summary {cursor:pointer;font-weight:650} .summary {margin:.65rem 0 1rem;overflow-wrap:anywhere}
.summary > :first-child {margin-top:0}.summary > :last-child {margin-bottom:0}
.summary pre {white-space:pre-wrap;overflow-wrap:anywhere;padding:.65rem;background:#8882}
.summary table {border-collapse:collapse;display:block;overflow-x:auto}
.summary th,.summary td {border:1px solid #8c969e;padding:.3rem .6rem;text-align:left}
.summary blockquote {border-left:3px solid #8c969e;margin-left:0;padding-left:1rem}
.summary.error {white-space:pre-wrap}
.meta {font-size:.85rem;opacity:.7}.error {color:#b34a4a}.warning{color:#956b11} .children {margin-left:.3rem}
'''

def _node(node: dict) -> str:
    title = html.escape(node['name'])
    kind = node['type']
    status = node.get('status', 'ok')
    text = node.get('summary', '')
    message = MARKDOWN.render(text) if status == 'ok' else html.escape(text)
    notes = ''.join(f'<p class="warning">{html.escape(note)}</p>' for note in node.get('warnings', []))
    image_kind = node.get('image_kind')
    image_label = f', image: {html.escape(image_kind)}' if image_kind else ''
    directory_stats = ''
    if kind == 'directory' and 'file_count' in node:
        modified_range = node.get('modified_range')
        dates = f', modified {html.escape(modified_range[0])} – {html.escape(modified_range[1])}' if modified_range else ', no file dates'
        directory_stats = (f', {node["file_count"]} files, {_format_size(node["size_bytes"])}{dates}')
    file_metadata = ''
    if kind == 'file' and 'size_bytes' in node:
        modified_date = html.escape(node['modified_date'])
        file_metadata = f', {_format_size(node["size_bytes"])}, modified {modified_date}'
    label = f'{title} <span class="meta">({kind}, {status}{image_label}{directory_stats}{file_metadata})</span>'
    children = ''.join(_node(child) for child in node.get('children', []))
    error_class = ' error' if status != 'ok' else ''
    return f'<details><summary>{label}</summary><div class="summary{error_class}">{message}</div>{notes}<div class="children">{children}</div></details>'

def render(root: dict, destination: Path):
    destination.parent.mkdir(parents=True, exist_ok=True)
    page = ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>Local AI Document Summaries</title><style>' + STYLE + '</style></head><body>'
            '<header><h1>Document summaries</h1><button onclick="document.querySelectorAll(\'details\').forEach(x=>x.open=true)">Expand all</button>'
            '<button onclick="document.querySelectorAll(\'details\').forEach(x=>x.open=false)">Collapse all</button></header>'
            '<p class="meta">Generated locally. Summaries may contain errors; verify against source documents.</p>'
            + _node(root) + '</body></html>')
    temp = destination.with_name(destination.name + '.tmp')
    temp.write_text(page, encoding='utf-8')
    temp.replace(destination)
