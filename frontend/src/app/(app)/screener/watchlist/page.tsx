import { PageHeader } from "@/components/common/PageHeader";
import { AddWatchlistButton } from "@/components/watchlist/AddWatchlistButton";
import { WatchlistTable } from "@/components/watchlist/WatchlistTable";

// 自選股清單頁
export default function WatchlistPage() {
  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        title="自選股清單"
        description="管理你關注的股票；後續可從這裡發起分析"
        actions={<AddWatchlistButton />}
      />
      <WatchlistTable />
    </div>
  );
}
