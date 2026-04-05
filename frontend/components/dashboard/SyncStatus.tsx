interface SyncRow {
  source: string;
  status: string;
  records_upserted: number;
  completed_at: string;
  duration_seconds: number;
}

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

export function SyncStatus({ data }: { data: SyncRow[] }) {
  return (
    <div className="flex flex-wrap gap-3">
      {data.map((row) => (
        <div key={row.source} className="flex items-center gap-1.5 text-xs" style={{ color: "#6b6f8a" }}>
          <span
            className="w-1.5 h-1.5 rounded-full inline-block"
            style={{ background: "#41bfec", boxShadow: "0 0 6px rgba(65,191,236,0.6)" }}
          />
          <span className="capitalize" style={{ color: "#a0a3b8" }}>{row.source}</span>
          <span>{timeAgo(row.completed_at)}</span>
        </div>
      ))}
    </div>
  );
}
