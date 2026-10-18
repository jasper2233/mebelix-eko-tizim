// Kromka stansiyasi — JONLI o'lchov oqimi (admin panel).
//
// «Qanday o'lchamli detal o'tdi» degan savolga javob o'sha lahzada kerak, shuning uchun
// yangi o'lchov WS (`kromka.measure`) bilan darhol qo'shiladi — 60 soniyalik poll kutilmaydi.
// Boshlang'ich ro'yxat sahifa ochilganda bir marta so'raladi.
//
// Stansiya ulanmagan tsexda butun blok chizilmaydi: ro'yxat bo'sh bo'lsa hech narsa yo'q.

import { useQuery } from "@tanstack/react-query"
import { useCallback, useState } from "react"

import { type KromkaMeasurementRow, MachinesService } from "@/client"
import { useMesWs } from "@/hooks/useMesWs"
import { KROMKA_VERDICT_LABELS, KROMKA_VERDICT_STYLE } from "@/lib/mes"
import { cn } from "@/lib/utils"

/** Ekranda turadigan qatorlar. Tarix bazada — bu faqat «hozir nima o'tyapti» oynasi. */
const LIMIT = 20

/** Pico kodi: OK dan boshqasi — datchik muammosi, ko'zga tashlanib tursin. */
const CODE_STYLE: Record<string, string> = {
  FARQ: "bg-amber-200 text-amber-900",
  FAQAT1: "bg-orange-200 text-orange-900",
  FAQAT2: "bg-orange-200 text-orange-900",
}

const clock = (iso: string) =>
  new Date(iso).toLocaleTimeString("uz-UZ", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  })

export function KromkaLive() {
  const { data } = useQuery({
    queryKey: ["machines", "kromka-measurements"],
    queryFn: async () =>
      (await MachinesService.readKromkaMeasurementFeed()).data,
    // WS asosiy manba; poll — soket uzilib qolgan holat uchun zaxira
    refetchInterval: 60_000,
  })
  // WS'dan kelganlar ro'yxat BOSHIGA qo'shiladi; so'rov javobi esa quyruq bo'lib qoladi
  const [live, setLive] = useState<KromkaMeasurementRow[]>([])

  useMesWs(
    useCallback((event) => {
      if (event.type !== "kromka.measure") return
      const p = event.payload as unknown as KromkaMeasurementRow
      setLive((old) => [p, ...old].slice(0, LIMIT))
    }, []),
  )

  const rows = [...live, ...(data ?? [])].slice(0, LIMIT)
  if (!rows.length) return null

  return (
    <section className="mt-8">
      <h2 className="mb-2 text-sm font-semibold">
        Kromka stansiyasi — jonli o'lchov
        <span className="ml-2 font-normal text-muted-foreground">
          detal datchiklardan o'tishi bilan chiqadi
        </span>
      </h2>
      <ul className="divide-y rounded-lg border">
        {rows.map((r, i) => (
          <li
            key={`${r.machine_id}-${r.at}-${r.length_mm ?? i}`}
            className={cn(
              "flex flex-wrap items-baseline gap-x-4 gap-y-1 px-3 py-2",
              // Eng yangisi bir marta yashil uriladi — devordagi tabloda ishlatiladigan
              // belgi bilan bir xil (`index.css`)
              i === 0 && live.length > 0 && "animate-cell-flash",
            )}
          >
            <span className="num w-20 shrink-0 text-xs text-muted-foreground">
              {clock(r.at)}
            </span>
            <span className="num w-28 shrink-0 text-xl font-black">
              {r.length_mm?.toFixed(1) ?? "—"}
              <span className="ml-1 text-xs font-bold">mm</span>
            </span>
            <span
              className={cn(
                "shrink-0 rounded-md px-2 py-0.5 text-xs font-black",
                KROMKA_VERDICT_STYLE[r.verdict] ?? "bg-muted",
              )}
            >
              {KROMKA_VERDICT_LABELS[r.verdict] ?? r.verdict}
            </span>
            {/* Paket: o'lchov bir nechta kichik bo'lakning yig'indisi (docs/12 §4.26) */}
            {r.pack_n != null && (
              <span className="shrink-0 rounded-md bg-sky-100 px-2 py-0.5 text-xs font-black text-sky-900">
                paket {r.pack_n} ta
              </span>
            )}
            {/* Datchik muammosi bo'lgandagina Pico kodi ko'rsatiladi */}
            {r.code !== "OK" && (
              <span
                className={cn(
                  "shrink-0 rounded-md px-2 py-0.5 text-xs font-black",
                  CODE_STYLE[r.code] ?? "bg-muted text-muted-foreground",
                )}
              >
                {r.code}
              </span>
            )}
            {/* Kutilgan o'lcham — qaysi tomon o'tgani shundan ko'rinadi */}
            {r.expected_mm != null && (
              <span className="num text-xs text-muted-foreground">
                kutilgan {r.expected_mm.toFixed(0)}
                {r.delta_mm != null &&
                  ` · farq ${r.delta_mm > 0 ? "+" : ""}${r.delta_mm.toFixed(1)}`}
              </span>
            )}
            <span className="truncate text-xs text-muted-foreground">
              {r.part_name ?? "—"}
              {r.qr_text ? ` · ${r.qr_text}` : ""}
            </span>
            <span className="ml-auto truncate text-xs text-muted-foreground">
              {r.machine_name}
            </span>
          </li>
        ))}
      </ul>
    </section>
  )
}
