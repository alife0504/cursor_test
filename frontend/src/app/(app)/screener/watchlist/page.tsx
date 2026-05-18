import { AddWatchlistButton } from "@/components/watchlist/AddWatchlistButton";
import { WatchlistTable } from "@/components/watchlist/WatchlistTable";

// Phase 16 § C:自選股清單頁
export default function WatchlistPage() {
  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">自選股清單</h1>
          <p className="text-sm text-muted-foreground">
            管理你關注的股票;後續可從這裡發起分析
          </p>
        </div>
        <AddWatchlistButton />
      </div>
      <WatchlistTable />
    </div>
  );
}
