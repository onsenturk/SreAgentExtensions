# Optional scheduled task: monthly FinOps sweep

Create this in Scheduled tasks. It runs the FinOps review on a schedule and posts the report.

- Name: Monthly FinOps cost optimization sweep
- Schedule: monthly, for example the first business day at 08:00.
- Response agent: the finops_cost_optimizer custom agent, or the main agent if you did not create the custom agent.
- Autonomy: Review. Cost recommendations should wait for human approval.

## Task instructions

Run a FinOps cost optimization review across the subscriptions this agent can read.

1. Use the finops-cost-optimizer skill.
2. Narrow scope by amortized spend over the last 30 days, then detect waste across the seven dimensions.
3. Rank findings by estimated monthly savings.
4. Produce the HTML report and post the file link with a short summary: total analyzed spend, total estimated monthly savings, findings by priority, and the top three recommendations.
5. If a previous run exists in memory, add a short month over month note on how analyzed spend and estimated savings changed.

Do not change or delete any resource. Propose recommendations only.
