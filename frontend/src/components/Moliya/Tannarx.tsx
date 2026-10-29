// Buyurtmaning to'liq (boshqaruv) tannarxi va OEE yo'qotishi pulda (EKO 10b–10d).
// Material (FIFO) + kromka normasi + ishbay mehnat + stanok vaqti (ideal sikl × soat narxi) + asbob (tig') normasi.
// Stanok va asbob normasi buxgalteriyaga yozilmaydi: ularning haqiqiy puli xarajatda — bu yerda faqat taqsimot.

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useState } from "react"

import { type TannarxQator, TannarxService } from "@/client"
import { SelectField } from "@/components/Common/SelectField"
import { Input } from "@/components/ui/input"
import { LoadingButton } from "@/components/ui/loading-button"
import { Skeleton } from "@/components/ui/skeleton"
import { TableCell, TableRow } from "@/components/ui/table"
import { formatDate, formatMoney } from "@/lib/mes"
import { cn } from "@/lib/utils"
import { fmtQty, parseNum } from "@/lib/warehouse"
import { extractErrorMessage } from "@/utils"
import { Bosh, bugun, Jadval, Karta, kecha, td, tdNum, Xato } from "./qism"

const soat = (s: number) =>
  s >= 3600
    ? `${Math.floor(s / 3600)} soat ${Math.round((s % 3600) / 60)} daq`
    : `${Math.round(s / 60)} daq`
const pul = (v: string | null | undefined) => (v == null ? "—" : formatMoney(v))

/** Amaldagi narx: eng oxirgi `amal_boshi <= bugun` */
function amaldagi<T extends { amal_boshi: string }>(
  rows: T[],
  kalit: (r: T) => string | number,
) {
  const out = new Map<string | number, T>()
  for (const r of rows) {
    if (r.amal_boshi > bugun()) continue
    const bor = out.get(kalit(r))
    if (!bor || bor.amal_boshi < r.amal_boshi) out.set(kalit(r), r)
  }
  return out
}

export function Tannarx() {
  const [dan, setDan] = useState(`${bugun().slice(0, 8)}01`)
  const [gacha, setGacha] = useState(bugun())
  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-sm text-muted-foreground">Davr</span>
        <Input
          aria-label="Davr boshi"
          type="date"
          className="w-40"
          value={dan}
          onChange={(e) => setDan(e.target.value)}
        />
        <span>—</span>
        <Input
          aria-label="Davr oxiri"
          type="date"
          className="w-40"
          value={gacha}
          onChange={(e) => setGacha(e.target.value)}
        />
      </div>
      <Buyurtmalar dan={dan} gacha={gacha} />
      <OeeYoqotish dan={dan} gacha={gacha} />
      <Normalar />
    </div>
  )
}

