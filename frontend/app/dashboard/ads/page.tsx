import { fetchDashboard } from "@/lib/api";
import { KpiCard } from "@/components/charts/KpiCard";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { AdSpendLineChart } from "@/components/charts/AdSpendLineChart";

interface Campaign {
  campaign_name: string;
  status: string;
  spend: number;
  leads: number;
  impressions: number;
  clicks: number;
  cpl: number | null;
  roas: number | null;
}

interface DailyRow {
  date: string;
  spend: number;
  leads: number;
  cpl: number | null;
}

interface AdsData {
  campaigns: Campaign[];
  daily: DailyRow[];
}

function fmt(v: unknown, prefix = "", suffix = "") {
  if (v == null) return "—";
  const n = Number(v);
  if (isNaN(n)) return String(v);
  return `${prefix}${n.toLocaleString()}${suffix}`;
}

export default async function AdsPage() {
  const data = await fetchDashboard("/api/dashboard/ads").catch(() => ({ campaigns: [], daily: [] })) as AdsData;
  const { campaigns = [], daily = [] } = data;

  const totalSpend = campaigns.reduce((s, c) => s + (c.spend || 0), 0);
  const totalLeads = campaigns.reduce((s, c) => s + (c.leads || 0), 0);
  const blendedCpl = totalLeads > 0 ? totalSpend / totalLeads : null;

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      <h1 className="text-xl font-semibold text-white">Ad Performance</h1>

      {/* KPIs */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <KpiCard label="Total Spend MTD" value={fmt(totalSpend.toFixed(2), "$")} />
        <KpiCard label="Total Leads MTD" value={fmt(totalLeads)} />
        <KpiCard label="Blended CPL" value={blendedCpl ? fmt(blendedCpl.toFixed(2), "$") : "—"} />
        <KpiCard label="Campaigns" value={campaigns.length} />
      </div>

      {/* Spend trend */}
      <Card className="bg-zinc-900 border-zinc-800">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium text-zinc-300">Daily Spend & CPL — Last 30 Days</CardTitle>
        </CardHeader>
        <CardContent>
          <AdSpendLineChart data={daily} />
        </CardContent>
      </Card>

      {/* Campaign table */}
      <Card className="bg-zinc-900 border-zinc-800">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium text-zinc-300">Campaigns MTD</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow className="border-zinc-800">
                <TableHead className="text-zinc-400 text-xs">Campaign</TableHead>
                <TableHead className="text-zinc-400 text-xs text-right">Spend</TableHead>
                <TableHead className="text-zinc-400 text-xs text-right">Leads</TableHead>
                <TableHead className="text-zinc-400 text-xs text-right">CPL</TableHead>
                <TableHead className="text-zinc-400 text-xs text-right">ROAS</TableHead>
                <TableHead className="text-zinc-400 text-xs text-right">Clicks</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {campaigns.map((c, i) => (
                <TableRow key={i} className="border-zinc-800">
                  <TableCell className="text-zinc-200 text-sm max-w-xs truncate">{c.campaign_name}</TableCell>
                  <TableCell className="text-zinc-300 text-sm text-right">{fmt(c.spend, "$")}</TableCell>
                  <TableCell className="text-zinc-300 text-sm text-right">{fmt(c.leads)}</TableCell>
                  <TableCell className="text-zinc-300 text-sm text-right">{fmt(c.cpl, "$")}</TableCell>
                  <TableCell className="text-zinc-300 text-sm text-right">{fmt(c.roas)}</TableCell>
                  <TableCell className="text-zinc-300 text-sm text-right">{fmt(c.clicks)}</TableCell>
                </TableRow>
              ))}
              {campaigns.length === 0 && (
                <TableRow>
                  <TableCell colSpan={6} className="text-zinc-500 text-sm text-center py-8">
                    No campaign data for this period
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
