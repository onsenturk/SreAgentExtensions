"""
cost_rank: Rank Azure subscriptions and resource groups by amortized spend.

Azure SRE Agent Python tool. Uses the agent managed identity (ARM scope) to
query Azure Cost Management at subscription scope over a trailing window, groups
cost by resource group, and selects the top decile with a floor so small tenants
still return a usable set. Falls back to the Consumption usage details read when
the Cost Management query action is not available under the current permissions.

Returns a JSON serializable dict. See references/ranking-method.md.

Heavy imports (azure-identity, requests) are loaded lazily inside functions so
the pure ranking helper can be imported and unit tested without those packages.
"""

import math
from datetime import datetime, timedelta, timezone

ARM_ENDPOINT = "https://management.azure.com"


def _select_top(items, top_percent, minimum):
    """Tag each item with a 1-based rank and a selected flag.

    items: a list of dicts already sorted by cost descending.
    Selection count: min(N, max(minimum, ceil(N * top_percent / 100))).
    Returns (items, selected_count).
    """
    n = len(items)
    if n == 0:
        return items, 0
    count = min(n, max(int(minimum), math.ceil(n * float(top_percent) / 100.0)))
    for index, item in enumerate(items):
        item["rank"] = index + 1
        item["selected"] = index < count
    return items, count


def _token():
    from azure.identity import DefaultAzureCredential

    credential = DefaultAzureCredential()
    return credential.get_token(f"{ARM_ENDPOINT}/.default").token


def _list_subscriptions(headers):
    import requests

    url = f"{ARM_ENDPOINT}/subscriptions?api-version=2022-12-01"
    subscriptions = []
    while url:
        response = requests.get(url, headers=headers, timeout=60)
        response.raise_for_status()
        body = response.json()
        for item in body.get("value", []):
            if item.get("state") in (None, "Enabled"):
                subscriptions.append(
                    {
                        "id": item["subscriptionId"],
                        "name": item.get("displayName", item["subscriptionId"]),
                    }
                )
        url = body.get("nextLink")
    return subscriptions


def _query_cost_management(headers, subscription_id, start, end):
    """Amortized cost grouped by resource group at subscription scope.

    Returns (rows, currency) where rows is a list of (resource_group, cost).
    Raises on failure so the caller can fall back to Consumption.
    """
    import requests

    url = (
        f"{ARM_ENDPOINT}/subscriptions/{subscription_id}"
        "/providers/Microsoft.CostManagement/query?api-version=2023-11-01"
    )
    payload = {
        "type": "AmortizedCost",
        "timeframe": "Custom",
        "timePeriod": {"from": start, "to": end},
        "dataset": {
            "granularity": "None",
            "aggregation": {"totalCost": {"name": "Cost", "function": "Sum"}},
            "grouping": [{"type": "Dimension", "name": "ResourceGroupName"}],
        },
    }
    response = requests.post(url, headers=headers, json=payload, timeout=120)
    response.raise_for_status()
    body = response.json()
    properties = body.get("properties", {})
    columns = [c["name"] for c in properties.get("columns", [])]
    cost_index = columns.index("Cost") if "Cost" in columns else 0
    rg_index = columns.index("ResourceGroupName") if "ResourceGroupName" in columns else None
    currency_index = columns.index("Currency") if "Currency" in columns else None
    rows = []
    currency = None
    for row in properties.get("rows", []):
        resource_group = row[rg_index] if rg_index is not None else "(unassigned)"
        raw_cost = row[cost_index] if cost_index < len(row) else 0.0
        cost = float(raw_cost) if raw_cost is not None else 0.0
        if currency_index is not None and currency_index < len(row):
            currency = row[currency_index]
        rows.append((resource_group or "(unassigned)", cost))
    return rows, currency


def _query_consumption(headers, subscription_id, start, end):
    """Fallback: aggregate Consumption usage details cost by resource group."""
    import requests

    url = (
        f"{ARM_ENDPOINT}/subscriptions/{subscription_id}"
        "/providers/Microsoft.Consumption/usageDetails"
        f"?api-version=2023-05-01&$filter=properties/usageStart ge '{start}'"
        f" and properties/usageEnd le '{end}'"
    )
    totals = {}
    currency = None
    pages = 0
    while url and pages < 50:
        response = requests.get(url, headers=headers, timeout=120)
        response.raise_for_status()
        body = response.json()
        for item in body.get("value", []):
            props = item.get("properties", {})
            resource_group = props.get("resourceGroup") or props.get("resourceGroupName") or "(unassigned)"
            cost = props.get("cost", props.get("costInBillingCurrency", 0.0)) or 0.0
            currency = props.get("billingCurrency", props.get("currency", currency))
            totals[resource_group] = totals.get(resource_group, 0.0) + float(cost)
        url = body.get("nextLink")
        pages += 1
    return [(rg, cost) for rg, cost in totals.items()], currency


