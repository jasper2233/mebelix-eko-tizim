import { ItemsService } from "@/client"

export function getItemsQueryOptions() {
  return {
    queryFn: () => ItemsService.readItems({ skip: 0, limit: 100 }),
    queryKey: ["items"] as const,
  }
}
