// Kromka kalibrlash sessiyasi (docs/12 §4.19–4.20).
//
// Admin sessiyani boshlaydi va etalon detallarni oddiy ishdagidek o'tkazadi: Pico har o'tishda
// `olchov` yuboradi, shu oraliqdagi hodisalar nuqta bo'ladi. Hisob — stansiyaning aynan
// algoritmi (`backend/app/services/kromka_kalib.py`). Tugagan sessiyani «Pico'ga qo'llash»
// mumkin: server qiymatlarni o'zi qayta hisoblaydi va chegaralarni tekshiradi, agent `SET`
// yozadi, Pico javobi tasdiq bo'ladi. Har qo'llashni orqaga qaytarish mumkin.

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useState } from "react"

import {
  type KalApplyRow,
  type KalibDetail,
  type KalibPoint,
  KromkaKalibService,
  MachinesService,
} from "@/client"
import { ConfirmDialog } from "@/components/Common/ConfirmDialog"
import { QueryError } from "@/components/Common/QueryError"
import { cardSurface } from "@/components/ui/card"
import { Checkbox } from "@/components/ui/checkbox"
import { Input } from "@/components/ui/input"
import { LoadingButton } from "@/components/ui/loading-button"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { formatDateTime } from "@/lib/mes"
import { cn } from "@/lib/utils"
import { crudCallbacks } from "@/queries/mes"

const LIST_KEY = ["kromka-kalib"]

/** `services/kromka_kalib.hisobla` natijasi (sxemada `dict[str, Any]`). */
type Natija = {
  D: number
  B1: number
  B2: number
  K1: number
  K2: number
  C: number
  V10: number | null
  V18: number | null
  tur: { B?: number; C?: number; K?: number }
  n_ish: number
  n_chet: number
  n_lens: number
  n_tez: number
  sd: number
  max_err: number
  sd_dat: number | null
  sd_tez: number | null
  dif_ort: number | null
  hukm: [string, string]
  kam: string[]
  qollasa_boladi: boolean
  td_tavsiya: number | null
  dopusk_tavsiya: number
  grp: {
    L_ref: number
    S: number
    n: number
    mean: number
    sd: number | null
  }[]
}

/** Yangi qiymat Pico'dagisi bilan yonma-yon — `SET` qilinsa nima o'zgarishini ko'rish uchun. */
const PARAMS: { key: keyof Natija; label: string; dp: number }[] = [
  { key: "D", label: "D — datchiklar orasi, mm", dp: 2 },
  { key: "B1", label: "B1, mm", dp: 2 },
  { key: "B2", label: "B2, mm", dp: 2 },
  { key: "K1", label: "K1, ms", dp: 3 },
  { key: "K2", label: "K2, ms", dp: 3 },
  { key: "C", label: "C, ms", dp: 3 },
  { key: "V10", label: "V10, m/min", dp: 3 },
  { key: "V18", label: "V18, m/min", dp: 3 },
]

const f = (v: number | null | undefined, dp: number) =>
  v == null ? "—" : v.toFixed(dp)
const signed = (v: number | null | undefined, dp: number) => {
  if (v == null) return "—"
  const s = v.toFixed(dp)
  // -0.004 → "-0.00" emas, "0.00": belgisiz nol farq yo'qligini ko'rsatadi
  return Number(s) === 0 ? (0).toFixed(dp) : (v > 0 ? "+" : "") + s
}

