// Operator terminali (TZ 8): POS monoblokda fullscreen ochiq turadigan ekran.
// Avto-skan input doim fokusda; beyjik UUID → sessiya, aks holda detal QR scan.

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute, redirect } from "@tanstack/react-router"
import {
  Lock,
  LogOut,
  Map as MapIcon,
  ScanLine,
  Undo2,
  WifiOff,
} from "lucide-react"
import { useCallback, useEffect, useRef, useState } from "react"

import {
  ApiError,
  type ScanResult,
  ScansService,
  TerminalService,
  UsersService,
} from "@/client"
import { ConfirmDialog } from "@/components/Common/ConfirmDialog"
import {
  playError,
  playSuccess,
  playWarning,
} from "@/components/Terminal/audio"
import { CutmapView } from "@/components/Terminal/CutmapView"
import { Button } from "@/components/ui/button"
import { Switch } from "@/components/ui/switch"
import useCustomToast from "@/hooks/useCustomToast"
import { useMesWs } from "@/hooks/useMesWs"
import { formatSize, OPERATOR_ROLES, POST_COLORS } from "@/lib/mes"
import { cn } from "@/lib/utils"
import {
  getTerminalContextQueryOptions,
  getTerminalTasksQueryOptions,
} from "@/queries/mes"

export const Route = createFileRoute("/terminal")({
  component: TerminalPage,
  head: () => ({ meta: [{ title: "Terminal | MebeliX" }] }),
  beforeLoad: async () => {
    try {
      const me = await UsersService.readUserMe()
      if (
        me.role !== "terminal" &&
        me.role !== "admin" &&
        !me.is_superuser &&
        !OPERATOR_ROLES.includes(me.role as never)
      ) {
        throw redirect({ to: "/" })
      }
    } catch (err) {
      if (err instanceof ApiError && err.status === 401)
        throw redirect({ to: "/login" })
      throw err
    }
  },
})

const BADGE_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i

type LastScan =
  | { kind: "ok"; code: string; qoldiq: number; scanId: number; at: number }
  | { kind: "error"; code: string; message: string; at: number }
  | null

