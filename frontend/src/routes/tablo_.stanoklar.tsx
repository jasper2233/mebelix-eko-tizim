// STANOK TAXTASI: tsex zalidagi TV ekran — Pico ulangan stanoklarning jonli holati
// va BUGUNGI OEE si. Buyurtma taxtasidan (`/tablo`) alohida sahifa: bitta ekranda
// ikkalasini siqish kartalarni o'qib bo'lmas darajada kichraytirardi.
//
// Raqamlar «Stanok vaqti» hisobotidan keladi (server o'sha handlerni bugungi kun
// uchun chaqiradi) — devordagi taxta va hisobot hech qachon ikki xil raqam
// ko'rsatmaydi.
//
// DIZAYN. Karta — tsexning o'z buyumi: kesilgan PANEL, chap chekkasida kromka
// lentasi. Holat aynan shu lentaning rangi bilan beriladi (eng uzoqdan ko'rinadigan
// element), panelning o'zi tinch qoladi. Ekranda YAGONA oltin raqam bor — OEE:
// taxtaga qaragan odam avval uni, keyin qolganini o'qiydi. Sarlavhada ortiqcha
// izoh yo'q: nom, soat va qaytish havolasi — xolos.

import { useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute, Link } from "@tanstack/react-router"
import { useCallback, useEffect, useState } from "react"

import { type TabloMachineRow, TabloService } from "@/client"
import { BrandLoader } from "@/components/Common/BrandLoader"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { useMesWs } from "@/hooks/useMesWs"
import { useThrottled } from "@/hooks/useThrottled"
import { requireAuth } from "@/lib/guards"
import {
  ANDON_STATE_LABELS,
  DEFECT_STATUS_LABELS,
  DOWNTIME_KIND_LABELS,
  KROMKA_VERDICT_LABELS,
  OPERATOR_ROLES,
} from "@/lib/mes"
import { cn } from "@/lib/utils"
import { getCurrentUserQueryOptions } from "@/queries/users"

export const Route = createFileRoute("/tablo_/stanoklar")({
  component: StanoklarPage,
  head: () => ({ meta: [{ title: "Stanoklar | MebeliX" }] }),
  beforeLoad: async () => {
    await requireAuth()
  },
})

/** Kromka lentasining rangi = stanok holati. Holat `null` bo'lsa — Pico yoki
 *  agentdan 90 soniyadan beri xabar yo'q: lenta CHIZIQLI bo'ladi va «o'chiq»
 *  bilan aralashmaydi. Nosozlik aynan shu farqda bilinadi. */
const BAND: Record<string, string> = {
  PROCESSING: "bg-[#3FB27F]",
  AWAIT_PART: "bg-[#3FB27F]",
  IDLE: "bg-[#E2A32D]",
  STOPPED: "bg-[#D2751F]",
  FAULT: "bg-[#D9534F]",
  OFF: "bg-[#4A5464]",
  BOOT: "bg-[#4E8FD1]",
}
const BAND_LOST =
  "bg-[#39424F] [background-image:repeating-linear-gradient(135deg,transparent,transparent_9px,rgba(255,255,255,.10)_9px,rgba(255,255,255,.10)_18px)]"
const HOLAT_MATN: Record<string, string> = {
  PROCESSING: "text-[#6ED4A6]",
  AWAIT_PART: "text-[#6ED4A6]",
  IDLE: "text-[#F0C060]",
  STOPPED: "text-[#EE9A4D]",
  FAULT: "text-[#F08581]",
  OFF: "text-[#8B95A5]",
  BOOT: "text-[#7FB4E6]",
}

const soat = (s: number) =>
  `${Math.floor(s / 3600)}:${String(Math.floor((s % 3600) / 60)).padStart(2, "0")}`
const foiz = (v: number | null | undefined) => (v == null ? "—" : `${v}%`)

/** "14 daq" / "2 soat 5 daq" — devor ekranida soniya keraksiz, sana o'qilmaydi. */
function davomiyligi(iso: string | null | undefined): string {
  if (!iso) return ""
  const d = Math.floor(
    Math.max(0, (Date.now() - new Date(iso).getTime()) / 60000),
  )
  if (d < 60) return `${d} daq`
  return `${Math.floor(d / 60)} soat ${d % 60} daq`
}

/** OEE ning uch tarkibi: nom, ustun, foiz. Ustun raqamdan oldin o'qiladi —
 *  qaysi biri stanokni pastga tortayotgani bir qarashda ko'rinadi. */
