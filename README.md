# DW AI Cloud FinOps

This project is a set of analytics tools to follow up the cloud consumption of DW AI projects (Stellar, DW AI portal, DW AI Insights, GPTap (Rip)).

We build tools to extract cloud consumption data directly from Azure and identify possible optimizations. The aim is to achieve at least **10% of cloud savings** while expanding our product landscape and use cases.

## Tech Stack

- **Language**: TypeScript (strict mode)
- **Backend Framework**: NestJS
- **ORM**: TypeORM
- **Database**: PostgreSQL
- **Testing**: Jest

## Project Structure

```
cloud-finops/
├── azure-consumption-extractor/   # Azure Cost Management API integration
├── azure-metrics-extractor/       # Azure resource usage metrics collection
├── dashboard/                     # Frontend visualization and reporting
├── database/                      # Shared entities, migrations, DataSource
├── ai-agents/                     # AI-powered analysis agents (TBD)
└── .ai/                           # AI agent configuration and task tracking
```

## Prerequisites

- **Node.js** >= 20 LTS
- **npm** >= 10
- **PostgreSQL** >= 18
- **Docker** >= 20.10 (optional, for containerized development)
- **Azure credentials** with appropriate RBAC roles — see [Azure Permissions Guide](docs/azure-permissions.md)

## Environment Configuration

The project uses a **single source of truth** for environment variables: the root `.env`.
Edit it once, then run the sync script to distribute copies to every sub-project.

```bash
cp .env.example .env          # create the root .env
# edit .env — set Azure creds, GCP_AGENTS_API_KEY, DB password, etc.
./scripts/sync-env.sh         # copy it to all sub-projects (--check for a dry run)
```

`sync-env.sh` writes a generated `.env` into `azure-consumption-extractor/`,
`azure-metrics-extractor/`, `database/`, and `ai-agents/python/`. Those copies are
marked "DO NOT EDIT" and are overwritten on every run — always change the root `.env`.
All `.env` files are gitignored; never commit them.

## Quick Start with Docker Compose

The easiest way to get started is using Docker Compose, which sets up PostgreSQL with persistent data and all services:

```bash
# Clone the repository
git clone <repository-url>
cd cloud-finops

# Configure environment (single source of truth)
cp .env.example .env
# Edit .env with your Azure credentials, GCP key, and other settings
./scripts/sync-env.sh
cp docker-compose.override.yml.example docker-compose.override.yml

# Note: docker-compose sets its own DB env; the .env files are for running services locally

# Start all services
docker-compose up --build

# Or run in background
docker-compose up -d --build
```

**Services will be available at:**
- **Consumption Extractor API**: http://localhost:3000
- **Metrics Extractor API**: http://localhost:3001
- **Dashboard**: http://localhost:3002
- **PostgreSQL**: localhost:5432 (database: `cloud_finops`, schema: `finops`)

**Database Persistence:**
- PostgreSQL data is persisted in a Docker volume (`postgres_data`)
- Run `docker-compose down` to stop services (data persists)
- Run `docker-compose down -v` to also remove persistent data

## Manual Development Setup

If you prefer to run services individually without Docker:

Each sub-project is self-contained with its own `package.json`. Navigate to a sub-project and install dependencies:

```bash
# Azure Consumption Extractor
cd azure-consumption-extractor
npm install
npm run build
npm run start:dev

# Azure Metrics Extractor
cd azure-metrics-extractor
npm install
npm run build
npm run start:dev

# Database (shared library)
cd database
npm install
npm run build
```

## Environment Variables

Each sub-project has a `.env.example` file. Copy it to `.env` and fill in the values:

```bash
cp .env.example .env
```

## Database Migrations

### With Docker Compose
```bash
# Run migrations using the migration runner service
docker-compose --profile tools run --rm migration-runner npm run migration:run

# Check migration status
docker-compose --profile tools run --rm migration-runner npm run migration:show

# Revert the last migration
docker-compose --profile tools run --rm migration-runner npm run migration:revert
```