function TerminalPage() {
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const { data: ctx } = useQuery(getTerminalContextQueryOptions())
  const { data: tasks } = useQuery(getTerminalTasksQueryOptions())

  const [scanOn, setScanOn] = useState(true)
  const [locked, setLocked] = useState(false)
  const [mapOrderId, setMapOrderId] = useState<number | null>(null)
  const [lastScan, setLastScan] = useState<LastScan>(null)
  const [history, setHistory] = useState<
    Array<{ id: number; code: string; ok: boolean; note: string; time: string }>
  >([])
  const [errorsOnly, setErrorsOnly] = useState(false)
  const [undoOpen, setUndoOpen] = useState(false)
  const [clock, setClock] = useState(() =>
    new Date().toLocaleTimeString("uz-Latn-UZ"),
  )
  const inputRef = useRef<HTMLInputElement>(null)
  const cooldownRef = useRef<Map<string, number>>(new Map())

  const { online } = useMesWs(
    useCallback(
      (event) => {
        if (
          [
            "scan.recorded",
            "scan.cancelled",
            "order.started",
            "order.cancelled",
          ].includes(event.type)
        ) {
          queryClient.invalidateQueries({ queryKey: ["terminal"] })
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
    return () => clearInterval(t)
  }, [])

  // Avto-skan: input doim fokusda (TZ 8.4.1)
  useEffect(() => {
    if (!scanOn || locked) return
    const focus = () => inputRef.current?.focus()
    focus()
    const t = setInterval(focus, 2000)
    return () => clearInterval(t)
  }, [scanOn, locked])

  const pushHistory = (entry: {
    id: number
    code: string
    ok: boolean
    note: string
  }) =>
    setHistory((prev) =>
      [
        { ...entry, time: new Date().toLocaleTimeString("uz-Latn-UZ") },
        ...prev,
      ].slice(0, 50),
    )

  const badgeMutation = useMutation({
    mutationFn: (badge: string) =>
      TerminalService.startTerminalSession({
        requestBody: { badge_id: badge },
      }),
    onSuccess: (s) => {
      playSuccess()
      showSuccessToast(`Sessiya ochildi: ${s.employee_name}`)
      queryClient.invalidateQueries({ queryKey: ["terminal"] })
    },
    onError: (err) => {
      playError()
      showErrorToast(detailMessage(err))
    },
  })

  const scanMutation = useMutation({
    mutationFn: (qr: string) =>
      ScansService.recordScan({
        requestBody: { qr_text: qr, client_event_id: crypto.randomUUID() },
      }),
    onSuccess: (r: ScanResult) => {
      playSuccess()
      setLastScan({
        kind: "ok",
        code: r.part_code,
        qoldiq: r.qoldiq,
        scanId: r.scan_id,
        at: Date.now(),
      })
      pushHistory({
        id: r.scan_id,
        code: `${r.part_code} (${r.instance_no})`,
        ok: true,
        note: `Qoldiq: ${r.qoldiq}`,
      })
      queryClient.invalidateQueries({ queryKey: ["terminal"] })
      if (r.order_completed) showSuccessToast("Buyurtma to'liq tayyor bo'ldi!")
      // SCX fayllar har scanda qaytadan (TZ 12.5): CNC postlarda avtomatik yuklab olish
      for (const fid of r.scx_file_ids ?? []) {
        const a = document.createElement("a")
        a.href = `${(window as never as { __API__?: string }).__API__ ?? ""}/api/v1/terminal/files/${fid}`
        a.download = ""
        a.click()
      }
    },
    onError: (err) => {
      const { code, message } = detailParts(err)
      if (code === "E001" && message.includes("yakunlangan")) playWarning()
      else playError()
      setLastScan({ kind: "error", code, message, at: Date.now() })
      pushHistory({ id: Date.now(), code: message, ok: false, note: code })
    },
  })

  const undoMutation = useMutation({
    mutationFn: (scanId: number) => ScansService.cancelScan({ scanId }),
    onSuccess: () => {
      playWarning()
      showSuccessToast("Oxirgi scan bekor qilindi")
      setUndoOpen(false)
      setLastScan(null)
      queryClient.invalidateQueries({ queryKey: ["terminal"] })
    },
    onError: (err) => {
      showErrorToast(detailMessage(err))
      setUndoOpen(false)
    },
  })

  const endSession = useMutation({
    mutationFn: () => TerminalService.endTerminalSession(),
    onSettled: () => queryClient.invalidateQueries({ queryKey: ["terminal"] }),
  })

  const handleSubmit = (raw: string) => {
    const value = raw.trim()
    if (!value) return
    if (BADGE_RE.test(value)) {
      badgeMutation.mutate(value)
      return
    }
    if (!online) {
      playError()
      setLastScan({
        kind: "error",
        code: "E007",
        message: "Aloqa yo'q, qaytadan urining",
        at: Date.now(),
      })
      return
    }
    // 2s cooldown (TZ 8.4.4): bir xil QR bir terminalda — duplikat, neytral signal
    const now = Date.now()
    const last = cooldownRef.current.get(value)
    if (last && now - last < 2000) return
    cooldownRef.current.set(value, now)
    scanMutation.mutate(value)
  }

  const mapOpen = ctx?.post_code === "ARRA" && mapOrderId !== null
  const canUndo = lastScan?.kind === "ok" && Date.now() - lastScan.at < 60_000
  const postColor = ctx
    ? (POST_COLORS[ctx.post_code] ?? "var(--primary)")
    : "var(--primary)"
  const visibleHistory = errorsOnly ? history.filter((h) => !h.ok) : history

  return (
    <div className="flex h-dvh flex-col bg-[#eef1f5]">
      {/* Header (TZ 8.3.1) */}
      <header className="flex items-center gap-4 border-b bg-white px-4 py-2 shadow-sm">
        <div>
          <div className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">
            Ishlab chiqarish posti
          </div>
          <div className="text-lg font-black" style={{ color: postColor }}>
            {ctx?.post_name?.toUpperCase() ?? "—"}
          </div>
        </div>
        <div className="hidden sm:block">
          <div className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">
            Aktiv uskuna
          </div>
          <div className="text-sm font-semibold">
            {ctx?.machine_name ?? "—"}
          </div>
        </div>

        {/* Xarita ochiq bo'lsa skan qismi yashirin — skan faqat proyektlar ro'yxatida */}
        <div
          className={cn(
            "relative mx-auto w-full max-w-md",
            mapOpen && "invisible",
          )}
        >
          <ScanLine className="absolute left-3 top-2.5 size-5 text-muted-foreground" />
          <input
            ref={inputRef}
            disabled={!scanOn || locked || mapOpen}
            className="h-10 w-full rounded-lg border-2 border-primary/40 bg-white pl-10 pr-24 font-mono text-sm outline-none focus:border-primary disabled:bg-muted"
            placeholder={
              ctx?.session ? "QR scan qiling..." : "Beyjik QR scan qiling..."
            }
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                handleSubmit((e.target as HTMLInputElement).value)
                ;(e.target as HTMLInputElement).value = ""
              }
            }}
          />
          <div className="absolute right-2 top-2 flex items-center gap-1.5 text-[10px] font-bold text-muted-foreground">
            AVTO-SKAN
            <Switch
              checked={scanOn}
              onCheckedChange={setScanOn}
              aria-label="SKAN ON/OFF"
            />
          </div>
        </div>

        {!online && (
          <div className="flex items-center gap-1.5 rounded-lg bg-red-600 px-3 py-1.5 text-xs font-bold text-white">
            <WifiOff className="size-4" /> ALOQA YO'Q
          </div>
        )}
        <div className="num hidden text-xl font-bold md:block">{clock}</div>
        <div className="flex items-center gap-1">
          {ctx?.post_code === "ARRA" && mapOrderId !== null && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => setMapOrderId(null)}
            >
              <MapIcon /> Proyektlar
            </Button>
          )}
          <Button
            variant="ghost"
            size="icon-sm"
            onClick={() => setLocked((v) => !v)}
            title="Ekranni bloklash"
          >
            <Lock className={locked ? "text-red-600" : ""} />
          </Button>
          {ctx?.session && (
            <Button
              variant="ghost"
              size="icon-sm"
              title="Sessiyani yakunlash"
              onClick={() => endSession.mutate()}
            >
              <LogOut />
            </Button>
          )}
        </div>
      </header>

      {/* Sessiya bar */}
      <div className="flex items-center gap-2 border-b bg-white/60 px-4 py-1.5 text-sm">
        {ctx?.session ? (
          <>
            <span className="size-2 rounded-full bg-green-500" />
            <b>{ctx.session.employee_name}</b>
            <span className="text-xs text-muted-foreground">AKTIV SESSIYA</span>
          </>
        ) : (
          <>
            <span className="size-2 rounded-full bg-amber-500" />
            <span className="text-muted-foreground">
              Sessiya ochilmagan — beyjik QR ni scan qiling
            </span>
          </>
        )}
      </div>

      {/* Asosiy maydon — ARRA: proyekt ro'yxati → kesish xaritasi; boshqa postlar: vazifalar */}
      <main className="flex min-h-0 flex-1 gap-3 p-3">
        {ctx?.post_code === "ARRA" ? (
          <div className="min-h-0 flex-1">
            {mapOrderId ? (
              <CutmapView
                orderId={mapOrderId}
                onBack={() => setMapOrderId(null)}
              />
            ) : (
              <OrderPicker onPick={setMapOrderId} />
            )}
          </div>
        ) : (
          <>
            {/* Vazifalar (70%) */}
            <section className="flex min-h-0 flex-[7] flex-col rounded-xl border bg-white">
              <div className="border-b px-4 py-2 text-xs font-bold uppercase tracking-wider text-muted-foreground">
                Navbatdagi vazifalar
              </div>
              <div className="min-h-0 flex-1 overflow-y-auto">
                <table className="w-full text-sm">
                  <thead className="sticky top-0 bg-muted/80 text-left text-[11px] uppercase tracking-wider text-muted-foreground backdrop-blur">
                    <tr>
                      <th className="px-4 py-2">Kod</th>
                      <th className="px-4 py-2">Nomi</th>
                      <th className="px-4 py-2">O'lchamlari</th>
                      <th className="px-4 py-2">Muddat</th>
                      <th className="px-4 py-2 text-right">Qoldiq</th>
                    </tr>
                  </thead>
                  <tbody>
                    {tasks?.length ? (
                      tasks.map((t) => (
                        <tr
                          key={`${t.order_id}-${t.part_id}`}
                          className="border-b last:border-0"
                        >
                          <td className="num px-4 py-2.5 font-semibold">
                            {t.code}
                          </td>
                          <td className="max-w-[240px] truncate px-4 py-2.5">
                            {t.name}
                          </td>
                          <td className="num px-4 py-2.5 text-xs">
                            {formatSize(t.length, t.width, t.thickness)}
                          </td>
                          <td className="num px-4 py-2.5 text-xs">
                            {t.deadline ?? "—"}
                          </td>
                          <td className="num px-4 py-2.5 text-right text-2xl font-black text-primary">
                            {t.qoldiq}
                          </td>
                        </tr>
                      ))
                    ) : (
                      <tr>
                        <td
                          colSpan={5}
                          className="h-32 text-center text-muted-foreground"
                        >
                          Vazifalar yo'q
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </section>

            {/* O'ng panel (30%) */}
            <section className="flex min-h-0 flex-[3] flex-col gap-3">
              <div
                className={cn(
                  "rounded-xl border-2 p-4 text-center transition-colors",
                  lastScan?.kind === "ok" &&
                    "animate-pulse-once border-green-500 bg-green-50",
                  lastScan?.kind === "error" && "border-red-500 bg-red-50",
                  !lastScan && "bg-white",
                )}
              >
                <div className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">
                  Oxirgi skan
                </div>
                {lastScan ? (
                  lastScan.kind === "ok" ? (
                    <>
                      <div className="num mt-1 text-2xl font-black text-green-700">
                        {lastScan.code}
                      </div>
                      <div className="text-sm text-green-800">
                        Qoldiq: {lastScan.qoldiq}
                      </div>
                    </>
                  ) : (
                    <>
                      <div className="mt-1 text-lg font-black text-red-700">
                        {lastScan.code}
                      </div>
                      <div className="text-xs text-red-800">
                        {lastScan.message}
                      </div>
                    </>
                  )
                ) : (
                  <div className="mt-1 text-2xl text-muted-foreground">---</div>
                )}
              </div>

              <div className="flex min-h-0 flex-1 flex-col rounded-xl border bg-white">
                <div className="flex items-center justify-between border-b px-3 py-2">
                  <span className="text-xs font-bold uppercase tracking-wider text-muted-foreground">
                    Tarix
                  </span>
                  <span className="flex items-center gap-1.5 text-[10px] font-semibold text-muted-foreground">
                    Faqat xatolar
                    <Switch
                      checked={errorsOnly}
                      onCheckedChange={setErrorsOnly}
                      aria-label="Faqat xatolar"
                    />
                  </span>
                </div>
                <ul className="min-h-0 flex-1 overflow-y-auto text-xs">
                  {visibleHistory.map((h) => (
                    <li
                      key={`${h.id}-${h.time}`}
                      className={cn(
                        "border-b px-3 py-1.5 last:border-0",
                        h.ok ? "text-muted-foreground" : "text-red-600",
                      )}
                    >
                      <span className="num font-semibold">{h.code}</span> —{" "}
                      {h.note} — {h.time}
                    </li>
                  ))}
                  {!visibleHistory.length && (
                    <li className="p-3 text-muted-foreground">Bo'sh</li>
                  )}
                </ul>
              </div>

              <Button
                variant="destructive"
                size="lg"
                className="h-14 text-base font-black"
                disabled={!canUndo}
                onClick={() => setUndoOpen(true)}
              >
                <Undo2 /> BEKOR QILISH
              </Button>
            </section>
          </>
        )}
      </main>

      <ConfirmDialog
        open={undoOpen}
        onOpenChange={setUndoOpen}
        title="Oxirgi scanni bekor qilish"
        description={
          lastScan?.kind === "ok"
            ? `${lastScan.code} scan bekor qilinadi, qoldiq qaytariladi.`
            : ""
        }
        confirmText="Bekor qilish"
        destructive
        loading={undoMutation.isPending}
        onConfirm={() =>
          lastScan?.kind === "ok" && undoMutation.mutate(lastScan.scanId)
        }
      />
    </div>
  )
}

