// Ishbay ish haqi (EKO 10a): stavkalar (post birligi uchun, sanadan), davr hisobi MES skanlaridan va vedomost
// (ikki kalit). Tasdiqlangan vedomost buxgalteriyaga D 2010 — K 6710 bo'lib tushadi va mehnat buyurtma
// tannarxiga qo'shiladi; bu ekran pul bermaydi — to'lov kassadan «Ish haqi (ishbay)» moddasi bilan.

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { TriangleAlert } from "lucide-react"
import { type ReactNode, useState } from "react"

import { type HaqQator, TannarxService } from "@/client"
import { SelectField } from "@/components/Common/SelectField"
import { Button } from "@/components/ui/button"
import { cardSurface } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { LoadingButton } from "@/components/ui/loading-button"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { formatDate, formatMoney } from "@/lib/mes"
import { cn } from "@/lib/utils"
import { fmtQty, parseNum } from "@/lib/warehouse"
import { extractErrorMessage } from "@/utils"

const BIRLIK: Record<string, string> = {
  m2: "m²",
  meter: "metr",
  piece: "dona",
}
const HOLAT: Record<string, string> = {
  qoralama: "qoralama",
  tasdiqlangan: "tasdiqlangan",
  bekor: "bekor qilingan",
}
const td = "border-b px-2 py-2"
const tdNum = "num border-b px-2 py-2 text-right whitespace-nowrap"
const sana = (d: Date) => d.toLocaleDateString("sv-SE")
const bugun = () => sana(new Date())
const kecha = () => {
  const d = new Date()
  d.setDate(d.getDate() - 1)
  return sana(d)
}
const birlik = (b: string) => BIRLIK[b] ?? b

function Karta({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className={cn(cardSurface, "flex flex-col gap-2 p-4")}>
      <h2 className="font-semibold">{title}</h2>
      {children}
    </section>
  )
}

function Jadval({
  bosh,
  ong = [],
  children,
}: {
  bosh: string[]
  ong?: number[]
  children: ReactNode
}) {
  return (
    <div className="overflow-x-auto">
      <Table className="w-full text-sm">
        <TableHeader>
          <TableRow className="border-b text-left text-xs text-muted-foreground uppercase">
            {bosh.map((h, i) => (
              <TableHead
                key={h || i}
                className={cn(
                  "px-2 py-2 font-medium",
                  ong.includes(i) && "text-right",
                )}
              >
                {h}
              </TableHead>
            ))}
          </TableRow>
        </TableHeader>
        <TableBody>{children}</TableBody>
      </Table>
    </div>
  )
}

function Xato({ text }: { text: string }) {
  if (!text) return null
  return (
    <div className="flex items-start gap-2 rounded border border-red-300 bg-red-50 p-2 text-sm text-red-900">
      <TriangleAlert className="mt-0.5 size-4 shrink-0" />
      {text}
    </div>
  )
}

const Bosh = ({ text }: { text: string }) => (
  <p className="p-2 text-sm text-muted-foreground">{text}</p>
)

