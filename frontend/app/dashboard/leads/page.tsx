import { fetchDashboard } from "@/lib/api";
import { KpiCard } from "@/components/charts/KpiCard";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { GoogleMetricsChart } from "@/components/charts/GoogleMetricsChart";

interface LeadSource {
  lead_source: string;
  total_leads: number;
  converted_leads: number;
  conversion_rate_pct: number | null;
}

interface GoogleRow {
  metric_date: string;
  total_reviews: number;
  average_rating: number;
  calls: number;
  website_clicks: number;
  direction_requests: number;
}

function fmt(v: unknown, suffix = "") {
  if (v == null) return "—";
  return `${Number(v).toLocaleString()}${suffix}`;
}

export default async function LeadsPage() {
  const [leads, google] = await Promise.all([
    fetchDashboard("/api/dashboard/leads").catch(() => []),
    fetchDashboard("/api/dashboard/google").catch(() => []),
  ]) as [LeadSource[], GoogleRow[]];

  const totalLeads = leads.reduce((s, r) => s + (r.total_leads || 0), 0);
  const totalConverted = leads.reduce((s, r) => s + (r.converted_leads || 0), 0);
  const overallConversion = totalLeads > 0 ? ((totalConverted / totalLeads) * 100).toFixed(1) : null;
  const latestGoogle = google[google.length - 1];

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      <h1 className="text-xl font-semibold text-white">Leads</h1>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <KpiCard label="Total Leads MTD" value={fmt(totalLeads)} />
        <KpiCard label="Converted MTD" value={fmt(totalConverted)} />
        <KpiCard label="Conversion Rate" value={overallConversion ? `${overallConversion}%` : "—"} />
        <KpiCard
          label="Google Rating"
          value={latestGoogle ? `${latestGoogle.average_rating} ★` : "—"}
          sublabel={latestGoogle ? `${latestGoogle.total_reviews} reviews` : undefined}
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Lead source table */}
        <Card className="bg-zinc-900 border-zinc-800">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-zinc-300">Leads by Source — MTD</CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            <Table>
              <TableHeader>
                <TableRow className="border-zinc-800">
                  <TableHead className="text-zinc-400 text-xs">Source</TableHead>
                  <TableHead className="text-zinc-400 text-xs text-right">Leads</TableHead>
                  <TableHead className="text-zinc-400 text-xs text-right">Converted</TableHead>
                  <TableHead className="text-zinc-400 text-xs text-right">Conv. Rate</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {leads.map((row, i) => (
                  <TableRow key={i} className="border-zinc-800">
                    <TableCell className="text-zinc-200 text-sm capitalize">{row.lead_source}</TableCell>
                    <TableCell className="text-zinc-300 text-sm text-right">{fmt(row.total_leads)}</TableCell>
                    <TableCell className="text-zinc-300 text-sm text-right">{fmt(row.converted_leads)}</TableCell>
                    <TableCell className="text-zinc-300 text-sm text-right">
                      {row.conversion_rate_pct != null ? `${row.conversion_rate_pct}%` : "—"}
                    </TableCell>
                  </TableRow>
                ))}
                {leads.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={4} className="text-zinc-500 text-sm text-center py-8">
                      No lead data for this period
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </CardContent>
        </Card>

        {/* Google Business metrics chart */}
        <Card className="bg-zinc-900 border-zinc-800">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-zinc-300">Google Business — Last 30 Days</CardTitle>
          </CardHeader>
          <CardContent>
            <GoogleMetricsChart data={google} />
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