export function KromkaKalibCard() {
  const queryClient = useQueryClient()
  const machines = useQuery({
    queryKey: ["system-settings", "kromka-calibration"],
    queryFn: async () => (await MachinesService.readKromkaCalibration()).data,
  })
  const sessions = useQuery({
    queryKey: LIST_KEY,
    queryFn: async () => (await KromkaKalibService.readKalibSessions()).data,
  })
  const [machineId, setMachineId] = useState("")
  const [lRef, setLRef] = useState("")
  const [picked, setPicked] = useState<number | null>(null)

  const startCb = crudCallbacks(queryClient, LIST_KEY, "Kalibrlash boshlandi")
  const start = useMutation({
    mutationFn: async () =>
      (
        await KromkaKalibService.startKalibSession({
          body: { machine_id: Number(machineId), L_ref: Number(lRef) },
        })
      ).data,
    ...startCb,
    onSuccess: (s) => {
      startCb.onSuccess()
      setPicked(s.id)
    },
  })

  if (machines.isLoading || sessions.isLoading)
    return <Skeleton className="h-48 w-full" />
  if (machines.isError || sessions.isError || !machines.data || !sessions.data)
    return (
      <QueryError
        onRetry={() => {
          machines.refetch()
          sessions.refetch()
        }}
      />
    )

  const ochiq = sessions.data.find(
    (s) => s.ended_at == null && String(s.machine_id) === machineId,
  )
  const tanlangan =
    picked ?? sessions.data.find((s) => s.ended_at == null)?.id ?? null

  return (
    <div className={cn(cardSurface, "space-y-4 p-4")}>
      <div>
        <h2 className="text-lg font-semibold">Kalibrlash sessiyasi</h2>
        <p className="text-sm text-muted-foreground">
          Sessiyani boshlang va shtangensirkul bilan o'lchangan etalon
          detallarni lentadan oddiy o'tkazing (kamida 2 xil uzunlik, ikkala
          tezlik, jami ~40 o'tish). Sessiya davomidagi o'tishlar skanga
          bog'lanmaydi. Tugagan sessiyani «Pico'ga qo'llash» mumkin — har
          qo'llashni orqaga qaytarsa bo'ladi.
        </p>
      </div>

      <div className="flex flex-wrap items-end gap-2">
        <div className="space-y-1">
          <span className="text-sm">Stanok</span>
          <Select value={machineId} onValueChange={setMachineId}>
            <SelectTrigger className="w-44">
              <SelectValue placeholder="Tanlang" />
            </SelectTrigger>
            <SelectContent>
              {machines.data.map((m) => (
                <SelectItem key={m.machine_id} value={String(m.machine_id)}>
                  {m.machine_name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-1">
          <span className="text-sm">Birinchi etalon, mm</span>
          <Input
            className="w-32"
            inputMode="decimal"
            value={lRef}
            onChange={(e) => setLRef(e.target.value)}
          />
        </div>
        <LoadingButton
          loading={start.isPending}
          disabled={!machineId || !(Number(lRef) > 0) || !!ochiq}
          onClick={() => start.mutate()}
        >
          Boshlash
        </LoadingButton>
        {ochiq && (
          <span className="text-sm text-muted-foreground">
            Bu stanokda sessiya ochiq
          </span>
        )}
      </div>

      {sessions.data.length > 0 && (
        <div className="overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Stanok</TableHead>
                <TableHead>Boshlangan</TableHead>
                <TableHead>Tugagan</TableHead>
                <TableHead>Etalonlar, mm</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {sessions.data.map((s) => (
                <TableRow
                  key={s.id}
                  className={cn(
                    "cursor-pointer",
                    s.id === tanlangan && "bg-muted",
                  )}
                  onClick={() => setPicked(s.id)}
                >
                  <TableCell>{s.machine_name}</TableCell>
                  <TableCell>{formatDateTime(s.started_at)}</TableCell>
                  <TableCell>
                    {s.ended_at ? formatDateTime(s.ended_at) : "ochiq"}
                  </TableCell>
                  <TableCell className="num">
                    {s.segments.map((g) => g.L_ref).join(" → ")}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      {tanlangan != null && <SessionDetail id={tanlangan} />}
    </div>
  )
}

function SessionDetail({ id }: { id: number }) {
  const queryClient = useQueryClient()
  const key = [...LIST_KEY, id]
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: key,
    queryFn: async () =>
      (await KromkaKalibService.readKalibSession({ path: { session_id: id } }))
        .data,
    // Ochiq sessiyada nuqtalar o'tgan sari qo'shiladi; qo'llash Pico javobini kutayotganda ham
    refetchInterval: (q) =>
      q.state.data?.ended_at == null ||
      q.state.data?.applies.some((a) => a.status === "kutilmoqda")
        ? 5_000
        : false,
  })
  const [lRef, setLRef] = useState("")
  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: LIST_KEY })
  }
  const etalonCb = crudCallbacks(queryClient, LIST_KEY, "Etalon almashtirildi")
  const etalon = useMutation({
    mutationFn: () =>
      KromkaKalibService.setKalibEtalon({
        path: { session_id: id },
        body: { L_ref: Number(lRef) },
      }),
    ...etalonCb,
    onSuccess: () => {
      etalonCb.onSuccess()
      setLRef("")
    },
  })
  const end = useMutation({
    mutationFn: () =>
      KromkaKalibService.endKalibSession({ path: { session_id: id } }),
    ...crudCallbacks(queryClient, LIST_KEY, "Sessiya tugadi"),
  })
  const exclude = useMutation({
    mutationFn: (p: KalibPoint) =>
      KromkaKalibService.excludeKalibPoint({
        path: { session_id: id, event_id: p.event_id },
        body: { excluded: !p.excluded },
      }),
    onSettled: invalidate,
  })

  const [confirm, setConfirm] = useState<"apply" | KalApplyRow | null>(null)
  const applyCb = crudCallbacks(
    queryClient,
    LIST_KEY,
    "Buyruq yuborildi — Pico javobi kutilmoqda",
  )
  const apply = useMutation({
    mutationFn: () =>
      confirm === "apply"
        ? KromkaKalibService.applyKalibSession({ path: { session_id: id } })
        : KromkaKalibService.rollbackKalApply({
            path: { apply_id: (confirm as KalApplyRow).id },
          }),
    ...applyCb,
    onSuccess: () => {
      applyCb.onSuccess()
      setConfirm(null)
    },
  })

  if (isLoading) return <Skeleton className="h-48 w-full" />
  if (isError || !data) return <QueryError onRetry={() => refetch()} />
  const r = data.result as Natija | null
  const kutilmoqda = data.applies.some((a) => a.status === "kutilmoqda")

  return (
    <div className="space-y-4 border-t pt-4">
      {data.ended_at == null && (
        <div className="flex flex-wrap items-end gap-2">
          <div className="space-y-1">
            <span className="text-sm">
              Hozir:{" "}
              {String(data.segments[data.segments.length - 1]?.L_ref ?? "")} mm
              · keyingi etalon, mm
            </span>
            <Input
              className="w-32"
              inputMode="decimal"
              value={lRef}
              onChange={(e) => setLRef(e.target.value)}
            />
          </div>
          <LoadingButton
            variant="outline"
            loading={etalon.isPending}
            disabled={!(Number(lRef) > 0)}
            onClick={() => etalon.mutate()}
          >
            Etalonni almashtirish
          </LoadingButton>
          <LoadingButton
            variant="destructive"
            loading={end.isPending}
            onClick={() => end.mutate()}
          >
            Tugatish
          </LoadingButton>
        </div>
      )}

      {r ? (
        <Result r={r} current={data.current} />
      ) : (
        <p className="text-sm text-muted-foreground">
          Hali nuqta yo'q — etalonni o'tkazing.
        </p>
      )}
      {r && data.ended_at != null && (
        <div className="flex flex-wrap items-center gap-2">
          <LoadingButton
            disabled={!r.qollasa_boladi || kutilmoqda}
            loading={apply.isPending && confirm === "apply"}
            onClick={() => setConfirm("apply")}
          >
            Pico'ga qo'llash
          </LoadingButton>
          <span className="text-sm text-muted-foreground">
            {!r.qollasa_boladi
              ? "Kamida 2 xil uzunlikdagi etalon kerak"
              : "Qo'llagach 1–2 etalonni qayta o'tkazib tekshiring"}
          </span>
        </div>
      )}
      {data.applies.length > 0 && (
        <Applies
          rows={data.applies}
          busy={kutilmoqda}
          onRollback={(a) => setConfirm(a)}
        />
      )}
      <Points data={data} onToggle={(p) => exclude.mutate(p)} />
      <ConfirmDialog
        open={confirm != null}
        onOpenChange={(v) => !v && setConfirm(null)}
        title={
          confirm === "apply"
            ? `${data.machine_name}: kalibrlashni qo'llash`
            : "Oldingi qiymatlarni qaytarish"
        }
        description={
          confirm === "apply"
            ? "Yangi qiymatlar Pico'ga yoziladi va shu zahoti hamma o'lchovga ta'sir qiladi. Natija yuqoridagi jadvaldagi «Yangi» ustuni. Qo'llagach etalonni qayta o'tkazib tekshiring; noto'g'ri bo'lsa — «Qaytarish»."
            : confirm
              ? `Pico'ga yoziladi: ${
                  confirm.previous
                    ? Object.entries(confirm.previous)
                        .map(([k, v]) => `${k}=${v}`)
                        .join(" ")
                    : ""
                }`
              : ""
        }
        confirmText={confirm === "apply" ? "Qo'llash" : "Qaytarish"}
        destructive={confirm !== "apply"}
        loading={apply.isPending}
        onConfirm={() => apply.mutate()}
      />
    </div>
  )
}

const STATUS_STYLE: Record<string, string> = {
  tasdiqlandi: "text-emerald-700",
  kutilmoqda: "text-amber-700",
  javobsiz: "text-red-700",
}

const STATUS_LABEL: Record<string, string> = {
  tasdiqlandi: "Pico tasdiqladi",
  kutilmoqda: "Pico javobi kutilmoqda…",
  javobsiz: "Javob kelmadi (agent 1.12.0 va ulangan Pico kerak)",
}

/** Stanokdagi oxirgi qo'llashlar — holati va orqaga qaytarish. */
function Applies({
  rows,
  busy,
  onRollback,
}: {
  rows: KalApplyRow[]
  busy: boolean
  onRollback: (a: KalApplyRow) => void
}) {
  return (
    <div className="overflow-x-auto">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Vaqt</TableHead>
            <TableHead>Buyruq</TableHead>
            <TableHead>Holat</TableHead>
            <TableHead />
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((a) => (
            <TableRow key={a.id}>
              <TableCell>{formatDateTime(a.created_at)}</TableCell>
              <TableCell className="num text-xs">
                {a.rollback_of_id != null && "↩ "}
                {a.line}
              </TableCell>
              <TableCell className={STATUS_STYLE[a.status]}>
                {STATUS_LABEL[a.status] ?? a.status}
                {a.confirmed_at && ` · ${formatDateTime(a.confirmed_at)}`}
              </TableCell>
              <TableCell className="text-right">
                {a.status === "tasdiqlandi" && (
                  <LoadingButton
                    variant="outline"
                    size="sm"
                    loading={false}
                    disabled={busy}
                    onClick={() => onRollback(a)}
                  >
                    Qaytarish
                  </LoadingButton>
                )}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}

function Result({
  r,
  current,
}: {
  r: Natija
  current: Record<string, number>
}) {
  return (
    <div className="space-y-3">
      <p
        className={cn(
          "font-semibold",
          r.hukm[0] === "ok" ? "text-emerald-700" : "text-amber-700",
        )}
      >
        2σ (95%) = {r.hukm[1]}
      </p>
      {r.kam.length > 0 && (
        <p className="text-sm text-amber-700">{r.kam.join(" · ")}</p>
      )}
      <p className="text-sm text-muted-foreground">
        Nuqta: {r.n_ish}
        {r.n_chet > 0 && ` (+${r.n_chet} chetlangan)`} · uzunlik: {r.n_lens} ·
        tezlik: {r.n_tez} · σ = {f(r.sd, 3)} mm · eng katta xato{" "}
        {f(r.max_err, 2)} mm
        {r.sd_dat != null &&
          ` · datchiklar ${f(r.sd_dat, 3)} / tezlik ${f(r.sd_tez, 3)} mm`}
        {r.dif_ort != null && ` · D1−D2 o'rtacha ${signed(r.dif_ort, 2)} mm`}
      </p>
      <p className="text-sm">
        Tavsiya: dopusk ± {r.dopusk_tavsiya.toFixed(1)} mm
        {r.td_tavsiya != null &&
          ` · datchik farqi (TD) ± ${r.td_tavsiya.toFixed(1)} mm`}
      </p>
      <div className="grid gap-4 lg:grid-cols-2">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Parametr</TableHead>
              <TableHead className="text-right">Pico'da</TableHead>
              <TableHead className="text-right">Yangi</TableHead>
              <TableHead className="text-right">Farq</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {PARAMS.map(({ key, label, dp }) => {
              const yangi = r[key] as number | null
              const eski = current[key]
              return (
                <TableRow key={key}>
                  <TableCell>{label}</TableCell>
                  <TableCell className="num text-right">
                    {f(eski, dp)}
                  </TableCell>
                  <TableCell className="num text-right">
                    {f(yangi, dp)}
                  </TableCell>
                  <TableCell className="num text-right">
                    {yangi != null && eski != null
                      ? signed(yangi - eski, dp)
                      : "—"}
                  </TableCell>
                </TableRow>
              )
            })}
          </TableBody>
        </Table>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Etalon</TableHead>
              <TableHead>m/min</TableHead>
              <TableHead className="text-right">n</TableHead>
              <TableHead className="text-right">O'rtacha</TableHead>
              <TableHead className="text-right">σ</TableHead>
              <TableHead className="text-right">Xato</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {r.grp.map((g) => (
              <TableRow key={`${g.L_ref}@${g.S}`}>
                <TableCell className="num">{g.L_ref}</TableCell>
                <TableCell className="num">{g.S}</TableCell>
                <TableCell className="num text-right">{g.n}</TableCell>
                <TableCell className="num text-right">{f(g.mean, 2)}</TableCell>
                <TableCell className="num text-right">{f(g.sd, 3)}</TableCell>
                <TableCell className="num text-right">
                  {signed(g.mean - g.L_ref, 2)}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  )
}

function Points({
  data,
  onToggle,
}: {
  data: KalibDetail
  onToggle: (p: KalibPoint) => void
}) {
  if (data.points.length === 0) return null
  return (
    <div className="max-h-96 overflow-auto">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Hisobda</TableHead>
            <TableHead>Vaqt</TableHead>
            <TableHead className="text-right">Etalon</TableHead>
            <TableHead className="text-right">m/min</TableHead>
            <TableHead className="text-right">t1, ms</TableHead>
            <TableHead className="text-right">t2, ms</TableHead>
            <TableHead className="text-right">Pico L</TableHead>
            <TableHead className="text-right">Yangi L</TableHead>
            <TableHead className="text-right">Xato</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {data.points.map((p) => (
            <TableRow
              key={p.event_id}
              className={cn((p.excluded || p.chet) && "opacity-50")}
            >
              <TableCell>
                <Checkbox
                  checked={!p.excluded}
                  onCheckedChange={() => onToggle(p)}
                  aria-label="Hisobga olish"
                />
              </TableCell>
              <TableCell>{formatDateTime(p.at)}</TableCell>
              <TableCell className="num text-right">{p.L_ref}</TableCell>
              <TableCell className="num text-right">{p.S}</TableCell>
              <TableCell className="num text-right">{f(p.t1, 1)}</TableCell>
              <TableCell className="num text-right">{f(p.t2, 1)}</TableCell>
              <TableCell className="num text-right">
                {f(p.L_pico, 1)}
                {p.kod && p.kod !== "OK" && ` ${p.kod}`}
              </TableCell>
              <TableCell className="num text-right">{f(p.Lfit, 2)}</TableCell>
              <TableCell
                className={cn(
                  "num text-right",
                  p.err != null && Math.abs(p.err) > 0.5 && "text-amber-700",
                )}
              >
                {signed(p.err, 2)}
                {p.chet && " ⊘"}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}
