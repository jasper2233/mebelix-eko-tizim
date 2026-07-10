// TABLO (TZ 9): sex zalidagi TV ekran — buyurtmalar × bosqichlar jonli matritsasi.
// Rejimlar: HAJM / SONI / FOIZ. Kontekst-aware: tablo user stanogi ustuni ajratiladi.

import { useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute, redirect } from "@tanstack/react-router"
import { useCallback, useEffect, useState } from "react"

import { ApiError, TabloService, UsersService } from "@/client"

type TabloPost = {
  id: number
  code: string
  name: string
  unit: string
  color?: string
  order_index: number
}

import { useMesWs } from "@/hooks/useMesWs"
import { formatDate, POST_COLORS } from "@/lib/mes"
import { cn } from "@/lib/utils"
import { getMachinesQueryOptions } from "@/queries/mes"

export const Route = createFileRoute("/tablo")({
  component: TabloPage,
  head: () => ({ meta: [{ title: "TABLO | MebeliX" }] }),
  beforeLoad: async () => {
    try {
      await UsersService.readUserMe()
    } catch (err) {
      if (err instanceof ApiError && err.status === 401)
        throw redirect({ to: "/login" })
      throw err
    }
  },
})

type Mode = "hajm" | "soni" | "foiz"

const UNIT_LABELS: Record<string, string> = {
  m2: "m²",
  meter: "m",
  piece: "dona",
}

