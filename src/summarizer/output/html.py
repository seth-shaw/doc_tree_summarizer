"""Render document summaries as a standalone HTML report."""

import html
from pathlib import Path

from markdown_it import MarkdownIt

# Model output is untrusted. Escape raw HTML and prevent embedded remote assets.
MARKDOWN = MarkdownIt('js-default', {'breaks': True}).disable('image')


def _format_size(size: int) -> str:
    """Format a byte count using a readable unit."""
    if size < 1000:
        return f'{size:,} bytes'
    value = float(size)
    for unit in ('KB', 'MB', 'GB', 'TB'):
        value /= 1000
        if value < 1000 or unit == 'TB':
            return f'{value:.1f} {unit}'
    return f'{value:.1f} TB'


STYLE = '''
:root {
  color-scheme: light dark;
  font-family: system-ui, -apple-system, sans-serif;
  line-height: 1.5;
}
body { max-width: 1100px; margin: 2rem auto; padding: 0 1rem; }
header { display: flex; align-items: center; gap: 1rem; flex-wrap: wrap; }
button { padding: .45rem .8rem; cursor: pointer; }
details {
  border-left: 2px solid #8c969e;
  margin: .7rem 0 .7rem .5rem;
  padding: .35rem 0 .35rem 1rem;
}
summary { cursor: pointer; font-weight: 650; }
.summary { margin: .65rem 0 1rem; overflow-wrap: anywhere; }
.summary > :first-child { margin-top: 0; }
.summary > :last-child { margin-bottom: 0; }
.summary pre { white-space: pre-wrap; overflow-wrap: anywhere; padding: .65rem; background: #8882; }
.summary table { border-collapse: collapse; display: block; overflow-x: auto; }
.summary th, .summary td { border: 1px solid #8c969e; padding: .3rem .6rem; text-align: left; }
.summary blockquote { border-left: 3px solid #8c969e; margin-left: 0; padding-left: 1rem; }
.summary.error { white-space: pre-wrap; }
.meta { font-size: .85rem; opacity: .7; }
.error { color: #b34a4a; }
.warning { color: #956b11; }
.children { margin-left: .3rem; }
'''


def _label(node: dict) -> str:
    """Build escaped summary metadata for a report node."""
    title = html.escape(node['name'])
    kind = node['type']
    status = node.get('status', 'ok')
    image_kind = node.get('image_kind')
    image_label = f', image: {html.escape(image_kind)}' if image_kind else ''
    directory_stats = ''
    if kind == 'directory' and 'file_count' in node:
        modified_range = node.get('modified_range')
        if modified_range:
            date_range = f'{html.escape(modified_range[0])} / {html.escape(modified_range[1])}'
            dates = f', modified {date_range}'
        else:
            dates = ', no file dates'
        size = _format_size(node['size_bytes'])
        directory_stats = f', {node["file_count"]} files, {size}{dates}'
    file_metadata = ''
    if kind == 'file' and 'size_bytes' in node:
        modified_date = html.escape(node['modified_date'])
        sample_status = ', skipped by sampling' if node.get('sampled_out') else ''
        file_size = _format_size(node['size_bytes'])
        file_metadata = f', {file_size}, modified {modified_date}{sample_status}'
    return (
        f'{title} <span class="meta">'
        f'({kind}, {status}{image_label}{directory_stats}{file_metadata})</span>')


def _node(node: dict) -> str:
    """Render one report node and all of its descendants."""
    text = node.get('summary', '')
    is_ok = node.get('status', 'ok') == 'ok'
    message = MARKDOWN.render(text) if is_ok else html.escape(text)
    error_class = '' if is_ok else ' error'
    summary_html = f'<div class="summary{error_class}">{message}</div>' if text else ''
    notes = ''.join(
        f'<p class="warning">{html.escape(note)}</p>' for note in node.get('warnings', []))
    label = _label(node)
    children = ''.join(_node(child) for child in node.get('children', []))
    return (
        f'<details><summary>{label}</summary>{summary_html}{notes}'
        f'<div class="children">{children}</div></details>')

def render(root: dict, destination: Path, sample: int = 100):
    """Write a complete standalone HTML summary report."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    sample_note = f'<p class="meta">Sample level: {sample}%</p>' if sample != 100 else ''
    page = ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>Local AI Document Summaries</title><style>' + STYLE + '</style></head><body>'
            '<header><h1>Document summaries</h1>'
            '<button onclick="document.querySelectorAll(\'details\').forEach(x=>x.open=true)">'
            'Expand all</button>'
            '<button onclick="document.querySelectorAll(\'details\').forEach(x=>x.open=false)">'
            'Collapse all</button></header>'
            '<p class="meta">Generated locally. Summaries may contain errors; '
            'verify against source documents.</p>'
            + sample_note
            + _node(root) + '</body></html>')
    temp = destination.with_name(destination.name + '.tmp')
    temp.write_text(page, encoding='utf-8')
    temp.replace(destination)
