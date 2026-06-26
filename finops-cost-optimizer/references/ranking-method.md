# Ranking method

The skill ranks in two phases. Spend decides where to look. Savings decides what to fix first.

## Phase 1: Narrow scope by spend

Cost basis:

- Metric: amortized cost. Reservation and savings plan purchases are spread across the benefit period, not shown as a lump on the purchase day.
- Window: the last 30 days.
- Grouping: by subscription, then by resource group within each selected subscription.

Selection rule (floor and cap) for a set of N items:

- selected = min(N, max(minimum, ceil(N * top_percent / 100)))
- Subscriptions: top_percent = 10, minimum = 3.
- Resource groups: top_percent = 10, minimum = 5.

This keeps the top decile for large estates while guaranteeing a usable set for small ones. Examples:

- 3 subscriptions: select 3 (the floor applies).
- 6 subscriptions: select 3.
- 200 subscriptions: select 20.
- 6 resource groups: select 5.

The cost_rank tool applies this rule and returns the ranked items with a selected flag.

## Phase 2: Rank findings by savings

After waste detection, score every finding:

Priority Score = (Value x Estimated Monthly Savings) / (Risk x Implementation Days)

- Value: 1 to 10, how strategically useful the change is.
- Risk: 1 to 10, the chance of a negative effect. Higher risk lowers the score.
- Implementation Days: estimated effort in days, minimum 0.5.

Bands:

- High priority: score above 20.
- Medium priority: score 5 to 20.
- Low priority: score below 5.

Sort findings by priority score, highest first.

## What cost_rank returns

A JSON object with:

- lookback_days and the cost currency.
- data_source: CostManagement or Consumption (the fallback).
- subscriptions: every visible subscription with id, name, total_cost, rank, and selected.
- selected_subscriptions: the ids chosen in phase 1.
- resource_groups: for each selected subscription, the ranked resource groups with name, cost, rank, and selected.
- notes: any warnings, for example mixed currencies or a fallback data source.
