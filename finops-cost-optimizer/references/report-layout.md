# Report layout

The generate_report tool builds a self contained HTML file (charts embedded as base64 PNG, no external assets) and writes it to the file store. Pass it the data below.

## Sections

1. Header: title, generation date, the analysis window (30 days), and the data source (CostManagement or the Consumption fallback).
2. Executive summary: total analyzed spend, total estimated monthly savings, savings as a percent of analyzed spend, and the count of findings by priority band.
3. Spend by subscription: a horizontal bar chart of the selected subscriptions by amortized spend.
4. Spend by resource group: a horizontal bar chart of the top resource groups across the selected subscriptions.
5. Savings by dimension: a bar chart of estimated monthly savings grouped by the seven dimensions.
6. Recommendations table: every finding sorted by priority score, with resource, dimension, current, proposed, monthly saving, risk, and priority band.

## Input shape for generate_report

Pass a report_data object with:

- generated_for: a label for the scope, for example the tenant or agent name.
- window_days and data_source.
- totals: analyzed_spend, estimated_monthly_savings, currency.
- subscriptions: a list of objects with name and cost for the selected subscriptions.
- resource_groups: a list of objects with name and cost for the top resource groups.
- savings_by_dimension: a mapping of dimension name to estimated monthly saving.
- findings: a list, each with resource, dimension, current, proposed, monthly_saving, risk, priority_score, and priority_band.

## Accessibility

- Use a colourblind friendly palette.
- Give every chart a descriptive title and alt text.
- Include the underlying numbers in a data table next to each chart so the report does not depend on colour alone.
- Keep text and background contrast at WCAG AA or better.

## Styling and interactivity

- The report uses Tailwind CSS through the Play CDN for a modern look, so it needs internet access when opened to render fully styled. Without internet it falls back to a basic but readable layout, and the charts (embedded as base64) still show.
- Every table is sortable (click a column header to toggle ascending or descending) and filterable (type in the box above the table). This is small embedded JavaScript with no external library.
