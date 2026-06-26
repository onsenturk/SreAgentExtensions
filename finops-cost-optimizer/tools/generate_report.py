"""
generate_report: Build a self contained HTML FinOps report.

Azure SRE Agent Python tool. Renders charts with matplotlib, embeds them as
base64 PNG (no external assets), writes the report to /mnt/data, and returns a
file link. See references/report-layout.md for the input shape.

Heavy imports (matplotlib) are loaded lazily inside the chart helper.
"""

import base64
import html
import io
import os
from datetime import datetime, timezone

OUTPUT_DIR = "/mnt/data"
# Colourblind friendly palette (Okabe and Ito).
PALETTE = ["#0072B2", "#E69F00", "#009E73", "#CC79A7", "#56B4E9", "#D55E00", "#F0E442"]


def _bar_png(labels, values, title, xlabel):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    height = max(2.5, 0.5 * len(labels) + 1.2)
    figure, axes = plt.subplots(figsize=(9, height))
    positions = list(range(len(labels)))
    axes.barh(positions, values, color=PALETTE[0])
    axes.set_yticks(positions)
    axes.set_yticklabels(labels)
    axes.invert_yaxis()
    axes.set_xlabel(xlabel)
    axes.set_title(title)
    for spine in ("top", "right"):
        axes.spines[spine].set_visible(False)
    figure.tight_layout()
    buffer = io.BytesIO()
    figure.savefig(buffer, format="png", dpi=120)
    plt.close(figure)
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def _img(png_b64, alt):
    return (
        f'<img src="data:image/png;base64,{png_b64}" alt="{html.escape(alt)}" '
        'class="w-full h-auto rounded-lg ring-1 ring-slate-100" />'
    )


def _table(headers, rows, table_id, numeric_columns=None):
    numeric_columns = numeric_columns or set()
    head_cells = ""
    for index, header in enumerate(headers):
        is_numeric = "true" if index in numeric_columns else "false"
        head_cells += (
            '<th scope="col" class="px-3 py-2 text-left">'
            f'<button type="button" onclick="sortTable(\'{table_id}\',{index},this)" data-numeric="{is_numeric}" '
            'class="inline-flex items-center gap-1 text-xs font-semibold uppercase tracking-wider text-slate-600 hover:text-slate-900">'
            f'{html.escape(str(header))}<span aria-hidden="true" class="indicator text-sky-600"></span></button></th>'
        )
    body_rows = ""
    for row in rows:
        cells = "".join(
            f'<td class="px-3 py-2 text-sm text-slate-700 align-top">{html.escape(str(cell))}</td>'
            for cell in row
        )
        body_rows += f'<tr class="border-t border-slate-100 hover:bg-slate-50">{cells}</tr>'
    return (
        '<div class="mb-3">'
        f'<input type="search" aria-label="Filter table rows" oninput="filterTable(\'{table_id}\',this.value)" '
        'placeholder="Filter rows..." '
        'class="w-full sm:w-72 rounded-lg border border-slate-300 px-3 py-1.5 text-sm text-slate-700 '
        'placeholder:text-slate-400 focus:border-sky-500 focus:outline-none focus:ring-1 focus:ring-sky-500" /></div>'
        '<div class="overflow-x-auto rounded-lg ring-1 ring-slate-200">'
        f'<table id="{table_id}" class="min-w-full text-left">'
        f'<thead class="bg-slate-50"><tr>{head_cells}</tr></thead>'
        f'<tbody class="bg-white">{body_rows}</tbody></table></div>'
        f'<p class="mt-2 text-xs text-slate-400" id="{table_id}-count"></p>'
    )


CARD = "bg-white rounded-xl shadow-sm ring-1 ring-slate-200 p-5 mb-6"
H2 = "text-lg font-semibold text-slate-800 mb-3"


def _document_head(title):
    return (
        '<!doctype html><html lang="en"><head>'
        '<meta charset="utf-8" />'
        '<meta name="viewport" content="width=device-width, initial-scale=1" />'
        f"<title>{html.escape(title)}</title>"
        '<script src="https://cdn.tailwindcss.com"></script>'
        "<style>"
        "body{font-family:Segoe UI,Arial,sans-serif;background:#f1f5f9;color:#1e293b;margin:0;}"
        "img{max-width:100%;height:auto;}"
        "th,td{padding:6px 10px;text-align:left;}"
        "@media print{.indicator{display:none;}input[type=search]{display:none;}}"
        "</style></head>"
    )


