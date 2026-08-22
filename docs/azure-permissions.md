# Azure Permissions Guide

This document describes the Azure RBAC permissions required by the Cloud FinOps extractor services to read cost and utilization data from your Azure subscriptions.

## Authentication

Both services use the **same credential strategy** (via `@azure/identity`):

| Priority | Method | When Used |
|----------|--------|-----------|
| 1st | **Service Principal** (`ClientSecretCredential`) | When `AZURE_TENANT_ID`, `AZURE_CLIENT_ID`, and `AZURE_CLIENT_SECRET` are all set |
| 2nd | **Default Credential Chain** (`DefaultAzureCredential`) | Fallback — supports Managed Identity, Azure CLI, environment variables, etc. |

For production, use a **Service Principal** or **Managed Identity**. For local development, `az login` (Azure CLI) works via `DefaultAzureCredential`.

---

## Required RBAC Roles

### Minimum Built-in Roles

| Service | Role | Scope | Purpose |
|---------|------|-------|---------|
| `azure-consumption-extractor` | **Cost Management Reader** | Subscription | Query cost/usage data via Cost Management API |
| `azure-metrics-extractor` | **Reader** | Subscription | List resources and read metric data from Azure Monitor |

> **Note**: The built-in **Reader** role at subscription scope already includes `Microsoft.Insights/metrics/read` and `Microsoft.Insights/metricDefinitions/read`, so a separate **Monitoring Reader** assignment is not needed.

If both services share the same identity, assign **both roles** to that identity at the subscription scope.

---

## Detailed Permission Breakdown

### Azure Consumption Extractor

Uses the **Azure Cost Management Query API** (`@azure/arm-costmanagement` SDK).

| SDK Client | SDK Method | REST API | Permission Action |
|------------|-----------|----------|-------------------|
| `CostManagementClient` | `query.usage()` | `POST /subscriptions/{id}/providers/Microsoft.CostManagement/query` | `Microsoft.CostManagement/query/action` |

**What it does**: Queries daily cost data aggregated by dimensions (ResourceGroup, MeterCategory, ServiceName, ResourceType) for a given date range. Read-only — no modifications to Azure resources.

**Built-in role**: [Cost Management Reader](https://learn.microsoft.com/en-us/azure/role-based-access-control/built-in-roles#cost-management-reader)

---

### Azure Metrics Extractor

Uses the **Azure Resource Manager** (`@azure/arm-resources`) and **Azure Monitor** (`@azure/arm-monitor`) SDKs.

| SDK Client | SDK Method | REST API | Permission Action |
|------------|-----------|----------|-------------------|
| `ResourceManagementClient` | `resources.list()` | `GET /subscriptions/{id}/resources` | `Microsoft.Resources/subscriptions/resources/read` |
| `ResourceManagementClient` | `resources.listByResourceGroup()` | `GET /subscriptions/{id}/resourceGroups/{rg}/resources` | `Microsoft.Resources/subscriptions/resourceGroups/resources/read` |
| `MonitorClient` | `metricDefinitions.list()` | `GET /{resourceId}/providers/Microsoft.Insights/metricDefinitions` | `Microsoft.Insights/metricDefinitions/read` |
| `MonitorClient` | `metrics.list()` | `GET /{resourceId}/providers/Microsoft.Insights/metrics` | `Microsoft.Insights/metrics/read` |

**What it does**: Discovers Azure resources (VMs, App Services, SQL DBs, Storage, Cosmos DB, AKS), retrieves available metric definitions, and collects utilization time-series data (CPU, memory, DTU, RU, etc.). Read-only — no modifications to Azure resources.

**Built-in role**: [Reader](https://learn.microsoft.com/en-us/azure/role-based-access-control/built-in-roles#reader) (includes all four permission actions above)

---

## Custom Role (Optional)

If you prefer a single custom role with least-privilege, use the following action set:

```json
{
  "Name": "Cloud FinOps Reader",
  "Description": "Minimum permissions for Cloud FinOps cost and metrics extraction",
  "Actions": [
    "Microsoft.CostManagement/query/action",
    "Microsoft.Resources/subscriptions/resources/read",
    "Microsoft.Resources/subscriptions/resourceGroups/resources/read",
    "Microsoft.Insights/metricDefinitions/read",
    "Microsoft.Insights/metrics/read"
  ],
  "NotActions": [],
  "AssignableScopes": [
    "/subscriptions/{your-subscription-id}"
  ]
}
```

---

## Setup Instructions

### 1. Create a Service Principal

```bash
az ad sp create-for-rbac \
  --name "cloud-finops-reader" \
  --role "Reader" \
  --scopes "/subscriptions/{SUBSCRIPTION_ID}"
```

This outputs `appId` (client ID), `password` (client secret), and `tenant`.

### 2. Assign Cost Management Reader

```bash
az role assignment create \
  --assignee "{APP_ID}" \
  --role "Cost Management Reader" \
  --scope "/subscriptions/{SUBSCRIPTION_ID}"
```

### 3. Configure Environment Variables

Add the credentials to your `.env` files (or Docker Compose environment):

```bash
AZURE_TENANT_ID=<tenant>
AZURE_CLIENT_ID=<appId>
AZURE_CLIENT_SECRET=<password>
AZURE_SUBSCRIPTION_ID=<subscription-id>
```

### 4. Verify Access

```bash
# Test cost data access
az costmanagement query \
  --type Usage \
  --scope "subscriptions/{SUBSCRIPTION_ID}" \
  --timeframe MonthToDate

# Test resource listing
az resource list --subscription "{SUBSCRIPTION_ID}" --output table

# Test metric reading (example: VM CPU)
az monitor metrics list \
  --resource "/subscriptions/{SUBSCRIPTION_ID}/resourceGroups/{RG}/providers/Microsoft.Compute/virtualMachines/{VM_NAME}" \
  --metric "Percentage CPU" \
  --interval PT1H
```

---

## Security Best Practices

- **Least privilege**: Both roles are read-only. No write, delete, or management actions are granted.
- **Scope to subscription**: Don't grant roles at the management group level unless you need multi-subscription extraction.
- **Rotate secrets**: If using a Service Principal, rotate the client secret on a regular schedule (90 days recommended).
- **Prefer Managed Identity**: When running in Azure (AKS, App Service, Container Apps), use Managed Identity instead of client secrets — eliminates secret management entirely.
- **Audit**: Enable Azure Activity Log monitoring on role assignments to detect unauthorized changes.