def main(
    top_percent: float = 10.0,
    min_subscriptions: int = 3,
    min_resource_groups: int = 5,
    lookback_days: int = 30,
    subscription_ids: list = None,
) -> dict:
    """Rank visible subscriptions and resource groups by amortized spend.

    top_percent: the top percentage to select at each level.
    min_subscriptions: floor on the number of subscriptions to select.
    min_resource_groups: floor on the number of resource groups per subscription.
    lookback_days: the trailing window in days.
    subscription_ids: optional explicit list; when omitted, enumerate visible subscriptions.
    """
    headers = {"Authorization": f"Bearer {_token()}", "Content-Type": "application/json"}
    end_date = datetime.now(timezone.utc).date()
    start_date = end_date - timedelta(days=int(lookback_days))
    start = start_date.isoformat()
    end = end_date.isoformat()

    notes = []
    data_source = "CostManagement"

    if subscription_ids:
        subscriptions = [{"id": sub, "name": sub} for sub in subscription_ids]
    else:
        try:
            subscriptions = _list_subscriptions(headers)
        except Exception as error:  # noqa: BLE001 - surface the failure to the agent
            return {"error": f"Could not list subscriptions: {error}", "subscriptions": []}

    currencies = set()
    resource_groups = {}
    for sub in subscriptions:
        rows = []
        currency = None
        try:
            rows, currency = _query_cost_management(headers, sub["id"], start, end)
        except Exception as cost_error:  # noqa: BLE001 - fall back to Consumption
            try:
                rows, currency = _query_consumption(headers, sub["id"], start, end)
                data_source = "Consumption"
                notes.append(f"Subscription {sub['id']}: used Consumption fallback ({cost_error}).")
            except Exception as consumption_error:  # noqa: BLE001
                notes.append(f"Subscription {sub['id']}: no cost data ({consumption_error}).")
        if currency:
            currencies.add(currency)
        rg_items = [{"name": rg, "cost": round(cost, 2)} for rg, cost in rows]
        rg_items.sort(key=lambda item: item["cost"], reverse=True)
        _select_top(rg_items, top_percent, min_resource_groups)
        resource_groups[sub["id"]] = rg_items
        sub["total_cost"] = round(sum(item["cost"] for item in rg_items), 2)

    subscriptions.sort(key=lambda item: item.get("total_cost", 0.0), reverse=True)
    _select_top(subscriptions, top_percent, min_subscriptions)

    if len(currencies) > 1:
        notes.append(f"Mixed currencies across subscriptions: {sorted(currencies)}. Totals are not converted.")

    selected_ids = [sub["id"] for sub in subscriptions if sub.get("selected")]
    selected_resource_groups = {sid: resource_groups.get(sid, []) for sid in selected_ids}

    return {
        "lookback_days": int(lookback_days),
        "window": {"from": start, "to": end},
        "currency": sorted(currencies)[0] if len(currencies) == 1 else None,
        "data_source": data_source,
        "subscriptions": subscriptions,
        "selected_subscriptions": selected_ids,
        "resource_groups": selected_resource_groups,
        "notes": notes,
    }


def _cli():
    import argparse
    import json

    parser = argparse.ArgumentParser(description="Rank Azure subscriptions and resource groups by amortized spend.")
    parser.add_argument("--top-percent", type=float, default=10.0)
    parser.add_argument("--min-subscriptions", type=int, default=3)
    parser.add_argument("--min-resource-groups", type=int, default=5)
    parser.add_argument("--lookback-days", type=int, default=30)
    parser.add_argument("--subscriptions", type=str, default=None, help="Comma separated subscription ids.")
    args = parser.parse_args()
    subscription_ids = [s.strip() for s in args.subscriptions.split(",") if s.strip()] if args.subscriptions else None
    result = main(
        top_percent=args.top_percent,
        min_subscriptions=args.min_subscriptions,
        min_resource_groups=args.min_resource_groups,
        lookback_days=args.lookback_days,
        subscription_ids=subscription_ids,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    _cli()
