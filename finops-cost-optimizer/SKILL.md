---
name: finops-cost-optimizer
description: Use when the user asks for a FinOps review, Azure cost optimization, cost savings, reducing spend, rightsizing, or "where is my Azure money going". Ranks the subscriptions and resource groups the agent can read by spend, detects waste across seven dimensions, ranks recommendations by estimated savings, and produces a self contained HTML cost optimization report.
tools:
  - RunAzCliReadCommands
  - RunInTerminal
  - SaveFileToBlob
---

# FinOps Cost Optimizer

This skill runs a FinOps cost optimization review across the Azure subscriptions and resource groups this agent is allowed to read. It narrows scope by spend, finds waste across seven dimensions, ranks the findings by savings, and produces an HTML report as the primary output.

## When to use this skill

Use this skill when the user asks to:

- Review or reduce Azure cost, find savings, or run a FinOps assessment.
- Understand where spend is concentrated across subscriptions or resource groups.
- Get cost optimization recommendations beyond raw Azure Advisor output.

## Operating principles

- Read only. This skill never changes or deletes resources. It proposes recommendations for a human to review.
- Default Reader scope. It analyzes only the subscriptions and resource groups this agent can already read. It does not require any extra role grant. See references/permissions-and-scope.md.
- Evidence first. Every recommendation carries the evidence behind it, an estimated monthly saving, and a risk rating. Never recommend a destructive action as the default.

## Workflow

The three Python helpers (tools/cost_rank.py, tools/commitment_recommendations.py, tools/generate_report.py) are bundled with this skill. Run them with the RunInTerminal tool using the Python in the agent runtime, which already has azure-identity, requests, pandas, and matplotlib. They authenticate to Azure with the agent managed identity. Follow these four phases in order.

### Phase 1: Narrow scope by spend

1. Run the helper with RunInTerminal: python tools/cost_rank.py. It queries Azure Cost Management at subscription scope for amortized spend over the last 30 days, groups by resource group, and applies the ranking rules in references/ranking-method.md.
2. It returns the ranked subscriptions, the selected top decile (with a floor so small tenants still return results), and for each selected subscription the ranked resource groups with their own selected top decile.
3. If the helper reports that it used the Consumption fallback, tell the user that cost data came from usage records because the Cost Management query was not available under the current permissions.

### Phase 2: Detect waste on the narrowed scope

For each selected subscription and resource group, work through every dimension in references/checks-catalog.md:

1. Azure Advisor cost baseline.
2. Orphaned resources.
3. Commitment coverage. Run python tools/commitment_recommendations.py --subscriptions <selected ids> with RunInTerminal for reservation and savings plan recommendations.
4. Idle or underused resources, using Azure Monitor metrics over a 30 day window.
5. Storage optimization.
6. Log Analytics optimization.
7. Dev and test scheduling.

Use the RunAzCliReadCommands tool to run the read only Azure CLI commands listed in the catalog. Record a finding for each opportunity with: resource id, dimension, current configuration, proposed change, estimated monthly saving, risk rating, and the supporting evidence.

### Phase 3: Rank findings by savings

Score every finding with the priority formula in references/ranking-method.md, then sort the findings from highest to lowest priority. Spend chose where to look. Savings decides what to fix first.

### Phase 4: Produce the report

1. Assemble the data described in references/report-layout.md.
2. Run python tools/generate_report.py with RunInTerminal, passing the assembled report_data as JSON on standard input. It writes a self contained HTML report to /mnt/data and returns the path. If the user wants a shareable link, store the file with the SaveFileToBlob tool.
3. Present the report to the user, followed by a short inline summary: total analyzed spend, total estimated monthly savings, the count of findings by priority, and the top three recommendations.

## Optional follow up

Only if the user asks for it, file tracking issues from the findings using references/issues-optional.md. This is off by default.

## Expected output

- Primary: a self contained HTML report delivered as a file link.
- Inline: a short summary with total spend analyzed, total estimated monthly savings, findings by priority, and the top three recommendations.
- Every recommendation includes evidence, an estimated monthly saving, and a risk rating.
