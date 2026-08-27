// Operator terminali (TZ 8): POS monoblokda fullscreen ochiq turadigan ekran.
// Avto-skan input doim fokusda; beyjik UUID → sessiya, aks holda detal QR scan.

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute, redirect } from "@tanstack/react-router"
import { Grid2x2, Lock, LogOut, Printer, ScanLine, WifiOff } from "lucide-react"
import { useCallback, useEffect, useRef, useState } from "react"
import { toast } from "sonner"

import {
  type ScanResult,
  ScansService,
  type SessionRead,
  TerminalService,
} from "@/client"
import { ConfirmDialog } from "@/components/Common/ConfirmDialog"
import {
  playError,
  playSuccess,
  playWarning,
} from "@/components/Terminal/audio"
import { CutmapView } from "@/components/Terminal/CutmapView"
import { KioskOverlays } from "@/components/Terminal/KioskOverlays"
import { KromkaView } from "@/components/Terminal/KromkaView"
import { OrderPicker } from "@/components/Terminal/OrderPicker"
import { PostQueueView } from "@/components/Terminal/PostQueueView"
import { PrisadkaView } from "@/components/Terminal/PrisadkaView"
import { type LastScan, ScanStrip } from "@/components/Terminal/ScanStrip"
import { CrewChips, ShiftGate } from "@/components/Terminal/ShiftGate"
import { TBtn } from "@/components/Terminal/TBtn"
import { TmoView } from "@/components/Terminal/TmoView"
import { UpakovkaView } from "@/components/Terminal/UpakovkaView"
import {
  QUIET_MS,
  useKioskShell,
  useScanFocus,
} from "@/components/Terminal/useKiosk"
import { useTerminalScan } from "@/components/Terminal/useTerminalScan"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { useAuth } from "@/hooks/useAuth"
import { useCurrentUser } from "@/hooks/useCurrentUser"
import { useMesWs } from "@/hooks/useMesWs"
import { requireAuth } from "@/lib/guards"
import { OPERATOR_ROLES, POST_COLORS } from "@/lib/mes"
import { cn } from "@/lib/utils"
import { getTerminalContextQueryOptions } from "@/queries/mes"
import { detailMessage, detailParts } from "@/utils"

export const Route = createFileRoute("/terminal")({
  component: TerminalPage,
  head: () => ({ meta: [{ title: "Terminal | MebeliX" }] }),
  beforeLoad: async () => {
    const me = await requireAuth()
    // Terminal — HUQUQ darajasi emas, QURILMA ekrani: u ish markazi kontekstisiz
    // ishlamaydi. Ofis hisobida esa ish markazi bo'lishi MUMKIN EMAS
    // (`users._check_machine` bog'lashni taqiqlaydi). Ilgari bu yerda admin va
    // superuser uchun istisno bor edi va ular "posti uchun ekran sozlanmagan"
    // degan chalg'ituvchi ekranga tushardi — go'yo sozlama buzuq.
    if (me.role !== "terminal" && !OPERATOR_ROLES.includes(me.role as never)) {
      throw redirect({ to: "/" })
    }
  },
})