function Qism({
  nom,
  qiymat,
  rang,
}: {
  nom: string
  qiymat: number | null | undefined
  rang: string
}) {
  const pct = qiymat == null ? 0 : Math.max(0, Math.min(100, qiymat))
  return (
    <div className="flex items-center gap-3">
      <span className="w-28 shrink-0 text-base text-[#8B95A5]">{nom}</span>
      <span className="h-2 min-w-0 flex-1 overflow-hidden rounded-sm bg-[#232B36]">
        <span
          className={cn("block h-full rounded-sm", rang)}
          style={{ width: `${pct}%` }}
        />
      </span>
      <span className="num w-16 shrink-0 text-right text-xl font-bold text-[#E7EAEF]">
        {foiz(qiymat)}
      </span>
    </div>
  )
}

/** Chapda nima, o'ngda qancha. «A · B · C» satri o'rniga — uzoqdan raqamlar
 *  bir-biriga qo'shilib ketmaydi. */
function Fakt({ nom, qiymat }: { nom: string; qiymat: string }) {
  return (
    <div className="flex items-baseline gap-2">
      <span className="text-base text-[#8B95A5]">{nom}</span>
      <span className="num text-lg font-semibold text-[#C8D0DC]">{qiymat}</span>
    </div>
  )
}

function MachineCard({
  row,
  onOpen,
}: {
  row: TabloMachineRow
  onOpen: () => void
}) {
  const ishlayapti = row.state === "PROCESSING" || row.state === "AWAIT_PART"
  const holat = row.state
    ? (ANDON_STATE_LABELS[row.state] ?? row.state)
    : "Aloqa yo'q"
  const mos = row.mos_count ?? 0
  const nomos = row.nomos_count ?? 0

  return (
    <button
      type="button"
      onClick={onOpen}
      className="group flex w-full min-w-0 overflow-hidden rounded-md bg-[#171C24] text-left outline-none ring-1 ring-[#232B36] focus-visible:ring-2 focus-visible:ring-[#D9B34A]"
    >
      {/* Kromka lentasi — holatning o'zi. Kartadagi eng uzoqdan ko'rinadigan narsa. */}
      <span
        className={cn(
          "w-4 shrink-0",
          row.state ? (BAND[row.state] ?? BAND.OFF) : BAND_LOST,
        )}
      />

      <div className="flex min-w-0 flex-1 flex-col gap-5 px-6 py-5">
        <div className="flex min-w-0 items-baseline gap-4">
          <h2 className="truncate text-3xl font-black tracking-tight text-[#E7EAEF]">
            {row.machine_name}
          </h2>
          <span
            className={cn(
              "ml-auto flex shrink-0 items-center gap-2 text-2xl font-bold",
              row.state ? (HOLAT_MATN[row.state] ?? "") : "text-[#8B95A5]",
            )}
          >
            {ishlayapti && (
              <span className="size-2.5 rounded-full bg-current motion-safe:animate-pulse" />
            )}
            {holat}
          </span>
          {row.since && (
            <span className="num shrink-0 text-xl text-[#8B95A5]">
              {davomiyligi(row.since)}
            </span>
          )}
        </div>

        {/* Smena — kim javobgar. Ochilmagan bo'lsa sabab ham so'ralmaydi va
            hisobot ham buziladi, shuning uchun bu qizil xabar. */}
        <p
          className={cn(
            "-mt-3 truncate text-xl",
            row.crew.length ? "text-[#C8D0DC]" : "text-[#F08581]",
          )}
        >
          {row.crew.length ? row.crew.join(", ") : "Smena ochilmagan"}
        </p>

        {/* Yagona oltin raqam — OEE. Uch tarkibi yonida, ustunlari bilan. */}
        <div className="flex items-center gap-8">
          {/* Kenglik QOTIRILGAN: «1.2%», «1%» va «—» har xil joy egallaydi va
              ustunlar kartadan kartaga siljib ketardi — devor ekranida bu
              darhol ko'zga tashlanadi */}
          <div className="w-40 shrink-0">
            {/* Oltin — FAQAT haqiqiy raqam uchun. Hisoblanmagan OEE («—») kulrang:
                aks holda bo'sh chiziq ekrandagi eng qimmat rangni egallab turardi */}
            <div
              className={cn(
                "num text-6xl font-black leading-none",
                row.oee_pct == null ? "text-[#4A5464]" : "text-[#D9B34A]",
              )}
            >
              {foiz(row.oee_pct)}
            </div>
            <div className="mt-1.5 text-base text-[#8B95A5]">OEE</div>
          </div>
          <div className="flex min-w-0 flex-1 flex-col gap-2">
            <Qism
              nom="Availability"
              qiymat={row.availability_pct}
              rang="bg-[#4E8FD1]"
            />
            <Qism
              nom="Performance"
              qiymat={row.performance_pct}
              rang="bg-[#9B7FD4]"
            />
            <Qism nom="Quality" qiymat={row.quality_pct} rang="bg-[#3FB27F]" />
          </div>
        </div>

        {/* Reja vaqti yo'q (ish jadvalida dam olish kuni yoki smena hali boshlanmagan) — OEE
            hisoblanmaydi va «Ishladi 0:00» stanok ishlab turgan bo'lsa ham buzuqdek ko'rinardi */}
        {row.planned_s > 0 ? (
          <div className="flex flex-wrap items-baseline gap-x-8 gap-y-2 border-t border-[#232B36] pt-4">
            <Fakt nom="Ishladi" qiymat={soat(row.run_s)} />
            <Fakt nom="To'xtadi" qiymat={soat(row.stop_s)} />
            <Fakt nom="Detal" qiymat={String(row.parts)} />
            {row.defects > 0 && (
              <Fakt nom="Brak" qiymat={String(row.defects)} />
            )}
          </div>
        ) : (
          <p className="border-t border-[#232B36] pt-4 text-lg text-[#8B95A5]">
            Bugun reja vaqti yo'q — dam olish kuni yoki smena hali boshlanmagan.
            OEE ish jadvali bo'yicha hisoblanadi.
          </p>
        )}

        {/* KROMKA: bugun nechta o'lchov kutilgan tomonga tushdi, nechtasi yo'q */}
        {(mos > 0 || nomos > 0 || row.last_mm != null) && (
          <div className="flex flex-wrap items-baseline gap-x-6 gap-y-1">
            <span className="num text-lg text-[#6ED4A6]">{mos} mos</span>
            <span
              className={cn(
                "num text-lg",
                nomos > 0 ? "text-[#F08581]" : "text-[#5D6675]",
              )}
            >
              {nomos} mos emas
            </span>
            {row.last_mm != null && (
              <span className="num truncate text-lg text-[#8B95A5]">
                oxirgi {row.last_mm.toFixed(0)} mm
                {row.last_verdict
                  ? `, ${(KROMKA_VERDICT_LABELS[row.last_verdict] ?? row.last_verdict).toLowerCase()}`
                  : ""}
              </span>
            )}
          </div>
        )}

        {row.pending_reasons > 0 && (
          <p className="truncate rounded-sm bg-[#D9534F]/15 px-4 py-2.5 text-lg font-semibold text-[#F08581]">
            {row.pending_reasons} to'xtashga sabab kiritilmagan
          </p>
        )}
      </div>
    </button>
  )
}