function TabloPage() {
  const queryClient = useQueryClient()
  const [mode, setMode] = useState<Mode>("foiz")
  const [drill, setDrill] = useState<number | null>(null)
  const [clock, setClock] = useState(() =>
    new Date().toLocaleTimeString("uz-Latn-UZ"),
  )

  const { data: me } = useQuery({
    queryKey: ["currentUser"],
    queryFn: () => UsersService.readUserMe(),
  })
  const { data: machines } = useQuery({
    ...getMachinesQueryOptions(),
    enabled: me?.role === "tablo",
  })
  const { data, isLoading } = useQuery({
    queryKey: ["tablo", "matrix"],
    queryFn: () => TabloService.readTabloMatrix(),
    refetchInterval: 60_000,
  })

  const { online } = useMesWs(
    useCallback(
      (event) => {
        if (event.type.startsWith("scan.") || event.type.startsWith("order.")) {
          queryClient.invalidateQueries({ queryKey: ["tablo"] })
        }
      },
      [queryClient],
    ),
  )

  useEffect(() => {
    const t = setInterval(
      () => setClock(new Date().toLocaleTimeString("uz-Latn-UZ")),
      1000,
    )
    // Auto-refresh har 5 daqiqada (TZ 9.7) — kesh muammolarini oldini oladi
    const reload = setTimeout(() => window.location.reload(), 5 * 60_000)
    return () => {
      clearInterval(t)
      clearTimeout(reload)
    }
  }, [])

  const myMachine = machines?.find((m) => m.id === me?.machine_id)
  const contextPostId = myMachine?.post_id ?? null

  if (drill !== null)
    return (
      <TabloOrderDrill
        orderId={drill}
        onBack={() => setDrill(null)}
        mode={mode}
      />
    )

  return (
    <div className="flex h-dvh flex-col bg-[#f4f6f9] text-[#1c2b42]">
      <header className="flex items-center gap-4 border-b border-border bg-white px-5 py-2.5 shadow-sm">
        <img src="/assets/logo/icon-gold.png" alt="" className="h-8" />
        <span className="text-lg font-black tracking-tight">MebeliX</span>
        <span className="text-xs font-bold uppercase tracking-widest text-muted-foreground">
          {mode === "hajm"
            ? "Hajm nazorati"
            : mode === "soni"
              ? "Soni nazorati"
              : "Foiz nazorati"}
        </span>
        {myMachine && (
          <span className="rounded bg-secondary px-2 py-1 text-xs font-bold">
            JORIY NUQTA: {myMachine.name}
          </span>
        )}
        <div className="mx-auto flex gap-1">
          {(["hajm", "soni", "foiz"] as Mode[]).map((m) => (
            <button
              type="button"
              key={m}
              onClick={() => setMode(m)}
              className={cn(
                "rounded px-3 py-1 text-xs font-black uppercase",
                mode === m
                  ? "bg-[#f0a52f] text-[#1c2b42]"
                  : "bg-secondary hover:bg-accent",
              )}
            >
              {m}
            </button>
          ))}
        </div>
        <span
          className={cn(
            "size-2.5 rounded-full",
            online ? "bg-green-500" : "bg-red-500",
          )}
        />
        {!online && (
          <span className="text-xs font-bold text-red-600">OFFLINE</span>
        )}
        <div className="num text-2xl font-black">{clock}</div>
      </header>

      <main className="min-h-0 flex-1 overflow-auto p-4">
        {isLoading ? (
          <p className="p-8 text-center text-muted-foreground">
            Yuklanmoqda...
          </p>
        ) : (
          <table className="w-full border-separate border-spacing-1">
            <thead>
              <tr className="text-[11px] uppercase tracking-wider text-muted-foreground">
                <th className="px-2 text-left">№ / Buyurtma</th>
                <th className="px-2 text-left">Topshirish sanasi</th>
                {(data?.posts as TabloPost[] | undefined)?.map((p) => (
                  <th
                    key={p.id}
                    className={cn(
                      "px-2 pb-1 text-center",
                      contextPostId && p.id !== contextPostId && "opacity-40",
                    )}
                    style={{ color: POST_COLORS[p.code] }}
                  >
                    {p.code}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data && data.orders.length > 0 && (
                <tr>
                  <td className="rounded-l-lg bg-[#2f496e] px-3 py-2 text-xs font-black uppercase tracking-wider text-white">
                    Jami hajm
                  </td>
                  <td className="bg-[#2f496e]/90" />
                  {(data.posts as TabloPost[]).map((p) => {
                    let done = 0
                    let total = 0
                    let vDone = 0
                    let vTotal = 0
                    for (const o of data.orders) {
                      const st = o.stages[p.code]
                      if (!st) continue
                      done += st.done
                      total += st.total
                      vDone += st.volume_done
                      vTotal += st.volume_total
                    }
                    const unit = UNIT_LABELS[p.unit] ?? p.unit
                    const label =
                      mode === "hajm"
                        ? `${round1(vDone)} / ${round1(vTotal)} ${unit}`
                        : mode === "soni"
                          ? `${done} / ${total}`
                          : total
                            ? `${Math.round((done / total) * 1000) / 10}%`
                            : "—"
                    return (
                      <td
                        key={p.id}
                        className="num bg-[#2f496e] px-2 py-2 text-center text-xs font-black text-white"
                      >
                        {total ? label : "—"}
                      </td>
                    )
                  })}
                </tr>
              )}
              {data?.orders.map((o, idx) => (
                <tr
                  key={o.id}
                  onClick={() => setDrill(o.id)}
                  className="cursor-pointer"
                >
                  <td className="rounded-l-lg bg-white px-3 py-2.5 shadow-sm">
                    <span className="num mr-2 text-muted-foreground/70">
                      {idx + 1}
                    </span>
                    <span className="font-bold">{o.number}</span>
                    {o.name && (
                      <span className="ml-2 hidden text-xs text-muted-foreground xl:inline">
                        {o.name}
                      </span>
                    )}
                  </td>
                  <td className="num bg-amber-100 px-3 py-2.5 text-sm font-semibold text-amber-800">
                    {formatDate(o.deadline)}
                  </td>
                  {(data.posts as TabloPost[]).map((p) => (
                    <TabloCell
                      key={p.id}
                      stage={o.stages[p.code]}
                      unit={UNIT_LABELS[p.unit] ?? p.unit}
                      mode={mode}
                      dim={Boolean(contextPostId && p.id !== contextPostId)}
                      color={POST_COLORS[p.code]}
                      deadline={o.deadline}
                    />
                  ))}
                </tr>
              ))}
              {!data?.orders.length && (
                <tr>
                  <td
                    colSpan={2 + (data?.posts.length ?? 0)}
                    className="p-12 text-center text-muted-foreground/70"
                  >
                    Aktiv buyurtmalar yo'q
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        )}
      </main>
    </div>
  )
}

function TabloCell({
  stage,
  unit,
  mode,
  dim,
  color,
  deadline,
}: {
  stage?: {
    done: number
    total: number
    volume_total: number
    volume_done: number
  }
  unit: string
  mode: Mode
  dim: boolean
  color?: string
  deadline?: string | null
}) {
  if (!stage?.total) {
    return (
      <td
        className={cn(
          "bg-white px-2 py-2.5 text-center text-muted-foreground/40 shadow-sm",
          dim && "opacity-40",
        )}
      >
        —
      </td>
    )
  }
  const pct = Math.round((stage.done / stage.total) * 1000) / 10
  const complete = stage.done >= stage.total
  const overdue =
    !complete &&
    deadline != null &&
    new Date(deadline) < new Date() &&
    stage.done === 0

  let label: string
  if (mode === "hajm")
    label = `${round1(stage.volume_done)} / ${round1(stage.volume_total)} ${unit}`
  else if (mode === "soni") label = `${stage.done} / ${stage.total}`
  else label = `${pct}%`

  return (
    <td
      className={cn(
        "relative overflow-hidden rounded px-2 py-2.5 text-center align-middle",
        dim && "opacity-40",
        complete
          ? "bg-green-100"
          : overdue
            ? "bg-red-100"
            : "bg-white shadow-sm",
      )}
    >
      {!complete && (
        <span
          className="absolute inset-y-0 left-0 transition-all duration-1000"
          style={{
            width: `${pct}%`,
            backgroundColor: color
              ? `color-mix(in srgb, ${color} 22%, transparent)`
              : "rgba(0,0,0,0.06)",
          }}
        />
      )}
      <span
        className={cn(
          "num relative text-sm font-black",
          complete ? "text-green-700" : overdue ? "text-red-700" : "",
        )}
      >
        {complete ? "✓" : label}
      </span>
      {overdue && (
        <span className="relative block text-[9px] font-bold text-red-700">
          BOSHLANMADI
        </span>
      )}
    </td>
  )
}

function TabloOrderDrill({
  orderId,
  onBack,
  mode,
}: {
  orderId: number
  onBack: () => void
  mode: Mode
}) {
  const { data } = useQuery({
    queryKey: ["tablo", "order", orderId],
    queryFn: () => TabloService.readTabloOrder({ orderId }),
    refetchInterval: 30_000,
  })
  return (
    <div className="flex h-dvh flex-col bg-[#f4f6f9] text-[#1c2b42]">
      <header className="flex items-center gap-4 border-b border-border bg-white px-5 py-3 shadow-sm">
        <span className="text-lg font-black">{data?.number ?? ""}</span>
        <span className="text-sm text-muted-foreground">
          {data?.name ?? ""}
        </span>
        <span className="ml-auto text-xs font-bold uppercase tracking-widest text-muted-foreground">
          Soni nazorati
        </span>
      </header>
      <main className="min-h-0 flex-1 overflow-auto p-4">
        <table className="w-full border-separate border-spacing-1">
          <thead>
            <tr className="text-[11px] uppercase tracking-wider text-muted-foreground">
              <th className="px-2 text-left">Detal</th>
              <th className="px-2 text-center">Soni</th>
              {["ARRA", "KROMKA", "PRISADKA", "PAZ", "ROVER", "STOLYARKA"].map(
                (c) => (
                  <th
                    key={c}
                    className="px-2 text-center"
                    style={{ color: POST_COLORS[c] }}
                  >
                    {c}
                  </th>
                ),
              )}
            </tr>
          </thead>
          <tbody>
            {data?.parts.map((p) => (
              <tr key={p.part_id}>
                <td className="rounded-l-lg bg-white px-3 py-2 shadow-sm">
                  <b className="num">{p.code}</b>{" "}
                  <span className="text-xs text-muted-foreground">
                    {p.name}
                  </span>
                </td>
                <td className="num bg-white px-2 py-2 text-center font-bold shadow-sm">
                  {p.count}
                </td>
                {[
                  "ARRA",
                  "KROMKA",
                  "PRISADKA",
                  "PAZ",
                  "ROVER",
                  "STOLYARKA",
                ].map((c) => (
                  <TabloCell
                    key={c}
                    stage={p.stages[c]}
                    unit="dona"
                    mode={mode === "hajm" ? "soni" : mode}
                    dim={false}
                    color={POST_COLORS[c]}
                  />
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </main>
      <button
        type="button"
        onClick={onBack}
        className="m-4 self-start rounded-lg bg-secondary px-6 py-3 text-sm font-black uppercase hover:bg-accent"
      >
        ← Ortda
      </button>
    </div>
  )
}

function round1(v: number): number {
  return Math.round(v * 10) / 10
}