SCRIPT = r"""<script>
function filterTable(id, query) {
  var table = document.getElementById(id);
  if (!table) return;
  var term = query.toLowerCase();
  var rows = table.tBodies[0].rows;
  var shown = 0;
  for (var i = 0; i < rows.length; i++) {
    var match = rows[i].textContent.toLowerCase().indexOf(term) !== -1;
    rows[i].style.display = match ? '' : 'none';
    if (match) shown++;
  }
  var counter = document.getElementById(id + '-count');
  if (counter) counter.textContent = shown + ' of ' + rows.length + ' rows';
}
function sortTable(id, col, btn) {
  var table = document.getElementById(id);
  var tbody = table.tBodies[0];
  var rows = Array.prototype.slice.call(tbody.rows);
  var asc = btn.getAttribute('data-asc') !== 'true';
  btn.setAttribute('data-asc', asc ? 'true' : 'false');
  var indicators = table.querySelectorAll('th .indicator');
  for (var k = 0; k < indicators.length; k++) indicators[k].textContent = '';
  var ind = btn.querySelector('.indicator');
  if (ind) ind.textContent = asc ? ' \u25B2' : ' \u25BC';
  var numeric = btn.getAttribute('data-numeric') === 'true';
  rows.sort(function (a, b) {
    var x = a.cells[col].textContent.trim();
    var y = b.cells[col].textContent.trim();
    if (numeric) {
      var nx = parseFloat(x.replace(/[^0-9.\-]/g, '')) || 0;
      var ny = parseFloat(y.replace(/[^0-9.\-]/g, '')) || 0;
      return asc ? nx - ny : ny - nx;
    }
    return asc ? x.localeCompare(y) : y.localeCompare(x);
  });
  for (var j = 0; j < rows.length; j++) tbody.appendChild(rows[j]);
}
</script>"""


