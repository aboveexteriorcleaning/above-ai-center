import { fetchDashboard } from "@/lib/api";
import { KpiCard } from "@/components/charts/KpiCard";
import { RevenueLineChart } from "@/components/charts/RevenueLineChart";
import { ServiceBarChart } from "@/components/charts/ServiceBarChart";
import { SyncStatus } from "@/components/dashboard/SyncStatus";

function fmt(v: unknown, prefix = "", suffix = "") {
  if (v == null) return null;
  const n = Number(v);
  if (isNaN(n)) return String(v);
  return `${prefix}${n.toLocaleString()}${suffix}`;
}

export default async function DashboardPage() {
  const [kpis, revenue, services, sync] = await Promise.all([
    fetchDashboard("/api/dashboard/kpis").catch(() => ({})),
    fetchDashboard("/api/dashboard/revenue").catch(() => []),
    fetchDashboard("/api/dashboard/services").catch(() => []),
    fetchDashboard("/api/dashboard/sync").catch(() => []),
  ]) as [Record<string, unknown>, unknown[], unknown[], unknown[]];

  const now = new Date();
  const monthName = now.toLocaleString("default", { month: "long" });

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex items-end justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight" style={{ color: "#f0f1f6" }}>
            Overview
          </h1>
          <p className="text-sm mt-0.5" style={{ color: "#6b6f8a" }}>
            {monthName} month-to-date
          </p>
        </div>
        {(sync as never[]).length > 0 && (
          <div
            className="rounded-xl px-4 py-2 border hidden sm:block"
            style={{ background: "#242638", borderColor: "#2e3048" }}
          >
            <p className="text-xs mb-1.5" style={{ color: "#6b6f8a" }}>Data synced</p>
            <SyncStatus data={sync as never} />
          </div>
        )}
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <KpiCard label="Cash Revenue" value={fmt(kpis.cash_revenue_mtd, "$")} accent />
        <KpiCard label="Billed Revenue" value={fmt(kpis.billed_revenue_mtd, "$")} />
        <KpiCard label="Jobs Completed" value={fmt(kpis.jobs_completed_mtd)} />
        <KpiCard label="Upcoming Jobs" value={fmt(kpis.jobs_scheduled_upcoming)} />
        <KpiCard label="Leads" value={fmt(kpis.leads_mtd)} />
        <KpiCard label="Ad Spend" value={fmt(kpis.ad_spend_mtd, "$")} />
        <KpiCard label="Cost Per Lead" value={fmt(kpis.cpl_mtd, "$")} />
        <KpiCard
          label="Google Rating"
          value={kpis.google_avg_rating != null && Number(kpis.google_avg_rating) > 0
            ? `${kpis.google_avg_rating} ★`
            : null}
          sublabel={kpis.google_review_count ? `${kpis.google_review_count} reviews` : undefined}
        />
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div
          className="rounded-2xl border p-5"
          style={{ background: "#242638", borderColor: "#2e3048" }}
        >
          <p className="text-sm font-medium mb-4" style={{ color: "#a0a3b8" }}>
            Cash Revenue — Last 12 Months
          </p>
          <RevenueLineChart data={revenue as never} />
        </div>

        <div
          className="rounded-2xl border p-5"
          style={{ background: "#242638", borderColor: "#2e3048" }}
        >
          <p className="text-sm font-medium mb-4" style={{ color: "#a0a3b8" }}>
            Revenue by Service — Year to Date
          </p>
          <ServiceBarChart data={services as never} />
        </div>
      </div>
    </div>
  );
}