const QUERY_KEY = ["tablo", "machines"]
// Kartani bosganda ochiladigan oyna. Ro'yxat bilan BIRGA yangilanadi (WS + poll): ilgari oyna
// ochilgan lahzadagi raqamlarda qotib qolardi — usta uni ochiq qoldirib kuzatsa ham o'zgarmasdi
const DIALOG_KEY = ["tablo", "machine"]

/** Kartani bosganda: shu stanokning kunlik/haftalik/oylik OEE si va oxirgi
 *  hodisalari. Devor ekrani uchun emas — usta yoki menejer bosadi, shuning
 *  uchun bu yerda mayda shrift va ro'yxatlar bo'lishi mumkin. */
function MachineDialog({
  machineId,
  onClose,
}: {
  machineId: number | null
  onClose: () => void
}) {
  const { data, isLoading } = useQuery({
    queryKey: [...DIALOG_KEY, machineId],
    queryFn: async () =>
      (
        await TabloService.readTabloMachine({
          path: { machine_id: machineId as number },
        })
      ).data,
    enabled: machineId != null,
    refetchInterval: 60_000, // WS uzilgan bo'lsa ham
  })

  return (
    <Dialog open={machineId != null} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="max-h-[90vh] max-w-4xl overflow-y-auto border-[#232B36] bg-[#12161D] text-[#E7EAEF] sm:max-w-4xl">
        <DialogHeader>
          <DialogTitle className="flex items-baseline gap-3 text-3xl font-black tracking-tight">
            {data?.machine_name ?? "Stanok"}
            <span className="text-lg font-normal text-[#8B95A5]">
              {data?.post_name}
            </span>
          </DialogTitle>
        </DialogHeader>

        {isLoading || !data ? (
          <BrandLoader />
        ) : (
          <div className="space-y-7">
            <table className="w-full">
              <thead className="text-left text-sm text-[#8B95A5]">
                <tr>
                  <th className="pb-2 font-normal">Davr</th>
                  <th className="pb-2 text-right font-normal">Reja</th>
                  <th className="pb-2 text-right font-normal">Ishladi</th>
                  <th className="pb-2 text-right font-normal">Availability</th>
                  <th className="pb-2 text-right font-normal">Performance</th>
                  <th className="pb-2 text-right font-normal">Quality</th>
                  <th className="pb-2 text-right font-normal">OEE</th>
                  <th className="pb-2 text-right font-normal">Detal</th>
                  <th className="pb-2 text-right font-normal">Brak</th>
                </tr>
              </thead>
              <tbody className="num text-base">
                {data.periods.map((p) => (
                  <tr key={p.label} className="border-t border-[#232B36]">
                    <td className="py-2.5 font-semibold">{p.label}</td>
                    <td className="py-2.5 text-right text-[#8B95A5]">
                      {soat(p.planned_s)}
                    </td>
                    <td className="py-2.5 text-right text-[#8B95A5]">
                      {soat(p.run_s)}
                    </td>
                    <td className="py-2.5 text-right">
                      {foiz(p.availability_pct)}
                    </td>
                    <td className="py-2.5 text-right">
                      {foiz(p.performance_pct)}
                    </td>
                    <td className="py-2.5 text-right">{foiz(p.quality_pct)}</td>
                    <td className="py-2.5 text-right text-xl font-black text-[#D9B34A]">
                      {foiz(p.oee_pct)}
                    </td>
                    <td className="py-2.5 text-right text-[#8B95A5]">
                      {p.parts}
                    </td>
                    <td className="py-2.5 text-right text-[#8B95A5]">
                      {p.defects}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>

            <Section title="To'xtashlar va avariyalar">
              {data.stops.length === 0 ? (
                <Empty>To'xtash yozilmagan.</Empty>
              ) : (
                data.stops.map((r) => (
                  <Row
                    key={`${r.started_at}-${r.kind}`}
                    left={`${vaqt(r.started_at)}  ${DOWNTIME_KIND_LABELS[r.kind] ?? r.kind}`}
                    right={soat(r.seconds)}
                    note={
                      r.reason ??
                      (r.ended_at ? "sabab kiritilmagan" : "davom etyapti")
                    }
                    tone={r.kind === "fault" ? "text-[#F08581]" : undefined}
                  />
                ))
              )}
            </Section>

            <Section title="Brak">
              {data.defects.length === 0 ? (
                <Empty>Brak qayd qilinmagan.</Empty>
              ) : (
                data.defects.map((r) => (
                  <Row
                    key={`${r.at}-${r.qr_text}`}
                    left={`${vaqt(r.at)}  ${r.part_name}`}
                    right={DEFECT_STATUS_LABELS[r.status] ?? r.status}
                    note={`${r.reason}, ${r.qr_text}`}
                    tone="text-[#F08581]"
                  />
                ))
              )}
            </Section>

            <Section title="Oxirgi bajarilgan ishlar">
              {data.recent_scans.length === 0 ? (
                <Empty>Bu stanokda skan yo'q.</Empty>
              ) : (
                data.recent_scans.map((r) => (
                  <Row
                    key={`${r.at}-${r.qr_text}`}
                    left={`${vaqt(r.at)}  ${r.part_name}`}
                    right={r.employee ?? ""}
                    note={r.qr_text}
                  />
                ))
              )}
            </Section>
          </div>
        )}
      </DialogContent>
    </Dialog>
  )
}

function Section({
  title,
  children,
}: {
  title: string
  children: React.ReactNode
}) {
  return (
    <section>
      <h3 className="mb-2 text-base font-semibold text-[#C8D0DC]">{title}</h3>
      <div className="divide-y divide-[#1D232C] rounded-sm bg-[#0E1116]">
        {children}
      </div>
    </section>
  )
}

const Empty = ({ children }: { children: React.ReactNode }) => (
  <p className="px-4 py-3 text-[#5D6675]">{children}</p>
)

function Row({
  left,
  right,
  note,
  tone,
}: {
  left: string
  right: string
  note?: string
  tone?: string
}) {
  return (
    <div className="flex items-baseline gap-4 px-4 py-2.5">
      <span className={cn("num min-w-0 flex-1 truncate", tone)}>{left}</span>
      {note && (
        <span className="num hidden truncate text-sm text-[#5D6675] sm:block">
          {note}
        </span>
      )}
      <span className="num shrink-0 font-semibold text-[#C8D0DC]">{right}</span>
    </div>
  )
}

const vaqt = (iso: string) =>
  new Date(iso).toLocaleString("uz-UZ", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  })

function StanoklarPage() {
  const queryClient = useQueryClient()
  const { data, isLoading } = useQuery({
    queryKey: QUERY_KEY,
    queryFn: async () => (await TabloService.readTabloMachines()).data,
    // Devor ekrani soatlab ochiq turadi: WS asosiy manba, poll — soket uzilgani uchun
    refetchInterval: 60_000,
  })

  // WS har hodisada so'rov yubormaydi: hisob bir kunlik oraliqni qayta yuritadi,
  // kromkada esa har detalda xabar keladi. Eng tez 15 soniyada bir marta —
  // oynadagi OXIRGI hodisa ham oxirida olinadi (`useThrottled`: leading + trailing)
  const refresh = useThrottled(() => {
    queryClient.invalidateQueries({ queryKey: QUERY_KEY })
    // Faqat OCHIQ oyna qayta so'raladi (yopilgani faol emas — invalidate uni so'ramaydi)
    queryClient.invalidateQueries({ queryKey: DIALOG_KEY })
  }, 15_000)
  const [, tik] = useState(0)
  useMesWs(
    useCallback(
      (event) => {
        if (
          !["andon.state", "kromka.measure", "scan.recorded"].includes(
            event.type,
          )
        )
          return
        refresh()
      },
      [refresh],
    ),
  )
  // Holat davomiyligi va yuqoridagi soat o'zi sanab tursin — usiz qotib qolardi
  useEffect(() => {
    const t = setInterval(() => tik((n) => n + 1), 30_000)
    return () => clearInterval(t)
  }, [])

  // Qaytish havolasi: manzil DOIM "/" — rolni `_layout` guard'i o'zi hal qiladi
  // (terminal va post rollari `/terminal` ga, tablo hisobi esa `/tablo` ga).
  // TABLO hisobiga havola ko'rsatilmaydi: u boshqaruv panelini ko'rmaydi va
  // bosilsa shu yerga qaytib kelardi.
  const { data: me } = useQuery(getCurrentUserQueryOptions())
  const qaytish =
    me && me.role !== "tablo"
      ? me.role === "terminal" || OPERATOR_ROLES.includes(me.role)
        ? "Terminal"
        : "Boshqaruv paneli"
      : null

  const [ochiq, setOchiq] = useState<number | null>(null)
  const rows = data ?? []

  return (
    <div className="min-h-screen bg-[#0E1116] px-8 py-7 text-[#E7EAEF]">
      <header className="mb-7 flex flex-wrap items-baseline gap-x-6 gap-y-2">
        <h1 className="text-4xl font-black tracking-tight">Stanoklar</h1>
        <span className="num ml-auto text-2xl font-semibold text-[#C8D0DC]">
          {new Date().toLocaleTimeString("uz-UZ", {
            hour: "2-digit",
            minute: "2-digit",
          })}
        </span>
        {qaytish && (
          <Link
            to="/"
            className="text-lg text-[#5D6675] outline-none hover:text-[#C8D0DC] focus-visible:text-[#C8D0DC]"
          >
            {qaytish}
          </Link>
        )}
      </header>

      {isLoading ? (
        <BrandLoader />
      ) : rows.length === 0 ? (
        <p className="max-w-prose text-2xl text-[#8B95A5]">
          Hali bitta ham stanok ulanmagan. Pico va agent ishga tushgach stanok
          shu yerda o'zi paydo bo'ladi.
        </p>
      ) : (
        <div className="grid gap-6 [grid-template-columns:repeat(auto-fit,minmax(38rem,1fr))]">
          {rows.map((row) => (
            <MachineCard
              key={row.machine_id}
              row={row}
              onOpen={() => setOchiq(row.machine_id)}
            />
          ))}
        </div>
      )}
      <MachineDialog machineId={ochiq} onClose={() => setOchiq(null)} />
    </div>
  )
}