function Buyurtmalar({ dan, gacha }: { dan: string; gacha: string }) {
  const { data, isLoading } = useQuery({
    queryKey: ["tannarx", "buyurtmalar", dan, gacha],
    queryFn: async () =>
      (await TannarxService.tannarxBuyurtmalar({ query: { dan, gacha } })).data,
    enabled: !!dan && !!gacha && dan <= gacha,
  })
  const rows = data ?? []
  const jam = (k: keyof TannarxQator) =>
    rows.reduce((a, r) => a + Number(r[k] ?? 0), 0)
  return (
    <Karta title="Buyurtmalarning to'liq tannarxi (yetkazilganlar)">
      <p className="text-sm text-muted-foreground">
        Moliya P&L dagi tannarx — material va tasdiqlangan ish haqi. Bu yerda
        to'liq boshqaruv tannarxi: unga kromka (sexga rulonda beriladi), stanok
        vaqti (ideal sikl × soat narxi) va asbob eskirishi qo'shiladi. Mehnat —
        hamma skan bo'yicha (tasdiqlanmagani ham).
      </p>
      {isLoading ? (
        <Skeleton className="h-24" />
      ) : rows.length === 0 ? (
        <Bosh text="Bu davrda yetkazilgan buyurtma yo'q" />
      ) : (
        <Jadval
          bosh={[
            "Buyurtma",
            "Summa",
            "Material",
            "Kromka",
            "Mehnat",
            "Stanok",
            "Asbob",
            "Tannarx",
            "Foyda",
            "Marja",
          ]}
          ong={[1, 2, 3, 4, 5, 6, 7, 8, 9]}
        >
          {rows.map((r) => {
            // Tannarxi umuman yo'q buyurtmada «100% marja» yolg'on — ko'rsatilmaydi
            const bosh = Number(r.jami) === 0
            const marja =
              Number(r.summa) && !bosh
                ? (Number(r.foyda) / Number(r.summa)) * 100
                : null
            return (
              <TableRow key={r.order_id}>
                <TableCell className={td}>
                  <div className="font-semibold">{r.number}</div>
                  <div className="text-xs text-muted-foreground">
                    {r.mijoz}
                    {r.yetkazilgan && ` · ${formatDate(r.yetkazilgan)}`}
                  </div>
                  {bosh && (
                    <div className="text-xs text-red-700">
                      tannarx yo'q: material berilmagan, skan yo'q
                    </div>
                  )}
                  {r.kamchilik.length > 0 && (
                    <div className="text-xs text-red-700">
                      narxi yo'q: {r.kamchilik.join(", ")}
                    </div>
                  )}
                </TableCell>
                <TableCell className={tdNum}>{formatMoney(r.summa)}</TableCell>
                <TableCell className={tdNum}>
                  {formatMoney(r.material)}
                </TableCell>
                <TableCell className={tdNum}>
                  {formatMoney(r.kromka)}
                  {Number(r.kromka_metr) > 0 && (
                    <div className="text-xs text-muted-foreground">
                      {fmtQty(r.kromka_metr)} m
                    </div>
                  )}
                </TableCell>
                <TableCell className={tdNum}>
                  {formatMoney(r.mehnat)}
                  {r.mehnat !== r.mehnat_tasdiqlangan && (
                    <div className="text-xs text-muted-foreground">
                      tasdiqlangan {formatMoney(r.mehnat_tasdiqlangan)}
                    </div>
                  )}
                </TableCell>
                <TableCell className={tdNum}>
                  {formatMoney(r.stanok)}
                  {Number(r.stanok_soat) > 0 && (
                    <div className="text-xs text-muted-foreground">
                      {soat(Number(r.stanok_soat) * 3600)}
                    </div>
                  )}
                </TableCell>
                <TableCell className={tdNum}>{formatMoney(r.asbob)}</TableCell>
                <TableCell className={cn(tdNum, "font-semibold")}>
                  {formatMoney(r.jami)}
                </TableCell>
                <TableCell
                  className={cn(tdNum, Number(r.foyda) < 0 && "text-red-700")}
                >
                  {formatMoney(r.foyda)}
                </TableCell>
                <TableCell className={tdNum}>
                  {marja == null ? "—" : `${marja.toFixed(1)}%`}
                </TableCell>
              </TableRow>
            )
          })}
          <TableRow className="font-semibold">
            <TableCell className={td}>Jami</TableCell>
            {(
              [
                "summa",
                "material",
                "kromka",
                "mehnat",
                "stanok",
                "asbob",
                "jami",
                "foyda",
              ] as const
            ).map((k) => (
              <TableCell key={k} className={tdNum}>
                {formatMoney(jam(k))}
              </TableCell>
            ))}
            <TableCell className={tdNum} />
          </TableRow>
        </Jadval>
      )}
    </Karta>
  )
}

