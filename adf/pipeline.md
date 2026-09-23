# ADF Pipeline — PE Fund Capital, Payment & Reconciliation Intelligence Platform

Covers the orchestration layer: 4 Linked Services, 1 Dataset, and the
pipeline that triggers Databricks Bronze ingestion for all 10 sources.

## Linked Services

| Name | Connects to | Auth |
|---|---|---|
| `ls_KeyVault` | `kv-pe-platform` | Managed identity, granted `Key Vault Secrets User` at the vault level |
| `ls_ADLS` | `pestorage3` (ADLS Gen2) | System Assigned Managed Identity, granted `Storage Blob Data Contributor` on the storage account |
| `ls_AzureSQL` | `pe-platform-sql-server` / `pe-platform-db` | SQL Authentication, password pulled from Key Vault (`sql-password`) |
| `ls_Databricks` | Databricks workspace | Access Token from Key Vault (`databricks-access-token`), cluster type **Serverless** (not "New job cluster" — avoids both the VM quota limit and unnecessary provisioning cost) |

## Dataset

`ds_EtlMetadata` — Azure SQL Database, linked service `ls_AzureSQL`, table
`control.etl_metadata`. The only Dataset needed — ADF never touches raw
data files directly, so no ADLS Dataset exists; Databricks handles all
actual file reads/writes.

## Pipeline: `pl_DailyIngestion`

```
AuditStart
   → LookupSources
      → ForEachSource (10 iterations, sequential)
           → RunBronzeJob  (Databricks Job activity → RunMedallionJob → task BronzeIngestion)
   → AuditCompleteSuccess  (on success)
   → AuditCompleteFailure  (on failure)
```

| Activity | What it does |
|---|---|
| `AuditStart` | Stored Procedure → `control.usp_AuditStart` — logs run start (`run_id`, `pipeline_name`, `status = RUNNING`) |
| `LookupSources` | Lookup → `SELECT * FROM control.etl_metadata WHERE is_active = 1` — returns all 10 active sources, first-row-only unchecked |
| `ForEachSource` | Iterates the 10 rows sequentially |
| `RunBronzeJob` | Databricks Job activity, calls `RunMedallionJob`. Parameters: `source_name = @item().source_name`, `folder_path` = constructed absolute path (see below), `run_id = @pipeline().RunId` |
| `AuditCompleteSuccess` / `AuditCompleteFailure` | Stored Procedure → `control.usp_AuditComplete` — closes out the audit row with final status |

### `folder_path` construction — why it isn't just `@item().landing_path`

`control.etl_metadata.landing_path` only stores a base folder template
(e.g. `market_price/`) — not a resolvable path. The actual value passed
to Databricks is built as:

```
@concat('abfss://ingested@pestorage3.dfs.core.windows.net/', item().landing_path, '*/*')
```

The double wildcard matches any date-partitioned subfolder (`ingestion_date=`
or `business_date=`) and any file inside it, letting one notebook call
correctly pick up all available data for a source without needing to know
the specific date in advance. This is intentional for the current
"manually run, process everything" design — see Trigger Strategy below.

## Trigger Strategy — manual, not a live Storage Event Trigger

**Deliberate decision, not an oversight.** A live Storage Event Trigger
was considered and rejected for this project's scope: with 6 internal
files landing near-simultaneously each generation run, a naive trigger
setup would multiply into far more pipeline executions than sources
actually changed, each consuming real serverless Databricks compute —
a genuine cost risk on a shared, limited student credit budget. Manual
triggering gives the team direct control over when compute is spent,
which matters more here than automation convenience.

## Bugs found & fixed along the way

| Issue | Root cause | Fix |
|---|---|---|
| ADLS Linked Service: "Cannot get storage account key" | Missing `listKeys` permission on the storage account | Switched authentication to System Assigned Managed Identity instead of Account Key |
| ADLS Managed Identity: `AuthorizationPermissionMismatch` | Role assignment was granted to the user's own account instead of ADF's managed identity | Redid the role assignment correctly: Access control (IAM) → Add role assignment → **Managed identity** → Data Factory (V2) → select the actual ADF instance |
| Databricks Linked Service: "does not have required scopes: jobs" | Access token was generated without the `jobs` API scope | Regenerated the token via **Other APIs** (not "BI Tools"), explicitly including the `jobs` scope |
| `AuditStart` failing: "Unrecognized Guid format" | A non-`run_id` parameter (`pipeline_name` or `source_name`) had its Type dropdown incorrectly set to `Guid` instead of `String` | Corrected parameter types in the Stored Procedure activity |
| Databricks job failing: `AZURE_INVALID_CREDENTIALS_CONFIGURATION` on `/mnt/bronze/...` | Serverless compute does not support legacy DBFS mounts or `fs.azure.account.key` config at all | Rebuilt storage access via Unity Catalog: Access Connector (managed identity) → Storage Credential → External Location, notebook rewritten to use direct `abfss://` paths instead of `/mnt/bronze/` |
| Databricks job failing: "Path must be absolute: market_price" | `folder_path` was passed as the bare `etl_metadata.landing_path` value with no storage prefix or date folder | Rebuilt the parameter expression in ADF as a full `abfss://` path with a wildcard (see above) |

## Known limitations

- **`records_read` / `records_written` in `control.pipeline_audit` are
  `NULL`.** The audit-complete call happens at the pipeline level, not
  per-source inside the ForEach loop, so individual row counts from each
  Databricks run aren't captured back into the audit table. Run status,
  timestamps, and success/failure are accurate; row-count granularity was
  deprioritized given the project timeline.
- **Failure-path testing — verified.** A genuine failure was induced by
  pointing one source at a nonexistent path. Confirmed in
  `control.pipeline_audit`: `audit_id = 4`, `run_id = a8563750-5de4-429...`,
  `start_time = 2026-09-23T10:01:5...`, `end_time = 2026-09-23T10:10:4...`,
  `status = FAILED` — a real start/end time pair, not a row stuck at
  `RUNNING` like the earlier cancelled-run attempt. The pipeline canvas
  confirms `ForEachSource`'s red failure branch correctly routed into
  `AuditCompleteFailure`, which executed successfully (green checkmark).
  Both the success path (rows 2–3) and failure path (row 4) are now
  demonstrated with real evidence. See `adf/pipeline/` for the
  supporting screenshots.
