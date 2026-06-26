# Checks catalog

Seven cost optimization dimensions. For each finding record: resource id, dimension, current configuration, proposed change, estimated monthly saving, risk rating, and evidence. All commands are read only.

Use the azure-pricing approach (Azure retail prices) to estimate the cost of a target SKU, and the current cost from cost_rank, to compute saving = current minus target.

## 1. Azure Advisor cost baseline

Start here. Advisor already finds many opportunities.

- List: az advisor recommendation list --category Cost --subscription <id>
- Capture each recommendation's impacted resource, problem, and the saving Advisor reports.
- Treat Advisor savings as the baseline and reconcile with your own findings to avoid double counting.

Risk: low. Evidence: the Advisor recommendation id and its reported saving.

## 2. Orphaned resources

Resources that cost money with nothing attached.

- Unattached managed disks: az disk list --subscription <id> --query "[?managedBy==null && diskState=='Unattached']"
- Unassociated public IPs: az network public-ip list --subscription <id> --query "[?ipConfiguration==null]"
- Unattached network interfaces: az network nic list --subscription <id> --query "[?virtualMachine==null]"
- Empty App Service plans: az appservice plan list --subscription <id> --query "[?numberOfSites==0]"
- Idle public load balancers and gateways with no backend pool members.

Saving: the full cost of the orphaned resource. Risk: low to medium (confirm the resource is not a staged or standby resource). Evidence: the empty association field plus age.

## 3. Commitment coverage

Reservations and savings plans for steady state usage.

- Call the commitment_recommendations tool. It returns reservation recommendations and, on a best effort basis, savings plan recommendations, each with the projected saving.
- Cross check against current coverage so you do not over recommend.

Saving: the projected net saving from the recommendation. Risk: medium (commitment term). Evidence: the recommendation payload and the usage that backs it.

## 4. Idle or underused resources

Resources that run but do little. Requires metrics.

- Pull Azure Monitor metrics over a 30 day window: az monitor metrics list --resource <id> --metric "Percentage CPU" --interval PT1H --start-time <iso> --end-time <iso>
- Flag a virtual machine as idle when average CPU is below 5 percent and network throughput is low across the window.
- Apply the same idea to gateways and load balancers with negligible throughput.

Saving: deallocate, or resize to a smaller SKU priced with the azure-pricing approach. Risk: medium (confirm the workload is not scheduled or seasonal). Evidence: the metric averages and the window.

## 5. Storage optimization

- Redundancy: flag GRS or ZRS accounts where LRS would meet the requirement. az storage account list --subscription <id> --query "[].{name:name,sku:sku.name}"
- Lifecycle: flag accounts with no lifecycle management policy that hold cool or rarely accessed blobs.
- Stale snapshots and old disk snapshots: az snapshot list --subscription <id>

Saving: redundancy tier delta, lifecycle tiering to cool or archive, snapshot deletion. Risk: low to medium. Evidence: the SKU, the missing policy, or the snapshot age.

## 6. Log Analytics optimization

- Retention beyond need: az monitor log-analytics workspace list --subscription <id>, then review retentionInDays.
- Ingestion volume: identify high ingestion tables and whether a commitment tier or basic logs would cost less.

Saving: shorter retention, a commitment tier, or moving verbose tables to basic logs. Risk: low to medium (retention may be a compliance requirement, confirm before recommending). Evidence: retention setting and ingestion volume.

## 7. Dev and test scheduling

- Identify non production subscriptions or resource groups by naming convention or tags.
- Flag virtual machines and other compute that run 24 by 7 but are only used in working hours.

Saving: a scheduled shutdown outside working hours, roughly the off hours fraction of compute cost. Risk: low. Evidence: the tag or naming convention plus the run pattern.
