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
    <div className="flex flex-wrap gap-2">
      {data.map((row) => (
        <div key={row.source} className="flex items-center gap-1.5 text-xs text-zinc-400">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 inline-block" />
          <span className="capitalize">{row.source}</span>
          <span className="text-zinc-600">{timeAgo(row.completed_at)}</span>
        </div>
      ))}
    </div>
  );
}
