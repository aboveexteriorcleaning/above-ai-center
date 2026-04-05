# Workflow: Job Revenue & Scheduling Queries

## Objective
Answer questions about job value, scheduled revenue, and job counts accurately.

## Data Source
Table: `jobs`
- Key fields: `scheduled_start`, `scheduled_end`, `completed_at`, `created_at`, `total_amount`, `status`, `service_type`
- Synced from Jobber every 2 hours (last 30 days of updated jobs). Full sync runs weekly Sunday 2am.

## CRITICAL: Date Field Rules

| Question intent | Field to use |
|----------------|-------------|
| "scheduled for March", "on the books", "upcoming" | `scheduled_start` |
| "completed in March", "finished" | `completed_at` |
| "booked in March", "created in March" | `created_at` |
| "invoiced" | use `invoices` table instead |

**Never** filter on `created_at` when the user asks about when a job is scheduled.

## Status Values

| Status | Meaning | Include in revenue? |
|--------|---------|---------------------|
| `scheduled` | On the calendar, not done yet | Yes — it's booked value |
| `completed` | Work done | Yes |
| `cancelled` | Cancelled | No — exclude unless explicitly asked |
| `quote` | Still a quote, not a confirmed job | No — exclude unless explicitly asked |

Default for "job value scheduled" or "jobs on the books": `WHERE status IN ('scheduled', 'completed')`

## Common Query Patterns

### Total job value scheduled for a specific month
```sql
SELECT
  COUNT(*)                        AS job_count,
  ROUND(SUM(total_amount), 2)     AS total_job_value
FROM jobs
WHERE scheduled_start >= '2026-03-01'
  AND scheduled_start < '2026-04-01'
  AND status IN ('scheduled', 'completed');
```

### This month's scheduled job value (dynamic)
```sql
SELECT
  COUNT(*)                        AS job_count,
  ROUND(SUM(total_amount), 2)     AS total_job_value
FROM jobs
WHERE scheduled_start >= DATE_TRUNC('month', CURRENT_DATE)
  AND scheduled_start < DATE_TRUNC('month', CURRENT_DATE) + INTERVAL '1 month'
  AND status IN ('scheduled', 'completed');
```

### Job value by service type this month
```sql
SELECT
  service_type,
  COUNT(*)                        AS job_count,
  ROUND(SUM(total_amount), 2)     AS total_value
FROM jobs
WHERE scheduled_start >= DATE_TRUNC('month', CURRENT_DATE)
  AND scheduled_start < DATE_TRUNC('month', CURRENT_DATE) + INTERVAL '1 month'
  AND status IN ('scheduled', 'completed')
GROUP BY service_type
ORDER BY total_value DESC;
```

### Completed revenue vs scheduled value (cash vs pipeline)
```sql
SELECT
  SUM(CASE WHEN status = 'completed' THEN total_amount ELSE 0 END) AS completed_revenue,
  SUM(CASE WHEN status = 'scheduled' THEN total_amount ELSE 0 END) AS pipeline_value,
  SUM(CASE WHEN status IN ('scheduled','completed') THEN total_amount ELSE 0 END) AS total_on_books
FROM jobs
WHERE scheduled_start >= DATE_TRUNC('month', CURRENT_DATE)
  AND scheduled_start < DATE_TRUNC('month', CURRENT_DATE) + INTERVAL '1 month';
```

## Edge Cases
- `total_amount` on jobs is Jobber's estimated/invoiced value. Actual cash received is in the `payments` table.
- Jobs can be rescheduled — `scheduled_start` always reflects the current scheduled date, not original booking date.
- If the answer seems low, check whether cancelled jobs are being excluded correctly.
