# Permissions and scope

This skill runs entirely on the agent's default Reader access. It does not require any additional role assignment.

## What this means

- Coverage equals the agent's existing read scope. The skill analyzes only the subscriptions and resource groups this agent was given when it was created.
- There is no tenant wide discovery. If a subscription is outside the agent's scope, the skill does not see it. To widen coverage, widen the agent's scope. That is a separate administrative action and is not a prerequisite for this skill.

## Reads used, all covered by Reader

- Subscription enumeration: the list of subscriptions the identity can see.
- Cost: the Cost Management query at subscription scope. Reader can read cost data at subscription and resource group scope.
- Cost fallback: if a tenant blocks the Cost Management query action, the cost_rank tool falls back to the Consumption usage details read, which is a plain read covered by Reader.
- Advisor cost recommendations.
- Azure Monitor metrics.
- Reservation recommendations. Savings plan recommendations are best effort and may return nothing under Reader in some tenants.
- Resource enumeration for the orphaned and storage checks.

## Billing scope note

Cost figures here come from resource and subscription scope queries. Enrollment or billing account scope data (for example EA or MCA invoice level views) is not used, because that requires billing roles outside the Azure RBAC Reader model.

## Identity setup for the Python tools

The cost_rank and commitment_recommendations tools call Azure Resource Manager. Enable managed identity with the ARM scope on each tool in the Identity tab when you create it in the Builder.
