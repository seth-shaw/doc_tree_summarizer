"""Tests for safe HTML report rendering."""

from bs4 import BeautifulSoup

from summarizer.output.html import render


def report(tmp_path, summary, **attributes):
    """Render a report node and return its parsed HTML."""
    destination = tmp_path / 'report.html'
    node = {'type': 'file', 'name': 'notes.md', 'summary': summary, **attributes}
    render(node, destination)
    return BeautifulSoup(destination.read_text(), 'html.parser')


def test_summary_markdown(tmp_path):
    """Verify Markdown summary content is rendered."""
    page = report(tmp_path, '''## Findings

**Important** and *uncertain* with `inline code`.

- First
- Second

1. Ordered
2. List

> Quoted finding

| Topic | Result |
| --- | --- |
| OCR | Good |

```python
print("<example>")
```

[Source](https://example.com)
''')
    summary = page.select_one('.summary')
    assert summary.h2.text == 'Findings'
    assert summary.strong.text == 'Important'
    assert summary.em.text == 'uncertain'
    assert summary.code.text == 'inline code'
    assert [item.text for item in summary.select('ul li')] == ['First', 'Second']
    assert len(summary.select('ol li')) == 2
    assert summary.blockquote is not None
    assert summary.table.td.text == 'OCR'
    assert summary.pre.code.text == 'print("<example>")\n'
    assert summary.a['href'] == 'https://example.com'


def test_untrusted_markup_and_metadata_are_escaped(tmp_path):
    """Verify untrusted content is safely escaped."""
    page = report(tmp_path, '''<script>alert(1)</script>
<img src="https://example.com/tracker" onerror="alert(1)">
[click](javascript:alert%281%29)
[data](data:text/html,payload)
![remote image](https://example.com/tracker.png)
''', name='<img src=x onerror=alert(1)>', warnings=['<script>warning</script>'])
    assert not page.select('script, img, iframe')
    assert not page.select('[onerror]')
    assert all(not link.get('href', '').startswith(('javascript:', 'data:'))
               for link in page.select('a'))
    assert '<script>alert(1)</script>' in page.select_one('.summary').text
    assert '<img src=x onerror=alert(1)>' in page.summary.text
    assert page.select_one('.warning').text == '<script>warning</script>'


def test_directory_and_file_summaries_both_render_markdown(tmp_path):
    """Verify nested file and directory summaries render."""
    page = report(tmp_path, '**Directory**', type='directory', children=[
        {'type': 'file', 'name': 'child.txt', 'summary': '*File*'},
    ])
    assert page.select_one('.summary strong').text == 'Directory'
    assert page.select_one('.children .summary em').text == 'File'


def test_plain_text_and_errors(tmp_path):
    """Verify plain text and failed summaries render correctly."""
    page = report(tmp_path, 'First line\nSecond line & <literal>')
    assert page.select_one('.summary br') is not None
    assert 'Second line & <literal>' in page.select_one('.summary').text
    page = report(tmp_path, '**Error**: <missing>\nRetry', status='failed')
    error = page.select_one('.summary.error')
    assert error.text == '**Error**: <missing>\nRetry'
    assert error.strong is None
