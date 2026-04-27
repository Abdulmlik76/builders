#!/usr/bin/env python3
"""
Render STRATEGY.md to a polished PDF for non-technical stakeholders.

Reads ../STRATEGY.md, converts markdown -> HTML (with tables, fenced code,
and inline Arabic preserved), wraps in a print stylesheet, renders via
weasyprint to ../STRATEGY.pdf.

Re-run any time STRATEGY.md changes:
    python3 tools/render_strategy_pdf.py
"""

from pathlib import Path
import datetime as dt

import markdown
from weasyprint import HTML, CSS

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "STRATEGY.md"
OUT = ROOT / "STRATEGY.pdf"

CSS_TEMPLATE = """
@page {
    size: A4;
    margin: 22mm 20mm 22mm 20mm;
    @bottom-left  { content: "Saudi Market Trends — Strategy"; font-size: 9pt; color: #888; }
    @bottom-right { content: "Page " counter(page) " / " counter(pages); font-size: 9pt; color: #888; }
}
@page :first { @bottom-left { content: ""; } @bottom-right { content: ""; } }

html, body {
    font-family: "Inter", "Helvetica Neue", "Arial", "Noto Sans Arabic", sans-serif;
    font-size: 10.5pt;
    line-height: 1.55;
    color: #1d1f23;
}

.cover {
    page-break-after: always;
    text-align: center;
    padding-top: 70mm;
}
.cover h1 { font-size: 30pt; margin-bottom: 6mm; color: #0a2540; }
.cover .subtitle { font-size: 13pt; color: #4a5568; margin-bottom: 18mm; }
.cover .meta { font-size: 10pt; color: #888; }
.cover .pill {
    display: inline-block; padding: 2mm 5mm; border-radius: 18pt;
    background: #eef3fb; color: #0a2540; font-size: 10pt; letter-spacing: 0.5pt;
}

h1 { font-size: 20pt; color: #0a2540; margin-top: 8mm; margin-bottom: 4mm;
     border-bottom: 1pt solid #e3e7ee; padding-bottom: 2mm; }
h2 { font-size: 15pt; color: #0a2540; margin-top: 9mm; margin-bottom: 3mm; }
h3 { font-size: 12pt; color: #1f3658; margin-top: 6mm; margin-bottom: 2mm; }
h4 { font-size: 11pt; color: #1f3658; margin-top: 4mm; margin-bottom: 1mm; }

p { margin: 2mm 0; }
ul, ol { margin: 2mm 0 2mm 5mm; }
li { margin: 1mm 0; }

a { color: #1559b8; text-decoration: none; }
strong { color: #0a2540; }
em { color: #2a3b55; }

blockquote {
    margin: 3mm 0;
    padding: 2mm 4mm;
    border-left: 2pt solid #1559b8;
    background: #f5f8fc;
    color: #2a3b55;
    font-size: 10pt;
}

hr { border: 0; border-top: 1pt dashed #cfd6e3; margin: 6mm 0; }

table {
    border-collapse: collapse;
    width: 100%;
    margin: 3mm 0;
    font-size: 9.2pt;
    page-break-inside: avoid;
}
thead { background: #0a2540; color: white; }
th, td {
    border: 0.5pt solid #d8dde6;
    padding: 1.5mm 2mm;
    vertical-align: top;
    text-align: left;
}
tbody tr:nth-child(even) { background: #f7f9fc; }

code {
    font-family: "JetBrains Mono", "Menlo", "Consolas", monospace;
    font-size: 9pt;
    background: #f0f3f9;
    padding: 0.5mm 1mm;
    border-radius: 2pt;
    color: #0a2540;
}
pre code { display: block; padding: 2mm 3mm; line-height: 1.4; }

/* Arabic snippets render correctly inline (no special class needed). */

/* Avoid awkward breaks */
h1, h2, h3, h4 { page-break-after: avoid; }
table, blockquote { page-break-inside: avoid; }

/* Section dividers stay clean */
hr + h2 { margin-top: 4mm; }
"""

COVER = """
<div class="cover">
  <div class="pill">SAUDI MARKET TRENDS PLATFORM</div>
  <h1>Strategy &amp; Hypotheses</h1>
  <div class="subtitle">Market positioning, advantages, and the open questions we plan to answer</div>
  <div class="meta">Generated {date} &middot; Internal stakeholder document</div>
</div>
"""


def render() -> None:
    md_text = SRC.read_text(encoding="utf-8")

    # Strip the first H1 because the cover page provides the title
    lines = md_text.splitlines()
    if lines and lines[0].startswith("# "):
        lines = lines[1:]

    # Stakeholder PDF: keep only sections 1-5. Section 6 onward is technical
    # (architecture implications) and lives in the full STRATEGY.md alongside
    # ARCHITECTURE.md for the engineering audience.
    cut_idx = next(
        (i for i, line in enumerate(lines) if line.startswith("## 6.")),
        None,
    )
    if cut_idx is not None:
        # Drop a trailing `---` rule if present immediately before section 6
        while cut_idx > 0 and lines[cut_idx - 1].strip() in ("", "---"):
            cut_idx -= 1
        lines = lines[:cut_idx]

    md_text = "\n".join(lines)

    html_body = markdown.markdown(
        md_text,
        extensions=["tables", "fenced_code", "sane_lists", "attr_list", "smarty"],
    )

    cover = COVER.format(date=dt.date.today().strftime("%B %Y"))
    full_html = f"""<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><title>Strategy &amp; Hypotheses</title></head>
<body>
{cover}
{html_body}
</body>
</html>"""

    HTML(string=full_html, base_url=str(ROOT)).write_pdf(
        str(OUT),
        stylesheets=[CSS(string=CSS_TEMPLATE)],
    )
    size_kb = OUT.stat().st_size // 1024
    print(f"Wrote {OUT.relative_to(ROOT)}  ({size_kb} KB)")


if __name__ == "__main__":
    render()