def main(report_data: dict, report_title: str = "Azure FinOps Cost Optimization Report") -> dict:
    """Render the HTML report and return its file link.

    report_data: see references/report-layout.md for the expected shape.
    """
    data = report_data or {}
    totals = data.get("totals", {})
    currency = totals.get("currency", "")
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    analyzed = float(totals.get("analyzed_spend", 0.0) or 0.0)
    savings = float(totals.get("estimated_monthly_savings", 0.0) or 0.0)
    pct = (savings / analyzed * 100.0) if analyzed else 0.0
    bands = {"High": 0, "Medium": 0, "Low": 0}
    for finding in data.get("findings", []):
        band = finding.get("priority_band", "Low")
        bands[band] = bands.get(band, 0) + 1

    counter = {"n": 0}

    def next_id():
        counter["n"] += 1
        return f"tbl{counter['n']}"

    def card(title, inner):
        return f'<section class="{CARD}"><h2 class="{H2}">{html.escape(title)}</h2>{inner}</section>'

    sections = []

    subs = data.get("subscriptions", [])
    if subs:
        labels = [str(item.get("name", "")) for item in subs]
        values = [float(item.get("cost", 0.0) or 0.0) for item in subs]
        png = _bar_png(labels, values, "Spend by subscription (amortized, 30 days)", f"Cost ({currency})")
        table = _table(["Subscription", f"Cost ({currency})"], [[label, f"{value:,.2f}"] for label, value in zip(labels, values)], next_id(), {1})
        sections.append(card("Spend by subscription", _img(png, "Spend by subscription bar chart") + f'<div class="mt-4">{table}</div>'))

    rgs = data.get("resource_groups", [])
    if rgs:
        labels = [str(item.get("name", "")) for item in rgs]
        values = [float(item.get("cost", 0.0) or 0.0) for item in rgs]
        png = _bar_png(labels, values, "Top resource groups by spend (amortized, 30 days)", f"Cost ({currency})")
        table = _table(["Resource group", f"Cost ({currency})"], [[label, f"{value:,.2f}"] for label, value in zip(labels, values)], next_id(), {1})
        sections.append(card("Spend by resource group", _img(png, "Spend by resource group bar chart") + f'<div class="mt-4">{table}</div>'))

    by_dimension = data.get("savings_by_dimension", {})
    if by_dimension:
        labels = list(by_dimension.keys())
        values = [float(by_dimension[key] or 0.0) for key in labels]
        png = _bar_png(labels, values, "Estimated monthly savings by dimension", f"Savings ({currency})")
        table = _table(["Dimension", f"Savings ({currency})"], [[label, f"{value:,.2f}"] for label, value in zip(labels, values)], next_id(), {1})
        sections.append(card("Savings by dimension", _img(png, "Savings by dimension bar chart") + f'<div class="mt-4">{table}</div>'))

    findings = data.get("findings", [])
    if findings:
        rows = []
        for finding in sorted(findings, key=lambda item: item.get("priority_score", 0.0), reverse=True):
            rows.append(
                [
                    finding.get("resource", ""),
                    finding.get("dimension", ""),
                    finding.get("current", ""),
                    finding.get("proposed", ""),
                    f"{float(finding.get('monthly_saving', 0.0) or 0.0):,.2f}",
                    finding.get("risk", ""),
                    finding.get("priority_band", ""),
                ]
            )
        table = _table(
            ["Resource", "Dimension", "Current", "Proposed", f"Monthly saving ({currency})", "Risk", "Priority"],
            rows,
            next_id(),
            {4},
        )
        sections.append(card("Recommendations", table))

    def stat(label, value, accent):
        return (
            '<div class="rounded-xl bg-white p-4 shadow-sm ring-1 ring-slate-200">'
            f'<dt class="text-xs font-medium uppercase tracking-wider text-slate-500">{label}</dt>'
            f'<dd class="mt-1 text-2xl font-semibold {accent}">{value}</dd></div>'
        )

    summary = (
        '<section class="mb-6">'
        f'<h2 class="{H2}">Executive summary</h2>'
        '<dl class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">'
        + stat("Analyzed spend (30 days)", f"{currency} {analyzed:,.0f}", "text-slate-900")
        + stat("Est. monthly savings", f"{currency} {savings:,.0f}", "text-emerald-600")
        + stat("Savings of spend", f"{pct:.1f}%", "text-emerald-600")
        + stat("Findings (H / M / L)", f'{bands.get("High", 0)} / {bands.get("Medium", 0)} / {bands.get("Low", 0)}', "text-slate-900")
        + "</dl></section>"
    )

    header_card = (
        '<header class="rounded-xl bg-gradient-to-r from-sky-600 to-indigo-600 text-white p-6 mb-6 shadow-sm">'
        f'<h1 class="text-2xl font-bold tracking-tight">{html.escape(report_title)}</h1>'
        f'<p class="mt-1 text-sm text-sky-100">Generated {generated} &middot; Window {int(data.get("window_days", 30))} days '
        f'&middot; Scope {html.escape(str(data.get("generated_for", "agent read scope")))} '
        f'&middot; Source {html.escape(str(data.get("data_source", "CostManagement")))}</p></header>'
    )

    footer = (
        '<footer class="mt-2 mb-10 text-xs text-slate-500">'
        'Figures are estimates. Validate each recommendation before acting. '
        'This report is read only and proposes no automatic changes.</footer>'
    )

    document = (
        _document_head(report_title)
        + '<body class="bg-slate-100 text-slate-800"><div class="mx-auto max-w-5xl p-4 sm:p-6">'
        + header_card
        + summary
        + "".join(sections)
        + footer
        + "</div>"
        + SCRIPT
        + "</body></html>"
    )

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    filename = f"finops-report-{stamp}.html"
    path = os.path.join(OUTPUT_DIR, filename)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(document)

    return {
        "report_path": f"/api/files/{filename}",
        "local_path": path,
        "summary": {
            "analyzed_spend": analyzed,
            "estimated_monthly_savings": savings,
            "savings_percent": round(pct, 1),
            "findings_total": len(findings),
            "findings_by_band": bands,
            "currency": currency,
        },
    }


def _cli():
    import argparse
    import json
    import sys

    parser = argparse.ArgumentParser(description="Build a self contained HTML FinOps report.")
    parser.add_argument("--input", type=str, default=None, help="Path to a JSON file with report_data. Reads stdin if omitted.")
    parser.add_argument("--title", type=str, default="Azure FinOps Cost Optimization Report")
    args = parser.parse_args()
    if args.input:
        with open(args.input, "r", encoding="utf-8") as handle:
            report_data = json.load(handle)
    else:
        report_data = json.load(sys.stdin)
    print(json.dumps(main(report_data=report_data, report_title=args.title), indent=2))


if __name__ == "__main__":
    _cli()