function OeeYoqotish({ dan, gacha }: { dan: string; gacha: string }) {
  const { data, isLoading } = useQuery({
    queryKey: ["tannarx", "oee", dan, gacha],
    queryFn: async () =>
      (await TannarxService.tannarxOeeYoqotish({ query: { dan, gacha } })).data,
    enabled: !!dan && !!gacha && dan <= gacha,
  })
  const rows = data ?? []
  return (
    <Karta title="OEE yo'qotishi pulda">
      <p className="text-sm text-muted-foreground">
        Reja vaqtidan yo'qotilgan soatlar uch qismda: to'xtash (Availability),
        idealdan sekin ishlash (Performance), brakka ketgan vaqt (Quality) — ×
        stanok soat narxi. Sabablar — rejasiz to'xtashlar, ko'p vaqt olgani
        birinchi.
      </p>
      {isLoading ? (
        <Skeleton className="h-24" />
      ) : rows.length === 0 ? (
        <Bosh text="Bu davrda reja vaqti yo'q — ish jadvali kiritilmagan yoki stanok ishlamagan" />
      ) : (
        <Jadval
          bosh={[
            "Stanok",
            "OEE",
            "To'xtash",
            "Sekin",
            "Brak",
            "Jami yo'qotish",
            "Asosiy sabablar",
          ]}
          ong={[1, 2, 3, 4, 5]}
        >
          {rows.map((r) => (
            <TableRow key={r.machine_id}>
              <TableCell className={td}>
                <div className="font-semibold">{r.nom}</div>
                <div className="text-xs text-muted-foreground">
                  {r.soat_narxi ? (
                    `${formatMoney(r.soat_narxi)} / soat`
                  ) : (
                    <span className="text-red-700">soat narxi yo'q</span>
                  )}
                </div>
              </TableCell>
              <TableCell className={tdNum}>
                {r.oee_pct == null ? "—" : `${r.oee_pct}%`}
              </TableCell>
              {(
                [
                  [r.to_xtash_s, r.to_xtash],
                  [r.sekin_s, r.sekin],
                  [r.brak_s, r.brak],
                ] as const
              ).map(([s, p], i) => (
                <TableCell key={i} className={tdNum}>
                  {pul(p)}
                  <div className="text-xs text-muted-foreground">{soat(s)}</div>
                </TableCell>
              ))}
              <TableCell className={cn(tdNum, "font-semibold")}>
                {pul(r.jami)}
              </TableCell>
              <TableCell className={cn(td, "text-xs")}>
                {r.sabablar.length === 0
                  ? "—"
                  : r.sabablar.map((s) => (
                      <div key={s.nom}>
                        {s.nom}: {soat(s.soniya)}
                        {s.pul != null && ` · ${formatMoney(s.pul)}`}
                      </div>
                    ))}
              </TableCell>
            </TableRow>
          ))}
        </Jadval>
      )}
    </Karta>
  )
}

