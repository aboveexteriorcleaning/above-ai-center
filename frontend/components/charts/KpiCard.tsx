import { Card, CardContent } from "@/components/ui/card";

interface KpiCardProps {
  label: string;
  value: string | number | null | undefined;
  prefix?: string;
  suffix?: string;
  sublabel?: string;
}

export function KpiCard({ label, value, prefix = "", suffix = "", sublabel }: KpiCardProps) {
  const display = value == null ? "—" : `${prefix}${value}${suffix}`;

  return (
    <Card className="bg-zinc-900 border-zinc-800">
      <CardContent className="pt-5 pb-4">
        <p className="text-xs text-zinc-400 uppercase tracking-wider mb-1">{label}</p>
        <p className="text-2xl font-semibold text-white">{display}</p>
        {sublabel && <p className="text-xs text-zinc-500 mt-1">{sublabel}</p>}
      </CardContent>
    </Card>
  );
}