export function IshHaqi() {
  const qc = useQueryClient()
  const [xato, setXato] = useState("")
  const [postId, setPostId] = useState("")
  const [narx, setNarx] = useState("")
  const [qachon, setQachon] = useState(bugun())
  const [dan, setDan] = useState(`${bugun().slice(0, 8)}01`)
  const [gacha, setGacha] = useState(kecha())
  const [ochiq, setOchiq] = useState<number | null>(null)

  const postlar = useQuery({
    queryKey: ["tannarx", "postlar"],
    queryFn: async () => (await TannarxService.tannarxPostlar()).data,
  })
  const stavkalar = useQuery({
    queryKey: ["tannarx", "stavkalar"],
    queryFn: async () => (await TannarxService.tannarxStavkalar()).data,
  })
  const hisob = useQuery({
    queryKey: ["tannarx", "hisob", dan, gacha],
    queryFn: async () =>
      (await TannarxService.tannarxHisob({ query: { dan, gacha } })).data,
    enabled: !!dan && !!gacha && dan <= gacha,
  })
  const vedomostlar = useQuery({
    queryKey: ["tannarx", "vedomostlar"],
    queryFn: async () => (await TannarxService.tannarxVedomostlar()).data,
  })
  const tanlangan = useQuery({
    queryKey: ["tannarx", "vedomost", ochiq],
    queryFn: async () =>
      (
        await TannarxService.tannarxVedomost({
          path: { vedomost_id: ochiq ?? 0 },
        })
      ).data,
    enabled: ochiq != null,
  })

  const ok = () => {
    setXato("")
    qc.invalidateQueries({ queryKey: ["tannarx"] })
    qc.invalidateQueries({ queryKey: ["moliya"] })
  }
  const onError = (e: unknown) => setXato(extractErrorMessage(e as Error))
  const stavka = useMutation({
    mutationFn: () =>
      TannarxService.tannarxStavkaQosh({
        body: {
          post_id: Number(postId),
          narx: parseNum(narx) ?? 0,
          amal_boshi: qachon,
        },
      }),
    onSuccess: () => {
      setNarx("")
      ok()
    },
    onError,
  })
  const amal = useMutation({
    mutationFn: async ({
      t,
      id = 0,
    }: {
      t: "yarat" | "tasdiq" | "bekor"
      id?: number
    }) =>
      t === "yarat"
        ? TannarxService.tannarxVedomostYarat({ body: { dan, gacha } })
        : t === "tasdiq"
          ? TannarxService.tannarxVedomostTasdiq({ path: { vedomost_id: id } })
          : TannarxService.tannarxVedomostBekor({ path: { vedomost_id: id } }),
    onSuccess: (r) => {
      setOchiq(r.data?.id ?? null)
      ok()
    },
    onError,
  })

  // Post bo'yicha bugun amaldagi stavka (postning hamma amali uchun yozilgani)
  const joriy = new Map<number, { narx: string; amal_boshi: string }>()
  for (const s of stavkalar.data ?? []) {
    if (s.process_code != null || s.amal_boshi > bugun()) continue
    const bor = joriy.get(s.post_id)
    if (!bor || bor.amal_boshi < s.amal_boshi) joriy.set(s.post_id, s)
  }
  const rows = hisob.data ?? []
  const jami = rows.reduce((a, q) => a + Number(q.summa), 0)
  const stavkasiz = rows.reduce((a, q) => a + (q.stavkasiz ?? 0), 0)

  return (
    <div className="flex flex-col gap-3">
      <Xato text={xato} />
      <Karta title="Ishbay stavkalar">
        <p className="text-sm text-muted-foreground">
          Ish haqi MES skanlaridan: har skan — postdagi bitta ish, hajmi detal
          o'lchamidan (arra va qadoqlash — m², kromka — metr, qolgani — dona).
          Stavka yozilgan sanadan amal qiladi; tasdiqlangan vedomost davriga
          orqaga yozilmaydi. Bekor qilingan (brak) skan haqi to'lanmaydi.
        </p>
        <Jadval
          bosh={["Post", "Birlik", "Amaldagi stavka", "Qachondan"]}
          ong={[2]}
        >
          {(postlar.data ?? []).map((p) => {
            const s = joriy.get(p.id)
            return (
              <TableRow key={p.id}>
                <TableCell className={cn(td, "font-semibold")}>
                  {p.nom}
                </TableCell>
                <TableCell className={td}>{birlik(p.birlik)}</TableCell>
                <TableCell className={tdNum}>
                  {s ? (
                    `${formatMoney(s.narx)} / ${birlik(p.birlik)}`
                  ) : (
                    <span className="text-red-700">yo'q</span>
                  )}
                </TableCell>
                <TableCell className={td}>
                  {s ? formatDate(s.amal_boshi) : "—"}
                </TableCell>
              </TableRow>
            )
          })}
        </Jadval>
        <div className="flex flex-wrap items-center gap-2">
          <SelectField
            className="w-56"
            value={postId}
            onChange={setPostId}
            placeholder="Post…"
            options={(postlar.data ?? []).map((p) => ({
              value: String(p.id),
              label: p.nom,
              hint: birlik(p.birlik),
            }))}
          />
          <Input
            aria-label="Narx"
            className="w-36"
            placeholder="Narx, so'm"
            inputMode="decimal"
            value={narx}
            onChange={(e) => setNarx(e.target.value)}
          />
          <Input
            aria-label="Qachondan"
            type="date"
            className="w-40"
            value={qachon}
            onChange={(e) => setQachon(e.target.value)}
          />
          <LoadingButton
            loading={stavka.isPending}
            disabled={!postId || parseNum(narx) == null}
            onClick={() => stavka.mutate()}
          >
            Stavka yozish
          </LoadingButton>
        </div>
      </Karta>

      <Karta title="Davr hisobi">
        <div className="flex flex-wrap items-center gap-2">
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
          <LoadingButton
            loading={amal.isPending}
            disabled={stavkasiz > 0 || rows.length === 0}
            onClick={() => amal.mutate({ t: "yarat" })}
          >
            Vedomost yozish
          </LoadingButton>
          <span className="num ml-auto font-semibold">
            Jami: {formatMoney(jami)}
          </span>
        </div>
        {stavkasiz > 0 && (
          <Xato
            text={`${stavkasiz} ta skan stavkasi yo'q postda — avval stavka yozing`}
          />
        )}
        {hisob.isLoading ? (
          <Skeleton className="h-24" />
        ) : (
          <HaqJadval rows={rows} />
        )}
      </Karta>

      <Karta title="Vedomostlar">
        <p className="text-sm text-muted-foreground">
          Tasdiqlash — ikki kalit: vedomostni yozgan xodim emas, boshqasi.
          Tasdiqlangach buxgalteriyaga D 2010 — K 6710 tushadi va mehnat
          buyurtmalar tannarxiga qo'shiladi. Ish haqini kassadan «Ish haqi
          (ishbay)» moddasi bilan bering — u xarajat emas, qarzni yopadi.
        </p>
        <Jadval
          bosh={[
            "№",
            "Davr",
            "Holat",
            "Skan",
            "Jami",
            "Yozdi · tasdiqladi",
            "",
          ]}
          ong={[3, 4]}
        >
          {(vedomostlar.data ?? []).map((v) => (
            <TableRow
              key={v.id}
              className={cn(ochiq === v.id && "bg-muted/50")}
            >
              <TableCell className={cn(td, "font-semibold")}>
                <button
                  type="button"
                  className="underline"
                  onClick={() => setOchiq(v.id)}
                >
                  {v.no}
                </button>
              </TableCell>
              <TableCell className={td}>
                {formatDate(v.dan)} — {formatDate(v.gacha)}
              </TableCell>
              <TableCell className={td}>{HOLAT[v.holat] ?? v.holat}</TableCell>
              <TableCell className={tdNum}>{v.skanlar}</TableCell>
              <TableCell className={tdNum}>{formatMoney(v.jami)}</TableCell>
              <TableCell className={cn(td, "text-xs")}>
                {v.yaratgan}
                {v.tasdiqlagan && ` · ${v.tasdiqlagan}`}
              </TableCell>
              <TableCell className={cn(td, "text-right whitespace-nowrap")}>
                {v.holat === "qoralama" && (
                  <>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => amal.mutate({ t: "tasdiq", id: v.id })}
                    >
                      Tasdiqlash
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => amal.mutate({ t: "bekor", id: v.id })}
                    >
                      Bekor
                    </Button>
                  </>
                )}
              </TableCell>
            </TableRow>
          ))}
        </Jadval>
        {vedomostlar.data?.length === 0 && <Bosh text="Hali vedomost yo'q" />}
        {tanlangan.data && (
          <div className="flex flex-col gap-1">
            <h3 className="text-sm font-semibold">
              {tanlangan.data.no} — hodimlar bo'yicha
            </h3>
            <HaqJadval rows={tanlangan.data.qatorlar ?? []} />
          </div>
        )}
      </Karta>
    </div>
  )
}

function HaqJadval({ rows }: { rows: HaqQator[] }) {
  if (!rows.length) return <Bosh text="Bu davrda skan yo'q" />
  return (
    <Jadval bosh={["Hodim", "Post", "Hajm", "Skan", "Summa"]} ong={[2, 3, 4]}>
      {rows.map((q) => (
        <TableRow key={`${q.employee_id}-${q.post_id}`}>
          <TableCell className={td}>{q.hodim}</TableCell>
          <TableCell className={td}>{q.post}</TableCell>
          <TableCell className={tdNum}>
            {fmtQty(q.hajm)} {birlik(q.birlik)}
          </TableCell>
          <TableCell className={tdNum}>{q.skanlar}</TableCell>
          <TableCell className={tdNum}>
            {q.stavkasiz ? (
              <span className="text-red-700">stavka yo'q</span>
            ) : (
              formatMoney(q.summa)
            )}
          </TableCell>
        </TableRow>
      ))}
    </Jadval>
  )
}