function Normalar() {
  const qc = useQueryClient()
  const [xato, setXato] = useState("")
  const [stanok, setStanok] = useState("")
  const [soatNarx, setSoatNarx] = useState("")
  const [amal, setAmal] = useState("")
  const [amalNarx, setAmalNarx] = useState("")
  const [qachon, setQachon] = useState(kecha())
  const stanoklar = useQuery({
    queryKey: ["tannarx", "stanoklar"],
    queryFn: async () => (await TannarxService.tannarxStanoklar()).data,
  })
  const stanokNarx = useQuery({
    queryKey: ["tannarx", "stanok-narx"],
    queryFn: async () => (await TannarxService.tannarxStanokNarxlari()).data,
  })
  const amallar = useQuery({
    queryKey: ["tannarx", "amallar"],
    queryFn: async () => (await TannarxService.tannarxAsbobAmallar()).data,
  })
  const asbob = useQuery({
    queryKey: ["tannarx", "asbob"],
    queryFn: async () => (await TannarxService.tannarxAsbob()).data,
  })
  const ok = () => {
    setXato("")
    qc.invalidateQueries({ queryKey: ["tannarx"] })
  }
  const onError = (e: unknown) => setXato(extractErrorMessage(e as Error))
  const sN = useMutation({
    mutationFn: () =>
      TannarxService.tannarxStanokNarxQosh({
        body: {
          machine_id: Number(stanok),
          soat_narxi: parseNum(soatNarx) ?? 0,
          amal_boshi: qachon,
        },
      }),
    onSuccess: () => {
      setSoatNarx("")
      ok()
    },
    onError,
  })
  const aN = useMutation({
    mutationFn: () =>
      TannarxService.tannarxAsbobQosh({
        body: { amal, narx: parseNum(amalNarx) ?? 0, amal_boshi: qachon },
      }),
    onSuccess: () => {
      setAmalNarx("")
      ok()
    },
    onError,
  })
  const sJoriy = amaldagi(stanokNarx.data ?? [], (r) => r.machine_id)
  const aJoriy = amaldagi(asbob.data ?? [], (r) => r.amal)
  return (
    <Karta title="Normalar: stanok soati va asbob">
      <p className="text-sm text-muted-foreground">
        Stanok soati — amortizatsiya, elektr va xizmatning bir soatga to'g'ri
        keladigan qismi. Asbob normasi — asbob narxi ÷ resursi (masalan sverlo
        200 000 so'm ÷ 20 000 teshik = 10 so'm/teshik). Teshik, paz, freza soni
        XNC fayldan olinadi. Narx sanadan amal qiladi, o'tgan sanaga ham
        yoziladi.
      </p>
      <Xato text={xato} />
      <div className="grid gap-4 lg:grid-cols-2">
        <div className="flex flex-col gap-2">
          {stanoklar.data?.length === 0 && (
            <Bosh text="Stanok yo'q — avval «Stanoklar» sahifasida qo'shing" />
          )}
          <Jadval bosh={["Stanok", "Soat narxi"]} ong={[1]}>
            {(stanoklar.data ?? []).map((m) => {
              const s = sJoriy.get(m.id)
              return (
                <TableRow key={m.id}>
                  <TableCell className={td}>
                    <span className="font-semibold">{m.nom}</span>{" "}
                    <span className="text-xs text-muted-foreground">
                      {m.post}
                    </span>
                  </TableCell>
                  <TableCell className={tdNum}>
                    {s ? (
                      `${formatMoney(s.soat_narxi)} · ${formatDate(s.amal_boshi)} dan`
                    ) : (
                      <span className="text-red-700">yo'q</span>
                    )}
                  </TableCell>
                </TableRow>
              )
            })}
          </Jadval>
          <div className="flex flex-wrap items-center gap-2">
            <SelectField
              className="w-52"
              value={stanok}
              onChange={setStanok}
              placeholder="Stanok…"
              options={(stanoklar.data ?? []).map((m) => ({
                value: String(m.id),
                label: m.nom,
                hint: m.post,
              }))}
            />
            <Input
              aria-label="Soat narxi"
              className="w-36"
              placeholder="So'm / soat"
              inputMode="decimal"
              value={soatNarx}
              onChange={(e) => setSoatNarx(e.target.value)}
            />
            <LoadingButton
              loading={sN.isPending}
              disabled={!stanok || parseNum(soatNarx) == null}
              onClick={() => sN.mutate()}
            >
              Yozish
            </LoadingButton>
          </div>
        </div>
        <div className="flex flex-col gap-2">
          <Jadval bosh={["Amal", "Norma"]} ong={[1]}>
            {(amallar.data ?? []).map((a) => {
              const s = aJoriy.get(a.kod)
              return (
                <TableRow key={a.kod}>
                  <TableCell className={td}>{a.nom}</TableCell>
                  <TableCell className={tdNum}>
                    {s ? (
                      `${formatMoney(s.narx)} · ${formatDate(s.amal_boshi)} dan`
                    ) : (
                      <span className="text-red-700">yo'q</span>
                    )}
                  </TableCell>
                </TableRow>
              )
            })}
          </Jadval>
          <div className="flex flex-wrap items-center gap-2">
            <SelectField
              className="w-60"
              value={amal}
              onChange={setAmal}
              placeholder="Amal…"
              options={(amallar.data ?? []).map((a) => ({
                value: a.kod,
                label: a.nom,
              }))}
            />
            <Input
              aria-label="Norma"
              className="w-32"
              placeholder="So'm"
              inputMode="decimal"
              value={amalNarx}
              onChange={(e) => setAmalNarx(e.target.value)}
            />
            <LoadingButton
              loading={aN.isPending}
              disabled={!amal || parseNum(amalNarx) == null}
              onClick={() => aN.mutate()}
            >
              Yozish
            </LoadingButton>
          </div>
        </div>
      </div>
      <div className="flex items-center gap-2 text-sm">
        <span className="text-muted-foreground">Qachondan:</span>
        <Input
          aria-label="Qachondan"
          type="date"
          className="w-40"
          value={qachon}
          onChange={(e) => setQachon(e.target.value)}
        />
      </div>
    </Karta>
  )
}
