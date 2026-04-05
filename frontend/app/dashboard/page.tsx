import { fetchDashboard } from "@/lib/api";
import { KpiCard } from "@/components/charts/KpiCard";
import { RevenueLineChart } from "@/components/charts/RevenueLineChart";
import { ServiceBarChart } from "@/components/charts/ServiceBarChart";
import { SyncStatus } from "@/components/dashboard/SyncStatus";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

function fmt(v: unknown, prefix = "", suffix = "") {
  if (v == null) return "—";
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

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-white">Overview</h1>
        <div className="text-xs text-zinc-500">Month-to-date</div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-4">
        <KpiCard label="Cash Revenue MTD" value={fmt(kpis.cash_revenue_mtd, "$")} />
        <KpiCard label="Billed Revenue MTD" value={fmt(kpis.billed_revenue_mtd, "$")} />
        <KpiCard label="Jobs Completed" value={fmt(kpis.jobs_completed_mtd)} />
        <KpiCard label="Upcoming Jobs" value={fmt(kpis.jobs_scheduled_upcoming)} />
        <KpiCard label="Leads MTD" value={fmt(kpis.leads_mtd)} />
        <KpiCard label="Ad Spend MTD" value={fmt(kpis.ad_spend_mtd, "$")} />
        <KpiCard label="CPL MTD" value={fmt(kpis.cpl_mtd, "$")} />
        <KpiCard
          label="Google Rating"
          value={kpis.google_avg_rating != null ? `${kpis.google_avg_rating} ★` : "—"}
          sublabel={kpis.google_review_count ? `${kpis.google_review_count} reviews` : undefined}
        />
      </div>

      {/* Charts row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card className="bg-zinc-900 border-zinc-800">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-zinc-300">Cash Revenue — Last 12 Months</CardTitle>
          </CardHeader>
          <CardContent>
            <RevenueLineChart data={revenue as never} />
          </CardContent>
        </Card>

        <Card className="bg-zinc-900 border-zinc-800">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-zinc-300">Revenue by Service — YTD</CardTitle>
          </CardHeader>
          <CardContent>
            <ServiceBarChart data={services as never} />
          </CardContent>
        </Card>
      </div>

      {/* Sync status */}
      {(sync as never[]).length > 0 && (
        <div className="border border-zinc-800 rounded-lg px-4 py-3 bg-zinc-900/50">
          <p className="text-xs text-zinc-500 mb-2 uppercase tracking-wider">Last Sync</p>
          <SyncStatus data={sync as never} />
        </div>
      )}
    </div>
  );
}