function TerminalPage() {
  const queryClient = useQueryClient()
  const {
    data: ctx,
    isLoading: ctxLoading,
    error: ctxError,
  } = useQuery(getTerminalContextQueryOptions())
  const { currentUser } = useCurrentUser()
  const { logout } = useAuth()
  const isOperator = OPERATOR_ROLES.includes(currentUser?.role as never)

  const [scanOn, setScanOn] = useState(true)
  // Oxirgi skan URINISHI vaqti (muvaffaqiyat ham, xato ham) — avto-reload
  // "tinchlik" o'lchovi; lastScan holatidan farqli, 15s da tozalanmaydi
  const lastScanAtRef = useRef(0)
  const [locked, setLocked] = useState(false)
  // ROVER: detallar ro'yxati (SCX/chek) va kesish xaritasi almashtirgichi
  const [roverMap, setRoverMap] = useState(false)
  // Ro'yxatdagi xarita ikonkasi: xarita shu detal belgilangan holda ochiladi
  const [focusPart, setFocusPart] = useState<string | undefined>(undefined)
  const [mapOrderId, setMapOrderIdRaw] = useState<number | null>(null)
  const setMapOrderId = (v: number | null) => {
    setMapOrderIdRaw(v)
    if (v === null) {
      setRoverMap(false) // keyingi proyekt detallardan boshlansin
      setFocusPart(undefined)
    }
  }
  const [lastScan, setLastScan] = useState<LastScan>(null)
  //: Shu brauzer qilgan skanlar — WS hodisasi qaytib kelganda takrorlamaslik uchun
  const ownScansRef = useRef<Set<number>>(new Set())
  //: Oxirgi xabar berilgan QR va vaqti.
  //
  //: Stanok stansiyasida bitta fizik skan IKKI yo'ldan ketadi: brauzerning
  //: skan maydoni (u doim fokusda) va agentning global klaviatura kuzatuvchisi.
  //: Ikkalasi ham serverga yozadi, ya'ni operator bir bosishga ikki xabar
  //: ko'rardi — ba'zan bir-biriga ZID: brauzerniki "bajarildi", agentniki esa
  //: "allaqachon bajarilgan" (ikkinchi so'rov E008 bilan rad etiladi).
  //: Ma'lumot to'g'ri qolgan — `total_done` ikki marta oshmaydi — muammo faqat
  //: ko'rsatishda edi.
  const notifiedRef = useRef<{ qr: string; at: number }>({ qr: "", at: 0 })
  /** Shu QR bo'yicha xabar berish kerakmi (4 soniyada bir marta).
   *  `useCallback([])` — faqat ref bilan ishlaydi, ya'ni barqaror: WS
   *  ishlov beruvchisi uni bog'liqlik sifatida olganda har renderda
   *  qayta yaratilmaydi. */
  const yangiXabar = useCallback((qr: string) => {
    const n = notifiedRef.current
    if (qr && n.qr === qr && Date.now() - n.at < 4000) return false
    notifiedRef.current = { qr, at: Date.now() }
    return true
  }, [])
  const [undoOpen, setUndoOpen] = useState(false)
  const [logoutOpen, setLogoutOpen] = useState(false)
  // Yakunlanayotgan smena — brigadada kim ekani muhim (biri ketib, ikkinchisi
  // qolishi odatiy hol)
  const [endFor, setEndFor] = useState<SessionRead | null>(null)
  // Kiosk qobig'i: to'liq ekran holati + yangi build chiqqanda avto-reload.
  // "Xavfsiz payt" = xarita yopiq va oxirgi skan urinishidan 2 daqiqa o'tgan.
  const fullscreen = useKioskShell(
    () => mapOrderId === null && Date.now() - lastScanAtRef.current > QUIET_MS,
  )
  // Xarita statlari header ichiga portal qilinadi (CutmapView statsContainer)
  const [statsEl, setStatsEl] = useState<HTMLDivElement | null>(null)
  // Xarita toolbari chap ustunga portal qilinadi (CutmapView toolbarContainer)
  const [toolbarEl, setToolbarEl] = useState<HTMLDivElement | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  // KROMKA: yozishdan oldin lokal tekshiruv (arradan chiqqanmi, tugamaganmi) —
  // null = yozish mumkin, "NOTFOUND" = bu proyektda yo'q, boshqa = xato matni
  const kromkaScanRef = useRef<((qr: string) => string | null) | null>(null)
  // Qadoqlash/TMO: skanni ekranning o'zi yozadi — detal qaysi QADOQqa
  // tushishini yoki qabulmi/topshirishmi ekanini faqat o'sha ekran biladi.
  // Qadoq QR'i (`PK-...`) umumiy yo'ldan o'tsa "QR noto'g'ri" bo'lib rad etilardi.
  const viewScanRef = useRef<((qr: string) => void) | null>(null)

  // Skan ish HOLATINI o'zgartiradi (post ekrani, buyurtma progressi), lekin
  // `context` ni — ish markazi, post, brigada — hech qachon. `["terminal"]`
  // prefiksi esa uni ham qamrab olardi va har skanga ortiqcha
  // `/terminal/context` round-trip'i qo'shardi (tsexda RTT ~100 ms).
  const invalidateWork = useCallback(
    () =>
      queryClient.invalidateQueries({
        predicate: (q) =>
          q.queryKey[0] === "terminal" && q.queryKey[1] !== "context",
      }),
    [queryClient],
  )

  // STANOK SKANERIDAN kelgan skanni ham ekranda ko'rsatamiz.
  //
  // Nanxing/prisadka stansiyasining skaneri QR'ni agentga beradi, agent esa
  // to'g'ridan-to'g'ri serverga yozadi — brauzer bu yo'lda umuman qatnashmaydi
  // va agent oynasiz fon jarayoni. Shu sababli operator na muvaffaqiyatni, na
  // "allaqachon skanerlangan" ni ko'rardi: skan bazaga tushar, ekranda esa
  // hech nima o'zgarmasdi. Server hodisani allaqachon chiqarayotgan ekan,
  // terminal uni O'ZI qilgan skan bilan bir xil banner va ovoz bilan ko'rsatadi.
  // Printer agenti holati: boshlang'ich qiymat kontekstdan (6 daqiqalik oyna),
  // jonli o'zgarish bridge.connected/disconnected dan — uzilish DARHOL ko'rinadi
  // (kontekstning o'zi last_seen tufayli 6 daqiqagacha "onlayn" deb turardi).
  const [printerLive, setPrinterLive] = useState<boolean | null>(null)
  const ctxMachineId = ctx?.machine_id
  useEffect(() => setPrinterLive(null), [ctxMachineId])
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
          invalidateWork()
        }
        const p = event.payload
        if (!ctx || p.machine_id !== ctx.machine_id) return
        if (event.type === "bridge.connected") setPrinterLive(true)
        else if (event.type === "bridge.disconnected") setPrinterLive(false)
        if (event.type === "scan.recorded") {
          const sid = Number(p.scan_id)
          // O'z skanimizni ikki marta ko'rsatmaymiz: `onSuccess` bannerni
          // allaqachon qo'ygan va unda BEKOR QILISH uchun `scanId` bor.
          if (ownScansRef.current.delete(sid)) return
          if (!yangiXabar(String(p.qr_text ?? p.part_code ?? ""))) return
          playSuccess()
          lastScanAtRef.current = Date.now()
          setLastScan({
            kind: "ok",
            code: String(p.part_code ?? ""),
            qoldiq: Number(p.qoldiq ?? 0),
            scanId: sid,
            at: Date.now(),
          })
        } else if (event.type === "scan.rejected") {
          if (!yangiXabar(String(p.qr_text ?? ""))) return
          const code = String(p.code ?? "")
          const message = String(p.message ?? "")
          // E008 — ish allaqachon bajarilgan: xato emas, neytral signal
          if (code === "E008") playWarning()
          else playError()
          lastScanAtRef.current = Date.now()
          setLastScan({ kind: "error", code, message, at: Date.now() })
          toast.error(message)
        }
      },
      [invalidateWork, ctx, yangiXabar],
    ),
  )

  // Avto-skan: input doim fokusda (TZ 8.4.1). Faqat ARRA xaritasi ochiqda
  // o'chadi (input yashirin) — KROMKA proyekt sahifasida skan doim ishlashi kerak
  const scanInputHidden = ctx?.post_code === "ARRA" && mapOrderId !== null
  // Qulf ostida ham fokus kerak: qulfning kaliti — beyjik skani
  useScanFocus(scanOn && !scanInputHidden, inputRef)

  // Smenaga QO'SHILISH rejimi: "+ Qo'shish" bosilgach keyingi tanlov brigadani
  // almashtirmaydi, ustiga qo'shadi. Sukut — almashtirish: ketayotgan odam
  // yakunlashni unutsa, keyingi kirish eski smenani yopadi (xavfsiz tomon).
  const [joining, setJoining] = useState(false)

  const startShift = useMutation({
    mutationFn: async (v: { badge_id?: string; employee_id?: number }) =>
      (
        await TerminalService.startTerminalSession({
          body: { ...v, join: joining },
        })
      ).data,
    onSuccess: (s) => {
      playSuccess()
      setLocked(false) // beyjik — qulfning kaliti
      setJoining(false)
      toast.success(`Smena ochildi: ${s.employee_name}`)
      // Faqat kontekst: sessiya ochilishi vazifalar ro'yxatini ham, kesish
      // xaritasini ham o'zgartirmaydi (["terminal"] prefiksi cutmap'ni ham olardi)
      queryClient.invalidateQueries({ queryKey: ["terminal", "context"] })
    },
    onError: (err) => {
      playError()
      toast.error(detailMessage(err))
    },
  })

  const scanMutation = useMutation({
    mutationFn: async (qr: string) =>
      (
        await ScansService.recordScan({
          body: { qr_text: qr, client_event_id: crypto.randomUUID() },
        })
      ).data,
    onSuccess: (r: ScanResult) => {
      yangiXabar(r.qr_text)
      playSuccess()
      ownScansRef.current.add(r.scan_id)
      lastScanAtRef.current = Date.now()
      // Chek/QR/SCX bilan bir xil satr — operator solishtirganda adashmasin
      setLastScan({
        kind: "ok",
        code: r.qr_text,
        qoldiq: r.qoldiq,
        scanId: r.scan_id,
        at: Date.now(),
      })
      invalidateWork()
      if (r.order_completed) toast.success("Buyurtma to'liq tayyor bo'ldi!")
      // SKAN FAYL YUKLAMAYDI. Ilgari har skanda o'sha detalning SCX'i avtomat
      // tushirilardi. Saqlangan papka tanlanmagan bo'lsa (yoki brauzer File
      // System Access API ni qo'llamasa) bu oddiy `<a download>` ga tushib,
      // har skanda brauzer yuklamasi ochilardi — operator ish o'rniga fayl
      // oynalarini yopib o'tirardi.
      //
      // Skanning ishi — bosqichni yopish, u shu yerda bajarildi. Fayl kerak
      // bo'lsa operator "Hammasini yuklab olish" ni bir marta bosadi.
    },
    onError: (err, qr) => {
      if (!yangiXabar(qr)) return
      lastScanAtRef.current = Date.now()
      const { code, message } = detailParts(err)
      // Ovoz KOD bo'yicha tanlanadi, matn bo'yicha emas: ilgari o'zbekcha
      // xabardan "yakunlangan" bo'lagi qidirilardi va matn tahrirlansa jimgina
      // buzilardi. E008 — ish allaqachon bajarilgan, bu xato emas: neytral signal.
      // ATX — qoldiq QR: xato emas, ma'lumot (o'lcham, buyurtma, list).
      // Qoldiq marshrutda yurmaydi, skan hech narsani yopmaydi.
      if (code === "ATX") {
        playWarning()
        setLastScan({ kind: "info", code, message, at: Date.now() })
        return
      }
      if (code === "E008") playWarning()
      else playError()
      // Shovqinli tsexda ovoz yetarli emas — xato toast bilan ham ko'rsatiladi
      toast.error(detailMessage(err))
      setLastScan({ kind: "error", code, message, at: Date.now() })
    },
  })

  const undoMutation = useMutation({
    mutationFn: (scanId: number) =>
      ScansService.cancelScan({ path: { scan_id: scanId } }),
    onSuccess: () => {
      playWarning()
      toast.success("Oxirgi scan bekor qilindi")
      setUndoOpen(false)
      setLastScan(null)
      invalidateWork()
    },
    onError: (err) => {
      toast.error(detailMessage(err))
      setUndoOpen(false)
    },
  })

  const endSession = useMutation({
    mutationFn: (employeeId?: number) =>
      TerminalService.endTerminalSession({
        query: { employee_id: employeeId },
      }),
    onSettled: () =>
      queryClient.invalidateQueries({ queryKey: ["terminal", "context"] }),
  })

  const handleSubmit = useTerminalScan({
    postCode: ctx?.post_code,
    online,
    locked,
    mapOrderId,
    viewScanRef,
    kromkaScanRef,
    onBadge: (badge) => startShift.mutate({ badge_id: badge }),
    onScan: (qr) => scanMutation.mutate(qr),
    onOffline: () => {
      playError()
      setLastScan({
        kind: "error",
        code: "E007",
        message: "Aloqa yo'q, qaytadan urining",
        at: Date.now(),
      })
    },
    openOrder: setMapOrderId,
  })

  const crew = ctx?.crew ?? []
  // "Kim ishlayapti?" FAQAT "+ Qo'shish" bosilganda ochiladi.
  //
  // Tsex hisobi bilan kirgan operator kimligini LOGIN allaqachon aytgan va
  // `login._open_shift_for` uning smenasini ochib bergan - ustiga savol berish
  // bitta faktni ikki marta so'rash bo'lardi. Ilgari savol bo'sh brigadada
  // avtomat ochilardi, natijada chiqishda ekran hisobdan chiqmay "Kim
  // ishlayapti?" ga qaytib qolardi.
  //
  // Qurilma hisobi (TERMINAL) uchun savol SHART: monoblokda login kim
  // ishlayotganini aytmaydi, ro'yxat aytadi.
  const gateOpen = !!ctx && (joining || (!isOperator && !crew.length))
  const { data: shiftEmployees } = useQuery({
    queryKey: ["terminal", "employees"],
    queryFn: async () => (await TerminalService.readTerminalEmployees()).data,
    enabled: gateOpen,
    staleTime: 60_000,
  })

  const mapOpen = scanInputHidden
  // BEKOR QILISH oynasi 60 s (TZ 8.6). Vaqtga bog'liq bo'lgani uchun taymer
  // kerak: busiz tugma muddat o'tgach ham yoqilgan ko'rinib turardi va
  // bosilganda server rad etardi.
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    if (lastScan?.kind !== "ok") return
    const left = 60_000 - (Date.now() - lastScan.at)
    if (left <= 0) return
    const t = setTimeout(() => setNow(Date.now()), left)
    return () => clearTimeout(t)
  }, [lastScan])
  const canUndo = lastScan?.kind === "ok" && now - lastScan.at < 60_000

  // Skan chizig'i 15s dan keyin o'zi yo'qoladi — ekranni band qilib turmasin;
  // har yangi skan taymerni qaytadan boshlaydi
  useEffect(() => {
    if (!lastScan) return
    const t = setTimeout(() => setLastScan(null), 15_000)
    return () => clearTimeout(t)
  }, [lastScan])
  const postColor = ctx
    ? (POST_COLORS[ctx.post_code] ?? "var(--primary)")
    : "var(--primary)"

  const scanStrip = (
    <ScanStrip
      scan={lastScan}
      canUndo={canUndo}
      onUndo={() => setUndoOpen(true)}
      birlik={ctx?.post_code === "KROMKA" ? "qirra" : undefined}
    />
  )

  return (
    // `select-none` BUTUN terminalga: sensorli monoblokda surish yoki uzoq
    // bosish matnni ko'kartirib belgilab qo'yardi va u ekranda osilib qolardi
    // (tsexda "bo'sh joyga bosib bekor qilish" odati yo'q). Kioskda matn
    // tanlashning ma'nosi ham yo'q — nusxa olib boradigan joy yo'q.
    //
    // Radix dialoglari portal orqali `body` ga chiqadi, ya'ni ular bu qoidani
    // MEROS QILMAYDI — tasdiq oynalaridagi matn odatdagidek qoladi.
    <div className="flex h-dvh select-none flex-col bg-surface">
      <KioskOverlays
        fullscreen={fullscreen}
        locked={locked}
        onLogout={() => logout()}
      />
      {/* Smena ochilmaguncha ish maydoni o'rniga ismlar turadi — alohida oqim
          emas, bitta to'siq. Qulf va to'liq ekran to'siqlari ustunroq. */}
      {gateOpen && fullscreen && !locked && (
        <ShiftGate
          employees={shiftEmployees ?? []}
          pending={startShift.isPending}
          onStart={(employee_id) => startShift.mutate({ employee_id })}
          onCancel={joining ? () => setJoining(false) : undefined}
        />
      )}
      {/* Header (TZ 8.3.1) */}
      <header className="flex items-center gap-4 border-b bg-card px-4 py-2 shadow-sm">
        {/* Arrachi tilida bitta identitet: ish markazi nomi (post rangida) — "post/uskuna"
            taksonomiyasi olib tashlandi, ism yonidagi chipda */}
        <div
          className="shrink-0 whitespace-nowrap text-xl font-black"
          style={{ color: postColor }}
        >
          {ctx?.machine_name ?? ctx?.post_name?.toUpperCase() ?? "—"}
        </div>

        {/* MES agent uzilganda QIZIL chip; boshqa hamma holatda HECH NARSA.
            Onlayn holat ko'rsatilmaydi: tray o'sha mashinada doimiy holatni
            beradi, terminalda dublikat shovqin bo'lardi — chip yo'qolishi
            "tuzaldi" tasdig'i. Faqat agent biriktirilgan postda ma'no bor
            (agent_online null = signal yo'q). Matn ikonkasiz emas: qizil
            belgi yolg'iz o'zini tushuntirmaydi. Ikonka rolni aytadi
            (printer / skaner). Cheklar baribir yo'qolmaydi — ogohlantirish. */}
        {(printerLive ?? ctx?.agent_online) === false && (
          <div className="flex shrink-0 items-center gap-1.5 rounded-md bg-red-600 px-2 py-1 text-sm font-bold text-white">
            {ctx?.agent_prints ? (
              <Printer className="size-4" />
            ) : (
              <ScanLine className="size-4" />
            )}
            AGENT UZILGAN
          </div>
        )}

        {/* Brigada — ixcham chiplar (alohida qator o'rniga, vertikal joy tejaladi).
            Ismni bosish o'sha odamning smenasini yakunlaydi. */}
        <CrewChips
          crew={crew}
          onEnd={setEndFor}
          onAdd={() => setJoining(true)}
        />

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
            disabled={!scanOn || mapOpen}
            // Maydon ichida tanlash QOLADI: skaner yozgan qiymatni qo'lda
            // to'g'rilash kerak bo'lib qolsa, ildizdagi `select-none` to'sib
            // qo'ymasin.
            className="h-12 w-full select-text rounded-lg border-2 border-primary/40 bg-card pl-10 pr-4 font-mono text-base outline-none focus:border-primary disabled:bg-muted"
            placeholder={
              crew.length ? "QR scan qiling..." : "Beyjik QR scan qiling..."
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
          {/* ROVER: detallar <-> kesish xaritasi. Terminalning barcha amallari
              shu 68px chap ustunda — xarita toolbari ham shu yerga portal
              qilinadi, ya'ni ikkita vertikal qator paydo bo'lmaydi. */}
          {ctx?.post_code === "ROVER" && mapOrderId !== null && !roverMap && (
            <TBtn label="Xarita" onClick={() => setRoverMap(true)}>
              <Grid2x2 />
            </TBtn>
          )}
          <div
            ref={setToolbarEl}
            className="flex flex-col gap-2 empty:hidden"
          />
          <div className="mt-auto flex flex-col gap-2">
            <TBtn label="Qulflash" tone="warn" onClick={() => setLocked(true)}>
              <Lock />
            </TBtn>
            {/* Tsex hisobi bilan kirgan odam uchun bitta tugma: CHIQISH.
                U hisobdan ham chiqaradi, smenani ham yopadi (backend `logout`
                o'zi yopadi). Ilgari avval "Yakunlash" chiqar, bosilgach ekran
                hisobda qolgan holda "Kim ishlayapti?" ga tushib qolardi -
                chiqish ikki bosqichli va chalkash edi.

                Sherikning smenasi sarlavhadagi chipini bosib yopiladi.

                Qurilma hisobida (TERMINAL) chiqish yo'q - monoblok bir marta,
                o'rnatishda kiradi; u yerda faqat smenani yakunlash kerak. */}
            {isOperator ? (
              <TBtn
                label="Chiqish"
                tone="danger"
                onClick={() => setLogoutOpen(true)}
              >
                <LogOut />
              </TBtn>
            ) : crew.length ? (
              <TBtn
                label="Yakunlash"
                tone="danger"
                onClick={() => setEndFor(crew[0] ?? null)}
              >
                <LogOut />
              </TBtn>
            ) : null}
          </div>
        </div>
        {ctxLoading && !ctx ? (
          <Skeleton className="h-full flex-1" />
        ) : !ctx && ctxError ? (
          /* Kontekst xatosi (masalan postda ish markazi yo'q) yutilmasin — sabab
             ekranda tursin, aks holda "hech nima chiqmayapti" bo'lib qoladi */
          <div className="flex flex-1 flex-col items-center justify-center gap-3 text-center">
            <WifiOff className="size-12 text-destructive/60" />
            <div className="max-w-md text-lg font-bold text-destructive">
              {detailMessage(ctxError)}
            </div>
            <p className="text-sm text-muted-foreground">
              Muammo hal bo'lgach sahifa o'zi yangilanadi.
            </p>
          </div>
        ) : ctx?.post_code === "ARRA" ? (
          <PostScreen
            strip={scanStrip}
            // Xarita ochiqda tepa/past/o'ng paddingga yopishadi — xarita kattaroq
            className={cn(mapOpen && "-my-3 -mr-3")}
          >
            {mapOrderId ? (
              <CutmapView
                orderId={mapOrderId}
                onBack={() => setMapOrderId(null)}
                statsContainer={statsEl}
                toolbarContainer={toolbarEl}
                postCode={ctx?.post_code}
              />
            ) : (
              <OrderPicker onPick={setMapOrderId} />
            )}
          </PostScreen>
        ) : ["PRISADKA", "ROVER"].includes(ctx?.post_code ?? "") ? (
          /* CNC postlar (PRISADKA/ROVER): proyekt ro'yxati → detallar + SCX
             fayllar; ROVER'da arra'siz detalga QR chiqarish ham shu sahifada */
          <PostScreen strip={scanStrip}>
            {mapOrderId && ctx?.post_code === "ROVER" && roverMap ? (
              <CutmapView
                orderId={mapOrderId}
                onBack={() => setRoverMap(false)}
                toolbarContainer={toolbarEl}
                postCode={ctx?.post_code}
                focusPartKey={focusPart}
              />
            ) : mapOrderId ? (
              <PrisadkaView
                orderId={mapOrderId}
                onBack={() => setMapOrderId(null)}
                showScx={ctx?.post_code !== "ROVER"}
                toolbarContainer={toolbarEl}
                onShowOnMap={
                  ctx?.post_code === "ROVER"
                    ? (partCode) => {
                        setFocusPart(partCode)
                        setRoverMap(true)
                      }
                    : undefined
                }
              />
            ) : (
              <OrderPicker
                onPick={setMapOrderId}
                title="Proyektlar — detallar uchun proyektni tanlang"
                showCutmapBadge={false}
              />
            )}
          </PostScreen>
        ) : ctx?.post_code === "UPAKOVKA" ? (
          /* QADOQLASH: proyekt ro'yxati → qadoq yig'ish ekrani */
          <PostScreen strip={scanStrip}>
            {mapOrderId ? (
              <UpakovkaView
                orderId={mapOrderId}
                onBack={() => setMapOrderId(null)}
                registerScan={(fn) => {
                  viewScanRef.current = fn
                }}
              />
            ) : (
              <OrderPicker
                onPick={setMapOrderId}
                title="Proyektlar — qadoqlash uchun proyektni tanlang"
                showCutmapBadge={false}
              />
            )}
          </PostScreen>
        ) : ["BOYOQ", "STOLYARKA"].includes(ctx?.post_code ?? "") ? (
          /* BOYOQ / STOLYARKA: proyekt ro'yxati -> shu postga yetib kelgan nusxalar */
          <PostScreen strip={scanStrip}>
            {mapOrderId ? (
              <PostQueueView
                orderId={mapOrderId}
                onBack={() => setMapOrderId(null)}
              />
            ) : (
              <OrderPicker
                onPick={setMapOrderId}
                title="Proyektlar — ish uchun proyektni tanlang"
                showCutmapBadge={false}
              />
            )}
          </PostScreen>
        ) : ctx?.post_code === "TMO" ? (
          /* TMO: proyekt ro'yxati → qabul va topshirish tablari */
          <PostScreen strip={scanStrip}>
            {mapOrderId ? (
              <TmoView
                orderId={mapOrderId}
                onBack={() => setMapOrderId(null)}
                registerScan={(fn) => {
                  viewScanRef.current = fn
                }}
              />
            ) : (
              <OrderPicker
                onPick={setMapOrderId}
                title="Proyektlar — TMO uchun proyektni tanlang"
                showCutmapBadge={false}
              />
            )}
          </PostScreen>
        ) : ctx?.post_code === "KROMKA" || ctx?.post_code === "OVAL" ? (
          /* KROMKA/OVAL: proyekt ro'yxati → detallar ro'yxati (tomon-progress;
             OVAL'da har detal 1 skan, Jarayonda paneli yo'q) */
          <PostScreen strip={scanStrip}>
            {mapOrderId ? (
              <KromkaView
                orderId={mapOrderId}
                onBack={() => setMapOrderId(null)}
                registerScan={(fn) => {
                  kromkaScanRef.current = fn
                }}
                oval={ctx?.post_code === "OVAL"}
              />
            ) : (
              <OrderPicker
                onPick={setMapOrderId}
                title="Proyektlar — detallar uchun proyektni tanlang"
                showCutmapBadge={false}
              />
            )}
          </PostScreen>
        ) : (
          /* Bu shoxga tushish uchun postning O'Z ekrani bo'lmasligi kerak.
             Hozir 9 postning HAMMASIDA o'z ekrani bor — bu faqat kelajakda
             yangi post qo'shilib, ekrani unutilgan holat uchun sug'urta. Ilgari bu
             yerda umumiy "Navbatdagi vazifalar" jadvali turardi: u detal
             darajasidagi agregat berardi va navbatni hisobga olmasdi, shuning
             uchun har post o'z ekraniga ko'chirilgan va jadval o'lik qolgan. */
          <div className="flex flex-1 flex-col items-center justify-center gap-3 text-center">
            <div className="text-lg font-bold">
              {ctx?.post_name} posti uchun ekran sozlanmagan
            </div>
            <p className="text-sm text-muted-foreground">
              Dasturchiga murojaat qiling.
            </p>
          </div>
        )}
      </main>

      <ConfirmDialog
        open={logoutOpen}
        onOpenChange={setLogoutOpen}
        title="Tizimdan chiqish"
        description="Smenangiz yopiladi va terminal login sahifasiga qaytadi — qayta kirish uchun parol kerak bo'ladi."
        confirmText="Chiqish"
        destructive
        onConfirm={() => logout()}
      />
      <ConfirmDialog
        open={!!endFor}
        onOpenChange={(v) => !v && setEndFor(null)}
        title="Smenani yakunlash"
        description={`${endFor?.employee_name ?? "Hodim"} smenasi yopiladi. Brigadaning qolgani ishlayveradi.`}
        confirmText="Yakunlash"
        destructive
        loading={endSession.isPending}
        onConfirm={() =>
          endFor &&
          endSession.mutate(endFor.employee_id, {
            onSuccess: () => {
              setEndFor(null)
              toast.success("Smena yakunlandi")
            },
          })
        }
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
        confirmText="Scanni bekor qilish"
        cancelText="Yopish"
        destructive
        loading={undoMutation.isPending}
        onConfirm={() =>
          lastScan?.kind === "ok" && undoMutation.mutate(lastScan.scanId)
        }
      />
    </div>
  )
}

/** Har post ekranining bir xil o'rami: tepada oxirgi skan chizig'i, ostida
 *  ekranning o'zi. Oltita shoxda bir xil markup takrorlanardi. */
function PostScreen({
  strip,
  className,
  children,
}: {
  strip: React.ReactNode
  className?: string
  children: React.ReactNode
}) {
  return (
    <div
      className={cn("flex min-h-0 min-w-0 flex-1 flex-col gap-3", className)}
    >
      {strip}
      <div className="min-h-0 flex-1">{children}</div>
    </div>
  )
}
