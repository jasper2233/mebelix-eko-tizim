// Barkod yorliqlari (EKO TZ §4.4): kirim hujjati (`?doc=`) yoki pozitsiya (`?item=`) birliklari.
// Har yorliq — alohida sahifa (58×40 mm yorliq printeri), QR ichida tizim barkodi `EK…`:
// sexdagi skanerlar 2D (detal cheklari ham QR).

import { useQuery } from "@tanstack/react-query"
import { createFileRoute, Link } from "@tanstack/react-router"
import { Printer } from "lucide-react"
import { QRCodeSVG } from "qrcode.react"

import { OmborService } from "@/client"
import { PageHeader } from "@/components/Common/PageHeader"
import { QueryError } from "@/components/Common/QueryError"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { requireAccess } from "@/lib/guards"
import { isWarehouseStaff } from "@/lib/mes"
import { fmtQty } from "@/lib/warehouse"

export const Route = createFileRoute("/_layout/warehouse/yorliq")({
  component: YorliqPage,
  beforeLoad: requireAccess(isWarehouseStaff),
  validateSearch: (
    s: Record<string, unknown>,
  ): { doc?: number; item?: number } => ({
    doc: Number(s.doc) || undefined,
    item: Number(s.item) || undefined,
  }),
  head: () => ({ meta: [{ title: "Yorliqlar | MebeliX" }] }),
})

function YorliqPage() {
  const { doc, item } = Route.useSearch()
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["ombor", "birliklar", { doc, item }],
    queryFn: async () =>
      (
        await OmborService.listBirliklar({
          query: { doc_id: doc ?? null, item_id: item ?? null },
        })
      ).data,
    enabled: doc != null || item != null,
  })
  // Faqat ombordagilar: sexdagi rulon yorlig'i allaqachon unda yopishgan
  const rows = (data ?? []).filter((u) => u.joy === "ombor")
  return (
    <div className="flex flex-col gap-4">
      <div className="print-hide flex flex-wrap items-end gap-3">
        <PageHeader
          title="Barkod yorliqlari"
          description={`${rows.length} ta yorliq — har biri alohida sahifada (58×40 mm)`}
        />
        <Button
          className="ml-auto"
          onClick={() => window.print()}
          disabled={!rows.length}
        >
          <Printer /> Chop etish
        </Button>
      </div>
      {doc == null && item == null ? (
        <p className="text-muted-foreground">
          Yorliqlar kirim hujjati yoki pozitsiya kartochkasidan ochiladi.{" "}
          <Link to="/warehouse/docs" className="underline">
            Hujjatlar
          </Link>
        </p>
      ) : isError ? (
        <QueryError onRetry={refetch} />
      ) : isLoading ? (
        <Skeleton className="h-40" />
      ) : (
        <div className="flex flex-wrap gap-3 print:block">
          {rows.map((u) => (
            <div
              key={u.id}
              className="flex h-[40mm] w-[58mm] items-center gap-2 overflow-hidden rounded border bg-white p-[2mm] text-black print:break-after-page print:rounded-none print:border-0"
            >
              <QRCodeSVG value={u.barkod ?? ""} size={96} level="M" />
              <div className="flex min-w-0 flex-col gap-0.5 text-[9pt] leading-tight">
                <b className="font-mono text-[11pt]">{u.barkod}</b>
                <span className="line-clamp-3">{u.item_name}</span>
                <span className="font-mono text-[8pt]">{u.item_code}</span>
                <b>
                  {fmtQty(u.hajm)} {u.unit ?? ""}
                </b>
                {u.ishlab_kod && (
                  <span className="font-mono text-[7pt]">{u.ishlab_kod}</span>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
