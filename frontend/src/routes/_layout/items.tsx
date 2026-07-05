import { useSuspenseQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { Search } from "lucide-react"
import { Suspense } from "react"

import { DataTable } from "@/components/Common/DataTable"
import AddItem from "@/components/Items/AddItem"
import { columns } from "@/components/Items/columns"
import PendingItems from "@/components/Pending/PendingItems"
import { getItemsQueryOptions } from "@/queries/items"

export const Route = createFileRoute("/_layout/items")({
  component: Items,
  head: () => ({
    meta: [
      {
        title: "Elementlar - FastAPI Cloud",
      },
    ],
  }),
})

function ItemsTableContent() {
  const { data: items } = useSuspenseQuery(getItemsQueryOptions())

  if (items.data.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center text-center py-12">
        <div className="rounded-full bg-muted p-4 mb-4">
          <Search className="h-8 w-8 text-muted-foreground" />
        </div>
        <h3 className="text-lg font-semibold">Sizda hali element yo'q</h3>
        <p className="text-muted-foreground">
          Boshlash uchun yangi element qo'shing
        </p>
      </div>
    )
  }

  return <DataTable columns={columns} data={items.data} />
}

function ItemsTable() {
  return (
    <Suspense fallback={<PendingItems />}>
      <ItemsTableContent />
    </Suspense>
  )
}

function Items() {
  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Elementlar</h1>
          <p className="text-muted-foreground">
            Elementlarni yarating va boshqaring
          </p>
        </div>
        <AddItem />
      </div>
      <ItemsTable />
    </div>
  )
}