### Manual Setup
```bash
cd database
npm run migration:run       # Apply all pending migrations
npm run migration:revert    # Revert the last migration
npm run migration:show      # Show migration status
```

## Running Tests

```bash
cd <sub-project>
npm run test        # Unit tests
npm run test:cov    # Unit tests with coverage
npm run test:e2e    # End-to-end tests (extractors only)
```

## Sub-Projects

### Azure Consumption Extractor (`azure-consumption-extractor/`)
NestJS service that extracts cloud cost data via the Azure Cost Management API and persists it to the database. Includes:
- **CostModule** — `AzureCostClientService` for querying cost data with flexible date ranges, subscriptions, granularity, and groupBy dimensions. Retry logic with exponential backoff + jitter for 429/5xx.
- **DatabaseModule** — TypeORM connection to PostgreSQL (`finops` schema) with entities for subscriptions, resource groups, and consumption records.
- **ExtractionModule** — `ConsumptionExtractorService` orchestrating the full pipeline: fetch → map → ensure subscriptions/resource groups → upsert consumption records in batches with transaction handling. Supports chunked date ranges (31-day chunks) and idempotent re-runs.
- Auth: `ClientSecretCredential` with `DefaultAzureCredential` fallback
- **Tests**: 47 unit tests (3 suites)
- Port: **3000**

### Azure Metrics Extractor (`azure-metrics-extractor/`)
NestJS service that collects resource utilization metrics from Azure Monitor to detect underused resources. Includes:
- **MetricsModule** — Azure API clients: `AzureResourceClientService` (ARM resource discovery), `AzureMonitorClientService` (metric queries, batch API), `UtilizationMetricsRegistry` (6 resource types, 25 metrics)
- **DatabaseModule** — TypeORM connection with local entity copies: `TrackedResourceEntity`, `MetricDefinitionEntity`, `MetricDataPointEntity`, `UtilizationSummaryEntity`, `SubscriptionEntity`, `ResourceGroupEntity`
- **ExtractionModule** — orchestration and analytics:
  - `MetricsExtractorService` — full pipeline: discover resources → sync to DB → fetch metrics via Batch API → persist data points in batched transactions
  - `UtilizationSummaryService` — daily roll-ups with avg/min/max/p95 computation, configurable underuse thresholds (CPU <10%, Memory <20%, DTU/RU <15%, Storage <10%), `is_underused` flagging
- Configurable thresholds via `underuseThresholdsConfig` (env-var overrides per metric type)
- Auth: `ClientSecretCredential` with `DefaultAzureCredential` fallback
- **Tests**: 99 unit tests (6 suites)
- Port: **3001**

### Cloud FinOps Database (`database/`)
Shared TypeORM library containing entity definitions, migrations, and the DataSource configuration consumed by the extractors.
- **Schema**: `finops` (PostgreSQL)
- **Core Entities**: `SubscriptionEntity`, `ResourceGroupEntity`, `ConsumptionRecordEntity` (FOCUS-compliant, 25+ fields)
- **Metrics Entities**: `TrackedResourceEntity`, `MetricDefinitionEntity`, `MetricDataPointEntity`, `UtilizationSummaryEntity`
- **Enums**: `MetricUnit` (13 values), `AggregationType` (6 values), `TimeGrain` (8 ISO 8601 durations)
- **Migrations**:
  - `InitialCoreSchema` — creates `subscriptions`, `resource_groups`, `consumption_records` tables
  - `AddMetricsSchema` — creates `tracked_resources`, `metric_definitions`, `metric_data_points`, `utilization_summaries` tables with enum types, composite indexes, and FK constraints
- **Tests**: 97 unit tests (7 suites) covering entities, enums, and migration SQL

### Dashboard (`dashboard/`)
Frontend application to visualize consumption trends, utilization metrics, underused resources, and optimization opportunities. *(Scaffold pending — TASK-014)*
- Port: **3002**

### AI Agents (`ai-agents/`) — TBD
Agents designed to analyze cloud consumption data and recommend optimizations. Last phase of the project.