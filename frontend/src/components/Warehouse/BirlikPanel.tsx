// Pozitsiyaning barkodli birliklari (EKO TZ §4.4): ombordagi list/rulonlar, sexdagi rulon
// qoldiqlari va yorlig'i yo'q eski qoldiq. Yorliqsiz qoldiq bir marta yorliqlanadi — keyin
// material faqat skaner bilan beriladi. Metrdagi pozitsiyada standart rulon uzunligi ham shu yerda.

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Link } from "@tanstack/react-router"
import { Printer, Tag } from "lucide-react"
import { useState } from "react"

import { type CatalogRow, CatalogService, OmborService } from "@/client"
import { Button } from "@/components/ui/button"
import { cardSurface } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { LoadingButton } from "@/components/ui/loading-button"
import { cn } from "@/lib/utils"
import { fmtQty, num, parseNum } from "@/lib/warehouse"
import { handleError } from "@/utils"

//: Backend `services/birlik.py: tracked` bilan bir xil
export const isTracked = (r: {
  catalog?: CatalogRow["catalog"] | null
  unit?: CatalogRow["unit"]
}) => r.catalog === "M" || (r.catalog !== "X" && r.unit === "metr")

export function BirlikPanel({
  item,
  canWrite,
}: {
  item: CatalogRow
  canWrite: boolean
}) {
  const queryClient = useQueryClient()
  const rulon = item.unit === "metr"
  const { data } = useQuery({
    queryKey: ["ombor", "birliklar", { item: item.id }],
    queryFn: async () =>
      (await OmborService.listBirliklar({ query: { item_id: item.id } })).data,
  })
  const units = data ?? []
  const ombor = units.filter((u) => u.joy === "ombor")
  const sex = units.filter((u) => u.joy === "sex")
  const yorliqli = units.reduce((s, u) => s + num(u.qoldiq), 0)
  const yorliqsiz = Math.max(0, num(item.quantity) - yorliqli)

  const [hajm, setHajm] = useState(
    item.birlik_hajm != null ? String(num(item.birlik_hajm)) : "",
  )
  const [soni, setSoni] = useState("")
  const [kod, setKod] = useState("")
  const done = () => {
    queryClient.invalidateQueries({ queryKey: ["ombor"] })
    queryClient.invalidateQueries({ queryKey: ["catalog"] })
  }
  const saveHajm = useMutation({
    mutationFn: () =>
      CatalogService.updateCatalogItem({
        path: { item_id: item.id },
        body: { birlik_hajm: parseNum(hajm) ? String(parseNum(hajm)) : null },
      }),
    onSuccess: done,
    onError: handleError,
  })
  const yorliq = useMutation({
    mutationFn: () =>
      OmborService.yorliqBirlik({
        body: {
          item_id: item.id,
          soni: Math.trunc(parseNum(soni) ?? 0),
          hajm: rulon && parseNum(hajm) ? String(parseNum(hajm)) : null,
          ishlab_kod: kod.trim() || null,
        },
      }),
    onSuccess: () => {
      setSoni("")
      done()
    },
    onError: handleError,
  })
  const n = Math.trunc(parseNum(soni) ?? 0)

  return (
    <section className={cn(cardSurface, "flex flex-col gap-3 p-4")}>
      <div className="flex flex-wrap items-center gap-x-6 gap-y-1 text-sm">
        <h2 className="font-semibold">Barkodli birliklar</h2>
        <span>
          Omborda: <b className="num">{ombor.length}</b>{" "}
          {rulon ? "rulon" : "ta"}
        </span>
        {rulon && (
          <span>
            Sexda: <b className="num">{sex.length}</b> rulon ·{" "}
            <span className="num">
              {fmtQty(sex.reduce((s, u) => s + num(u.qoldiq), 0))} m
            </span>
          </span>
        )}
        <span className={cn(yorliqsiz > 0 && "font-semibold text-amber-700")}>
          Yorliqsiz: <span className="num">{fmtQty(yorliqsiz)}</span>{" "}
          {item.unit ?? ""}
        </span>
        {ombor.length > 0 && (
          <Button size="sm" variant="outline" className="ml-auto" asChild>
            <Link to="/warehouse/yorliq" search={{ item: item.id }}>
              <Printer /> Yorliqlarni chop etish
            </Link>
          </Button>
        )}
      </div>
      {canWrite && rulon && (
        <label
          htmlFor="birlik-hajm"
          className="flex flex-wrap items-center gap-2 text-sm"
        >
          Bitta rulon, metr
          <Input
            id="birlik-hajm"
            className="num h-8 w-28 text-right"
            inputMode="decimal"
            placeholder="masalan 100"
            value={hajm}
            onChange={(e) => setHajm(e.target.value.replace(/[^0-9.,]/g, ""))}
          />
          <LoadingButton
            size="sm"
            variant="outline"
            loading={saveHajm.isPending}
            disabled={
              (parseNum(hajm) ?? null) === num(item.birlik_hajm ?? undefined)
            }
            onClick={() => saveHajm.mutate()}
          >
            Saqlash
          </LoadingButton>
          <span className="text-xs text-muted-foreground">
            kirimda miqdor shu uzunlikdagi rulonlarga bo'linadi
          </span>
        </label>
      )}
      {canWrite && yorliqsiz > 0 && (
        <div className="flex flex-wrap items-center gap-2 rounded border border-amber-300 bg-amber-50 p-2 text-sm">
          <Tag className="size-4 text-amber-800" />
          Eski qoldiqni yorliqlash:
          <Input
            className="num h-8 w-20 text-right"
            inputMode="numeric"
            placeholder="soni"
            value={soni}
            onChange={(e) => setSoni(e.target.value.replace(/[^0-9]/g, ""))}
          />
          {rulon ? `rulon × ${hajm || "?"} m` : `ta ${item.unit ?? ""}`}
          <Input
            className="h-8 w-44 font-mono"
            placeholder="zavod kodi (ixtiyoriy)"
            value={kod}
            onChange={(e) => setKod(e.target.value)}
          />
          <LoadingButton
            size="sm"
            loading={yorliq.isPending}
            disabled={n < 1 || (rulon && !parseNum(hajm))}
            onClick={() => yorliq.mutate()}
          >
            Barkod yaratish
          </LoadingButton>
        </div>
      )}
      {units.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {units.slice(0, 60).map((u) => (
            <span
              key={u.id}
              className={cn(
                "rounded border px-1.5 py-0.5 font-mono text-xs",
                u.joy === "sex" && "border-emerald-400 bg-emerald-50",
              )}
              title={u.joy === "sex" ? "sexda" : "omborda"}
            >
              {u.barkod}
              {rulon && ` · ${fmtQty(u.qoldiq)} m`}
            </span>
          ))}
          {units.length > 60 && (
            <span className="text-xs text-muted-foreground">
              +{units.length - 60}
            </span>
          )}
        </div>
      )}
    </section>
  )
}
