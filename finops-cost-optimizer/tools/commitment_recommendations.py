"""
commitment_recommendations: Reservation and savings plan recommendations.

Azure SRE Agent Python tool. Uses the agent managed identity (ARM scope) to read
reservation recommendations (covered by Reader) and, on a best effort basis,
savings plan benefit recommendations, for each subscription in scope.

Returns a JSON serializable dict. Heavy imports are loaded lazily inside
functions.
"""

ARM_ENDPOINT = "https://management.azure.com"


def _token():
    from azure.identity import DefaultAzureCredential

    credential = DefaultAzureCredential()
    return credential.get_token(f"{ARM_ENDPOINT}/.default").token


def _get_all(headers, url):
    import requests

    items = []
    pages = 0
    while url and pages < 20:
        response = requests.get(url, headers=headers, timeout=120)
        response.raise_for_status()
        body = response.json()
        items.extend(body.get("value", []))
        url = body.get("nextLink")
        pages += 1
    return items


def _reservation_recommendations(headers, subscription_id, look_back):
    url = (
        f"{ARM_ENDPOINT}/subscriptions/{subscription_id}"
        "/providers/Microsoft.Consumption/reservationRecommendations"
        f"?api-version=2023-05-01&$filter=properties/lookBackPeriod eq '{look_back}'"
    )
    out = []
    for item in _get_all(headers, url):
        props = item.get("properties", {})
        out.append(
            {
                "kind": "reservation",
                "sku": props.get("skuName") or props.get("displayName"),
                "scope": props.get("scope"),
                "term": props.get("term"),
                "recommended_quantity": props.get(
                    "recommendedQuantityNormalized", props.get("recommendedQuantity")
                ),
                "net_savings": props.get("netSavings"),
                "currency": props.get("currencyCode") or props.get("netSavingsCurrency"),
                "location": item.get("location"),
            }
        )
    return out


def _savings_plan_recommendations(headers, subscription_id, look_back):
    # Best effort. May return nothing under Reader in some tenants.
    url = (
        f"{ARM_ENDPOINT}/subscriptions/{subscription_id}"
        "/providers/Microsoft.CostManagement/benefitRecommendations"
        f"?api-version=2024-08-01&$filter=properties/lookBackPeriod eq '{look_back}'"
    )
    out = []
    for item in _get_all(headers, url):
        props = item.get("properties", {})
        out.append(
            {
                "kind": "savings_plan",
                "term": props.get("term"),
                "net_savings": props.get("savingsAmount") or props.get("netSavings"),
                "currency": props.get("currencyCode"),
                "scope": props.get("scope"),
            }
        )
    return out


def main(subscription_ids: list = None, look_back_period: str = "Last30Days") -> dict:
    """Return reservation and savings plan recommendations for the given subscriptions.

    subscription_ids: the subscriptions to analyze. Pass the selected_subscriptions
    from cost_rank. If omitted, returns an error asking for the list.
    look_back_period: one of Last7Days, Last30Days, Last60Days.
    """
    if not subscription_ids:
        return {"error": "Provide subscription_ids, for example the selected_subscriptions from cost_rank."}

    headers = {"Authorization": f"Bearer {_token()}", "Content-Type": "application/json"}
    results = {}
    notes = []
    total_savings = 0.0
    for subscription_id in subscription_ids:
        reservations = []
        savings_plans = []
        try:
            reservations = _reservation_recommendations(headers, subscription_id, look_back_period)
        except Exception as error:  # noqa: BLE001 - surface, continue with others
            notes.append(f"Subscription {subscription_id}: reservation recommendations unavailable ({error}).")
        try:
            savings_plans = _savings_plan_recommendations(headers, subscription_id, look_back_period)
        except Exception as error:  # noqa: BLE001 - best effort under Reader
            notes.append(f"Subscription {subscription_id}: savings plan recommendations unavailable ({error}).")
        for recommendation in reservations + savings_plans:
            try:
                total_savings += float(recommendation.get("net_savings") or 0.0)
            except (TypeError, ValueError):
                pass
        results[subscription_id] = {"reservations": reservations, "savings_plans": savings_plans}

    return {
        "look_back_period": look_back_period,
        "estimated_total_net_savings": round(total_savings, 2),
        "by_subscription": results,
        "notes": notes,
    }


def _cli():
    import argparse
    import json

    parser = argparse.ArgumentParser(description="Reservation and savings plan recommendations.")
    parser.add_argument("--subscriptions", type=str, required=True, help="Comma separated subscription ids.")
    parser.add_argument("--look-back-period", type=str, default="Last30Days")
    args = parser.parse_args()
    subscription_ids = [s.strip() for s in args.subscriptions.split(",") if s.strip()]
    print(json.dumps(main(subscription_ids=subscription_ids, look_back_period=args.look_back_period), indent=2))


if __name__ == "__main__":
    _cli()
