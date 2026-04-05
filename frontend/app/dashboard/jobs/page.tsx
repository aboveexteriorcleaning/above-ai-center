import { fetchDashboard } from "@/lib/api";
import { KpiCard } from "@/components/charts/KpiCard";
import { RevenueLineChart } from "@/components/charts/RevenueLineChart";
import { ServiceBarChart } from "@/components/charts/ServiceBarChart";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

interface ServiceRow {
  service_type: string;
  revenue: number;
  job_count: number;
}

interface JobsData {
  by_service: ServiceRow[];
  trend: unknown[];
}

function fmt(v: unknown, prefix = "", suffix = "") {
  if (v == null) return "—";
  const n = Number(v);
  if (isNaN(n)) return String(v);
  return `${prefix}${n.toLocaleString()}${suffix}`;
}

export default async function JobsPage() {
  const [jobsData, revenue] = await Promise.all([
    fetchDashboard("/api/dashboard/jobs").catch(() => ({ by_service: [], trend: [] })),
    fetchDashboard("/api/dashboard/revenue").catch(() => []),
  ]) as [JobsData, unknown[]];

  const { by_service = [] } = jobsData;
  const totalRevenue = by_service.reduce((s, r) => s + (r.revenue || 0), 0);
  const totalJobs = by_service.reduce((s, r) => s + (r.job_count || 0), 0);
  const topService = by_service[0]?.service_type ?? "—";

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      <h1 className="text-xl font-semibold text-white">Jobs & Revenue</h1>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <KpiCard label="Revenue YTD" value={fmt(totalRevenue.toFixed(2), "$")} />
        <KpiCard label="Completed Jobs YTD" value={fmt(totalJobs)} />
        <KpiCard label="Top Service" value={topService.replace(/_/g, " ")} />
        <KpiCard
          label="Avg Job Value"
          value={totalJobs > 0 ? fmt((totalRevenue / totalJobs).toFixed(2), "$") : "—"}
        />
      </div>

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
            <CardTitle className="text-sm font-medium text-zinc-300">Revenue by Service Type — YTD</CardTitle>
          </CardHeader>
          <CardContent>
            <ServiceBarChart data={by_service as never} />
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
