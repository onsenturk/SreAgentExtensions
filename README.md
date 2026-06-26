# Azure SRE Agent FinOps Cost Optimizer

A FinOps cost optimization Skill and its Python tools for Azure SRE Agent. The agent ranks the subscriptions and resource groups it can read by spend, detects waste across seven dimensions, ranks recommendations by estimated savings, and produces a self contained HTML report.

This repository holds the source. The running artifact lives inside the SRE Agent, authored in the Builder.

## What is here

- finops-cost-optimizer/SKILL.md: the orchestration playbook.
- finops-cost-optimizer/references/: supporting reference files the skill follows.
- finops-cost-optimizer/tools/: the Python tools (cost_rank, commitment_recommendations, generate_report) plus a unit test for the ranking math.
- finops-cost-optimizer/optional/: an optional custom agent and an optional monthly scheduled task.

## Design summary

- Output: a self contained HTML report (charts embedded, no external assets), delivered as a file link. Issue creation is optional and off by default.
- Permissions: the agent's default Reader. No extra role grant. Coverage equals the agent's existing read scope.
- Ranking: two phase. Spend narrows scope (top decile with a floor for small tenants). Savings ranks the final findings.
- Guardrails: read only. Recommendations carry evidence, an estimated saving, and a risk rating. Run the trigger in Review mode.

## How to author this into the SRE Agent Builder

1. Create the Python tools. In Builder, open the subagent builder and create three Python tools by pasting the code from finops-cost-optimizer/tools. On each tool, open the Identity tab and enable managed identity with the ARM scope.
   - cost_rank from tools/cost_rank.py
   - commitment_recommendations from tools/commitment_recommendations.py
   - generate_report from tools/generate_report.py
2. Create the skill. In Builder then Skills, create a skill named finops-cost-optimizer. Paste finops-cost-optimizer/SKILL.md into the editor, then upload the files under references/ as supporting files. Attach the tools RunAzCliReadCommands, cost_rank, commitment_recommendations, and generate_report.
3. Test. In a new chat thread, ask the agent to run a cost optimization review. Confirm the skill loads, the cost numbers reconcile against the Azure Cost Management portal for one subscription, and the report link opens.
4. Optional. Create the custom agent from optional/finops-cost-optimizer.agent.yaml and the scheduled task from optional/monthly-finops-sweep.md. Set the trigger to Review mode.

## Deploy with IaC (alternative)

Instead of the Builder, you can deploy the skill as code. The working path for most tenants is the data plane script iac/deploy.ps1, which PUTs the skill (with the reference files and Python helpers bundled as additionalFiles) to the agent endpoint, the same surface the portal Builder uses. A Bicep control plane template is also included, but the control plane Agent Extensions API is restricted to internal Microsoft tenants in preview. See iac/README.md.

## Prerequisites

- An Azure SRE Agent with Builder access.
- The agent's managed identity has its default Reader on the subscriptions and resource groups you want analyzed.
- For the optional issue creation, a connected GitHub or Azure DevOps repository.