function OrderPicker({ onPick }: { onPick: (orderId: number) => void }) {
  const { data } = useQuery({
    queryKey: ["terminal", "orders"],
    queryFn: () => TerminalService.readTerminalOrders(),
    refetchInterval: 30_000,
  })
  return (
    <div className="rounded-xl border bg-white p-4">
      <h2 className="mb-3 text-sm font-bold uppercase tracking-wider text-muted-foreground">
        Proyektlar — xarita uchun proyektni tanlang
      </h2>
      <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
        {(
          data as
            | Array<{
                id: number
                number: string
                project_name?: string
                deadline?: string
              }>
            | undefined
        )?.map((o) => (
          <button
            type="button"
            key={o.id}
            onClick={() => onPick(o.id)}
            className="rounded-xl border-2 p-4 text-left hover:border-primary"
          >
            <div className="text-lg font-black">{o.number}</div>
            <div className="truncate text-sm text-muted-foreground">
              {o.project_name ?? ""}
            </div>
            <div className="num mt-1 text-xs">Muddat: {o.deadline ?? "—"}</div>
          </button>
        ))}
        {!data?.length && (
          <p className="text-sm text-muted-foreground">
            Aktiv buyurtmalar yo'q
          </p>
        )}
      </div>
    </div>
  )
}

function detailParts(err: unknown): { code: string; message: string } {
  const detail = (
    err as { body?: { detail?: { code?: string; message?: string } | string } }
  )?.body?.detail
  if (typeof detail === "object" && detail)
    return { code: detail.code ?? "XATO", message: detail.message ?? "" }
  return {
    code: "XATO",
    message: typeof detail === "string" ? detail : "Xatolik yuz berdi",
  }
}

function detailMessage(err: unknown): string {
  const { code, message } = detailParts(err)
  return message ? `${code}: ${message}` : code
}
