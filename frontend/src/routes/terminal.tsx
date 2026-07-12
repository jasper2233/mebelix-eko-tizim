// Operator terminali (TZ 8): POS monoblokda fullscreen ochiq turadigan ekran.
// Avto-skan input doim fokusda; beyjik UUID → sessiya, aks holda detal QR scan.

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute, redirect } from "@tanstack/react-router"
import {
  Expand,
  Lock,
  LogOut,
  ScanLine,
  Undo2,
  UserRound,
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
import { CutmapView, TBtn } from "@/components/Terminal/CutmapView"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { Switch } from "@/components/ui/switch"
import useAuth from "@/hooks/useAuth"
import useCurrentUser from "@/hooks/useCurrentUser"
import useCustomToast from "@/hooks/useCustomToast"
import { useMesWs } from "@/hooks/useMesWs"
import {
  formatDate,
  formatSize,
  OPERATOR_ROLES,
  POST_COLORS,
  PRIORITY_BADGE_CLASSES,
  PRIORITY_LABELS,
} from "@/lib/mes"
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
  const { data: ctx, isLoading: ctxLoading } = useQuery(
    getTerminalContextQueryOptions(),
  )
  const { data: tasks } = useQuery(getTerminalTasksQueryOptions())
  const { currentUser } = useCurrentUser()
  const { logout } = useAuth()
  const isOperator = OPERATOR_ROLES.includes(currentUser?.role as never)

  const [scanOn, setScanOn] = useState(true)
  const [locked, setLocked] = useState(false)
  const [mapOrderId, setMapOrderId] = useState<number | null>(null)
  const [lastScan, setLastScan] = useState<LastScan>(null)
  const [history, setHistory] = useState<
    Array<{ id: number; code: string; ok: boolean; note: string; time: string }>
  >([])
  const [errorsOnly, setErrorsOnly] = useState(false)
  const [undoOpen, setUndoOpen] = useState(false)
  const [logoutOpen, setLogoutOpen] = useState(false)
  // Kiosk to'liq ekran: Fullscreen API YOKI chrome --kiosk / PWA (display-mode)
  const [fullscreen, setFullscreen] = useState(
    () =>
      !!document.fullscreenElement ||
      window.matchMedia("(display-mode: fullscreen)").matches,
  )
  // Yangi build chiqdi — xavfsiz paytda avto-reload
  const [updateReady, setUpdateReady] = useState(false)
  // Xarita statlari header ichiga portal qilinadi (CutmapView statsContainer)
  const [statsEl, setStatsEl] = useState<HTMLDivElement | null>(null)
  // Xarita toolbari chap ustunga portal qilinadi (CutmapView toolbarContainer)
  const [toolbarEl, setToolbarEl] = useState<HTMLDivElement | null>(null)
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
    const mq = window.matchMedia("(display-mode: fullscreen)")
    const onFs = () => setFullscreen(!!document.fullscreenElement || mq.matches)
    document.addEventListener("fullscreenchange", onFs)
    mq.addEventListener("change", onFs)
    return () => {
      document.removeEventListener("fullscreenchange", onFs)
      mq.removeEventListener("change", onFs)
    }
  }, [])

  // Deploy'dan keyin yangi build: index.html ETag o'zgarsa belgilab qo'yamiz,
  // xavfsiz paytda (xarita yopiq, 2 daqiqa skan yo'q) o'zi reload qiladi.
  useEffect(() => {
    let etag: string | null = null
    const check = async () => {
      try {
        const r = await fetch("/", { method: "HEAD", cache: "no-store" })
        const e = r.headers.get("etag")
        if (etag === null) etag = e
        else if (e && e !== etag) setUpdateReady(true)
      } catch {
        /* oflayn — keyingi urinishda */
      }
    }
    check()
    const t = setInterval(check, 5 * 60_000)
    return () => clearInterval(t)
  }, [])

  useEffect(() => {
    if (!updateReady) return
    const tryReload = () => {
      const quiet = !lastScan || Date.now() - lastScan.at > 120_000
      if (mapOrderId === null && quiet) window.location.reload()
    }
    tryReload()
    const t = setInterval(tryReload, 30_000)
    return () => clearInterval(t)
  }, [updateReady, mapOrderId, lastScan])

  // Avto-skan: input doim fokusda (TZ 8.4.1); xarita yopilganda darhol qaytadi
  useEffect(() => {
    if (!scanOn || locked || mapOrderId !== null) return
    const focus = () => inputRef.current?.focus()
    focus()
    const t = setInterval(focus, 2000)
    return () => clearInterval(t)
  }, [scanOn, locked, mapOrderId])

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
      // Shovqinli sexda ovoz yetarli emas — xato toast bilan ham ko'rsatiladi
      showErrorToast(detailMessage(err))
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
      {/* Majburiy to'liq ekran: kiosk tartibi — to'liq ekranga o'tmaguncha ish yo'q.
          requestFullscreen user-gesture talab qiladi, shuning uchun tugma. */}
      {!fullscreen && !locked && (
        <div className="fixed inset-0 z-40 flex flex-col items-center justify-center gap-6 bg-slate-900/95 text-white">
          <Expand className="size-16 opacity-80" />
          <div className="text-2xl font-black">
            Terminal to'liq ekranda ishlaydi
          </div>
          <Button
            size="lg"
            variant="secondary"
            className="h-14 px-10 text-lg font-bold"
            onClick={() => document.documentElement.requestFullscreen()}
          >
            To'liq ekranga o'tish
          </Button>
        </div>
      )}
      {/* Qulf ekrani: tasodifiy tegishlardan himoya */}
      {locked && (
        <div className="fixed inset-0 z-50 flex flex-col items-center justify-center gap-6 bg-slate-900/95 text-white">
          <Lock className="size-16 opacity-80" />
          <div className="text-2xl font-black">Ekran qulflangan</div>
          <Button
            size="lg"
            variant="secondary"
            className="h-14 px-10 text-lg font-bold"
            onClick={() => setLocked(false)}
          >
            Ochish
          </Button>
        </div>
      )}
      {/* Header (TZ 8.3.1) */}
      <header className="flex items-center gap-4 border-b bg-white px-4 py-2 shadow-sm">
        {/* Arrachi tilida bitta identitet: stanok nomi (post rangida) — "post/uskuna"
            taksonomiyasi olib tashlandi, ism yonidagi chipda */}
        <div
          className="shrink-0 whitespace-nowrap text-xl font-black"
          style={{ color: postColor }}
        >
          {ctx?.machine_name ?? ctx?.post_name?.toUpperCase() ?? "—"}
        </div>

        {/* Sessiya — ixcham chip (alohida qator o'rniga, vertikal joy tejaladi) */}
        <div className="hidden shrink-0 items-center gap-1.5 rounded-full border bg-white px-3 py-1.5 text-sm md:flex">
          <UserRound className="size-4 text-muted-foreground" />
          {ctx?.session ? (
            <>
              <span className="size-2 rounded-full bg-green-500" />
              <b className="max-w-40 truncate">{ctx.session.employee_name}</b>
            </>
          ) : (
            <>
              <span className="size-2 rounded-full bg-amber-500" />
              <span className="text-muted-foreground">
                Beyjik QR scan qiling
              </span>
            </>
          )}
        </div>

        {/* Xarita ochiq bo'lsa skan o'rnini ixcham material statlari egallaydi */}
        <div
          className={cn(
            "relative mx-auto w-full max-w-md",
            mapOpen && "hidden",
          )}
        >
          <ScanLine className="absolute left-3 top-2.5 size-5 text-muted-foreground" />
          <input
            ref={inputRef}
            disabled={!scanOn || locked || mapOpen}
            className="h-12 w-full rounded-lg border-2 border-primary/40 bg-white pl-10 pr-4 font-mono text-base outline-none focus:border-primary disabled:bg-muted"
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
        </div>
        <div
          ref={setStatsEl}
          className={cn(
            "min-w-0 flex-1 px-4 empty:hidden",
            !mapOpen && "hidden",
          )}
        />

        {/* 48px toggle: qo'lqop bilan ham aniq; OFF holati qizil — skan to'xtagani ko'rinib tursin */}
        <Button
          variant={scanOn ? "outline" : "destructive"}
          className="h-12 shrink-0 px-3 text-xs font-black"
          onClick={() => setScanOn(!scanOn)}
        >
          <ScanLine className="size-5" />
          {scanOn ? "SKAN ON" : "SKAN OFF"}
        </Button>

        {!online && (
          <div className="flex items-center gap-1.5 rounded-lg bg-red-600 px-3 py-1.5 text-xs font-bold text-white">
            <WifiOff className="size-4" /> ALOQA YO'Q
          </div>
        )}
      </header>

      {/* Asosiy maydon — ARRA: proyekt ro'yxati → kesish xaritasi; boshqa postlar: vazifalar */}
      <main className="flex min-h-0 flex-1 gap-1.5 p-3 pl-1.5">
        {/* Chap ustun: xarita toolbari (portal) tepada, qulf/chiqish doim pastda */}
        <div className="flex w-[68px] shrink-0 flex-col gap-2">
          <div
            ref={setToolbarEl}
            className="flex flex-col gap-2 empty:hidden"
          />
          <div className="mt-auto flex flex-col gap-2">
            <TBtn label="Qulflash" tone="warn" onClick={() => setLocked(true)}>
              <Lock />
            </TBtn>
            {isOperator ? (
              <TBtn
                label="Chiqish"
                tone="danger"
                onClick={() => setLogoutOpen(true)}
              >
                <LogOut />
              </TBtn>
            ) : ctx?.session ? (
              <TBtn
                label="Yakunlash"
                tone="danger"
                onClick={() => endSession.mutate()}
              >
                <LogOut />
              </TBtn>
            ) : null}
          </div>
        </div>
        {ctxLoading && !ctx ? (
          <Skeleton className="h-full flex-1" />
        ) : ctx?.post_code === "ARRA" ? (
          <div
            className={cn(
              "flex min-h-0 min-w-0 flex-1 flex-col gap-3",
              // Xarita ochiqda tepa/past/o'ng paddingga yopishadi — xarita kattaroq
              mapOpen && "-my-3 -mr-3",
            )}
          >
            {/* Oxirgi skan + BEKOR QILISH — arra shovqinida ovozga ishonib bo'lmaydi */}
            {lastScan && (
              <div
                className={cn(
                  "flex items-center gap-3 rounded-xl border-2 px-4 py-2",
                  lastScan.kind === "ok"
                    ? "border-green-500 bg-green-50"
                    : "border-red-500 bg-red-50",
                )}
              >
                {lastScan.kind === "ok" ? (
                  <>
                    <span className="num text-xl font-black text-green-700">
                      {lastScan.code}
                    </span>
                    <span className="text-base text-green-800">
                      Qoldiq: <b>{lastScan.qoldiq}</b>
                    </span>
                  </>
                ) : (
                  <>
                    <span className="text-lg font-black text-red-700">
                      {lastScan.code}
                    </span>
                    <span className="truncate text-base text-red-800">
                      {lastScan.message}
                    </span>
                  </>
                )}
                <Button
                  variant="destructive"
                  className="ml-auto h-12 shrink-0 px-4 text-sm font-black"
                  disabled={!canUndo}
                  onClick={() => setUndoOpen(true)}
                >
                  <Undo2 /> BEKOR QILISH
                </Button>
              </div>
            )}
            <div className="min-h-0 flex-1">
              {mapOrderId ? (
                <CutmapView
                  orderId={mapOrderId}
                  onBack={() => setMapOrderId(null)}
                  statsContainer={statsEl}
                  toolbarContainer={toolbarEl}
                />
              ) : (
                <OrderPicker onPick={setMapOrderId} />
              )}
            </div>
          </div>
        ) : (
          <>
            {/* Vazifalar (70%) */}
            <section className="flex min-h-0 flex-[7] flex-col rounded-xl border bg-white">
              <div className="border-b px-4 py-2 text-xs font-bold uppercase tracking-wider text-muted-foreground">
                Navbatdagi vazifalar
              </div>
              <div className="min-h-0 flex-1 overflow-y-auto">
                <table className="w-full text-base">
                  <thead className="sticky top-0 bg-muted/80 text-left text-xs uppercase tracking-wider text-muted-foreground backdrop-blur">
                    <tr>
                      <th className="px-4 py-2.5">Kod</th>
                      <th className="px-4 py-2.5">Nomi</th>
                      <th className="px-4 py-2.5">O'lchamlari</th>
                      <th className="px-4 py-2.5">Topshirish sanasi</th>
                      <th className="px-4 py-2.5 text-right">Qoldiq</th>
                    </tr>
                  </thead>
                  <tbody>
                    {tasks?.length ? (
                      tasks.map((t) => (
                        <tr
                          key={`${t.order_id}-${t.part_id}`}
                          className="border-b last:border-0"
                        >
                          <td className="num px-4 py-3.5 font-semibold">
                            {t.code}
                          </td>
                          <td className="max-w-[240px] truncate px-4 py-3.5">
                            {t.name}
                          </td>
                          <td className="num px-4 py-3.5 text-sm">
                            {formatSize(t.length, t.width, t.thickness)}
                          </td>
                          <td className="num px-4 py-3.5 text-sm">
                            {formatDate(t.deadline)}
                          </td>
                          <td className="num px-4 py-3.5 text-right text-3xl font-black text-primary">
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
                <ul className="min-h-0 flex-1 overflow-y-auto text-sm">
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
        open={logoutOpen}
        onOpenChange={setLogoutOpen}
        title="Tizimdan chiqish"
        description="Terminal login sahifasiga qaytadi — qayta kirish uchun parol kerak bo'ladi."
        confirmText="Chiqish"
        destructive
        onConfirm={() => logout()}
      />
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

// Muddat ohangi: o'tgan = qizil, bugun = amber
function deadlineTone(value?: string | null): "overdue" | "today" | "" {
  if (!value) return ""
  const d = new Date(value)
  const today = new Date()
  d.setHours(0, 0, 0, 0)
  today.setHours(0, 0, 0, 0)
  if (d < today) return "overdue"
  if (d.getTime() === today.getTime()) return "today"
  return ""
}

function OrderPicker({ onPick }: { onPick: (orderId: number) => void }) {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["terminal", "orders"],
    queryFn: () => TerminalService.readTerminalOrders(),
    refetchInterval: 30_000,
  })
  const orders = data as
    | Array<{
        id: number
        number: string
        project_name?: string
        deadline?: string
        priority?: string
        done?: number
        total?: number
        materials?: string[]
        sheets_total?: number
        has_cutmap?: boolean
      }>
    | undefined
  return (
    <div className="h-full overflow-y-auto rounded-xl border bg-white p-4">
      <h2 className="mb-3 text-sm font-bold uppercase tracking-wider text-muted-foreground">
        Proyektlar — xarita uchun proyektni tanlang
      </h2>
      {isError && (
        <div className="mb-3 rounded-lg border-2 border-red-500 bg-red-50 px-4 py-3 text-base font-bold text-red-700">
          Yuklashda xato — qayta urinilmoqda...
        </div>
      )}
      {isLoading ? (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {[1, 2, 3, 4, 5, 6].map((i) => (
            <Skeleton key={i} className="h-44 rounded-xl" />
          ))}
        </div>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {orders?.map((o) => {
            const total = o.total ?? 0
            const done = o.done ?? 0
            const pct = total ? Math.round((done / total) * 100) : 0
            const finished = total > 0 && done >= total
            const tone = deadlineTone(o.deadline)
            return (
              <button
                type="button"
                key={o.id}
                onClick={() => onPick(o.id)}
                className={`rounded-xl border-2 p-4 text-left transition-all hover:border-primary active:scale-[0.98] active:border-primary ${
                  finished ? "border-green-500/60 bg-green-50/50" : ""
                }`}
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <div className="text-base font-black">{o.number}</div>
                    <div className="truncate text-sm text-muted-foreground">
                      {o.project_name ?? ""}
                    </div>
                  </div>
                  {o.priority && (
                    <span
                      className={`shrink-0 rounded px-2 py-0.5 text-sm font-black ${
                        PRIORITY_BADGE_CLASSES[o.priority] ??
                        "bg-muted text-muted-foreground"
                      }`}
                    >
                      {PRIORITY_LABELS[o.priority] ?? o.priority}
                    </span>
                  )}
                </div>
                {/* Material — arrachi arradagi plita bo'yicha partiyalab kesadi */}
                {!!o.materials?.length && (
                  <div className="mt-1 truncate text-sm font-semibold">
                    {o.materials.join(" · ")}
                  </div>
                )}
                {/* ARRA bo'yicha bajarilish: kesilgan nusxalar / jami */}
                <div className="mt-2">
                  <div className="h-2 overflow-hidden rounded-full bg-muted">
                    <div
                      className={`h-full rounded-full ${finished ? "bg-green-500" : "bg-primary"}`}
                      style={{ width: `${pct}%` }}
                    />
                  </div>
                  <div className="num mt-1 flex items-end justify-between">
                    {finished ? (
                      <span className="text-xl font-black text-green-600">
                        ✓ 100%
                      </span>
                    ) : (
                      <span className="text-xl font-black text-primary">
                        Qoldiq: {total - done}
                      </span>
                    )}
                    <span className="text-sm text-muted-foreground">
                      {done}/{total} detal
                      {o.sheets_total ? ` · ${o.sheets_total} list` : ""}
                    </span>
                  </div>
                </div>
                <div
                  className={`num mt-1.5 text-base font-bold ${
                    tone === "overdue"
                      ? "text-red-600"
                      : tone === "today"
                        ? "text-amber-600"
                        : ""
                  }`}
                >
                  {formatDate(o.deadline)}
                  {tone === "overdue" && " · KECHIKKAN"}
                  {tone === "today" && " · BUGUN"}
                </div>
                {o.has_cutmap === false && (
                  <span className="mt-1.5 inline-block rounded bg-muted px-2 py-0.5 text-xs font-bold text-muted-foreground">
                    XARITA YO'Q
                  </span>
                )}
              </button>
            )
          })}
          {!isError && !orders?.length && (
            <p className="text-sm text-muted-foreground">
              Aktiv buyurtmalar yo'q
            </p>
          )}
        </div>
      )}
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
