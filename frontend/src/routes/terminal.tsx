// Operator terminali: POS monoblokda fullscreen ochiq turadigan ekran.
// Avto-skan input doim fokusda; beyjik UUID → sessiya, aks holda detal QR scan.

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute, redirect } from "@tanstack/react-router"
import {
  Grid2x2,
  Lock,
  LogOut,
  MonitorX,
  ScanLine,
  WifiOff,
} from "lucide-react"
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
    if (me.role !== "terminal" && !OPERATOR_ROLES.includes(me.role)) {
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
  const isOperator = !!currentUser && OPERATOR_ROLES.includes(currentUser.role)

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
  // Bekor qilinayotgan skan — dialog OCHILGANDA suratga olinadi. `lastScan`
  // 15 s da tozalanadi, ya'ni dialog ochiqligicha qolsa tasdiqlash tugmasi jim
  // no-op bo'lib qolardi.
  const [undoFor, setUndoFor] = useState<{
    scanId: number
    code: string
  } | null>(null)
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
  // MES agent holati: boshlang'ich qiymat kontekstdan (6 daqiqalik oyna),
  // jonli o'zgarish bridge.connected/disconnected dan — uzilish DARHOL ko'rinadi
  // (kontekstning o'zi last_seen tufayli 6 daqiqagacha "onlayn" deb turardi).
  const [printerLive, setPrinterLive] = useState<boolean | null>(null)
  const ctxMachineId = ctx?.machine_id
  // Ish markazi almashdi — eski jonli override endi boshqa mashinaga tegishli
  useEffect(() => {
    if (ctxMachineId !== undefined) setPrinterLive(null)
  }, [ctxMachineId])
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
          // Chek chiqarishdan tug'ilgan AVTO-skan (payload.auto — server qo'yadi):
          // muvaffaqiyat banneri chiqmaydi. Chek bosilgan katak o'zi yashil
          // bo'ladi — banner dublikat shovqin edi, undagi BEKOR QILISH esa
          // yarim-tuzoq: skanni qaytarib chek bayrog'ini qoldirardi (to'liq
          // bekor — katak dialogida). Post nomi bo'yicha EMAS: ROVER ham chek
          // chiqaradi, ham qo'lda skan oladi — farq skanning kelib chiqishida.
          // XATO baribir pastdagi scan.rejected shoxidan ko'rinadi.
          if (p.auto) return
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

  // Avto-skan: input doim fokusda. ARRA xaritasi ochiqda o'chadi
  // (input yashirin) — KROMKA proyekt sahifasida skan doim ishlashi kerak.
  const mapOpen = ctx?.post_code === "ARRA" && mapOrderId !== null
  // Tasdiq dialogi ochiqda ham o'chadi: input modaldan tashqarida, ya'ni
  // interval/keydown fokusni tortadi, Radix trap darhol qaytaradi — churn
  const dialogOpen = logoutOpen || endFor !== null || undoFor !== null
  // Qulf ostida ham fokus kerak: qulfning kaliti — beyjik skani
  useScanFocus(scanOn && !mapOpen && !dialogOpen, inputRef)

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
      setUndoFor(null)
      setLastScan(null)
      invalidateWork()
    },
    onError: (err) => {
      toast.error(detailMessage(err))
      setUndoFor(null)
    },
  })

  const endSession = useMutation({
    mutationFn: (employeeId?: number) =>
      TerminalService.endTerminalSession({
        query: { employee_id: employeeId },
      }),
    onError: (err) => {
      playError()
      toast.error(detailMessage(err))
      setEndFor(null)
    },
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
    // Ikkilamchi to'siq: oldingi so'rov javob bermaguncha yangisi ketmaydi
    onBadge: (badge) => {
      lastScanAtRef.current = Date.now()
      if (startShift.isPending) return
      startShift.mutate({ badge_id: badge })
    },
    onScan: (qr) => scanMutation.mutate(qr),
    onOffline: () => {
      // Aloqasiz skan ham operator FAOL ekanining belgisi: avto-reload
      // "tinchlik" o'lchovini boshqa yo'llar bilan bir xil yangilaymiz.
      lastScanAtRef.current = Date.now()
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

  // BEKOR QILISH oynasi serverda 60 s (`SCAN_UNDO_SECONDS`, undan keyin
  // faqat admin). Chiziq ham AYNAN 60 s turadi: ilgari 15 s da yo'qolar edi —
  // tugma bilan birga, ya'ni 20-soniyada xatoni sezgan ishchi bekor qila
  // olmasdi (server hali ruxsat bergan holda). Muddat taymeri yo'q — tugma
  // bor ekan, bekor qilish mumkin.
  const canUndo = lastScan?.kind === "ok"

  // Skan chizig'i 60 s dan keyin o'zi yo'qoladi — ekranni band qilib turmasin;
  // har yangi skan taymerni qaytadan boshlaydi
  useEffect(() => {
    if (!lastScan) return
    const t = setTimeout(() => setLastScan(null), 60_000)
    return () => clearTimeout(t)
  }, [lastScan])
  const postColor = ctx
    ? (POST_COLORS[ctx.post_code] ?? "var(--primary)")
    : "var(--primary)"
  // Chap toolbar ustuni kimga kerak: ARRA xarita ochiq (toolbar portal),
  // ROVER proyekt ichida (Xarita/Chop etish). Qolganlarda — yo'q.
  const leftColumn =
    mapOrderId !== null &&
    (ctx?.post_code === "ARRA" || ctx?.post_code === "ROVER")

  // Proyekt tanlagich: ARRA'dan boshqa hamma postda bir xil, faqat sarlavha
  // farq qiladi (kesish xaritasi bejigi ham faqat ARRA'da ma'noga ega)
  const picker = (title: string) => (
    <OrderPicker onPick={setMapOrderId} title={title} showCutmapBadge={false} />
  )

  const scanStrip = (
    <ScanStrip
      scan={lastScan}
      canUndo={canUndo}
      onUndo={() =>
        lastScan?.kind === "ok" &&
        setUndoFor({ scanId: lastScan.scanId, code: lastScan.code })
      }
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
      {/* Header */}
      <header className="flex items-center gap-3 border-b bg-card px-4 py-2 shadow-sm">
        {/* Arrachi tilida bitta identitet: ish markazi nomi (post rangida) — "post/uskuna"
            taksonomiyasi olib tashlandi, ism yonidagi chipda */}
        <div
          className="shrink-0 whitespace-nowrap text-xl font-black"
          style={{ color: postColor }}
        >
          {ctx?.machine_name ?? "—"}
        </div>

        {/* MES agent uzilganda QIZIL chip; boshqa hamma holatda HECH NARSA.
            Onlayn holat ko'rsatilmaydi: tray o'sha mashinada doimiy holatni
            beradi, terminalda dublikat shovqin bo'lardi — chip yo'qolishi
            "tuzaldi" tasdig'i. Faqat agent biriktirilgan postda ma'no bor
            (agent_online null = signal yo'q). Matn ikonkasiz emas: qizil
            belgi yolg'iz o'zini tushuntirmaydi. Ikonka rolni aytadi
            (printer / skaner). Cheklar baribir yo'qolmaydi — ogohlantirish. */}
        {(printerLive ?? ctx?.agent_online) === false && (
          <div
            className="flex h-12 w-12 shrink-0 animate-pulse items-center justify-center rounded-lg bg-red-600 text-white"
            role="status"
            title="MES agent uzilgan — chek chiqmaydi / stanok skani yozilmaydi"
            aria-label="MES agent uzilgan"
          >
            {/* Faqat ikonka (qulf/chiqish bilan bir uslub): uzilgan ekran
                belgisi + qizil + sekin puls — matnsiz ham «uzilgan» deydi,
                header joyi tejaladi. Agent — tsex kompyuteri (sidebar
                MonitorCog bilan bir oila). */}
            <MonitorX className="size-6" />
          </div>
        )}

        {/* Brigada — ixcham chiplar (alohida qator o'rniga, vertikal joy tejaladi).
            Ismni bosish o'sha odamning smenasini yakunlaydi. */}
        <CrewChips
          crew={crew}
          onEnd={setEndFor}
          onAdd={() => setJoining(true)}
        />

        {/* Skan maydoni IXCHAM: ishchi unga yozmaydi, skaner yozadi — 448px li
            matn maydoni header markazini bekorga egallardi. Endi holat chipi
            ko'rinishida (224px): «Skan tayyor» / «Beyjik kuting»; skaner
            yozgan matn bir zum ko'rinib turadi (nosozlikda foydali).
            Xarita ochiq bo'lsa o'rnini ixcham material statlari egallaydi. */}
        <div
          className={cn("relative mx-auto w-44 shrink-0", mapOpen && "hidden")}
        >
          {/* Tayyor holatda ikonka yengil pulsatsiya qiladi — «skan kutyapman»
              signali; skan o'chiq / smena yo'q bo'lsa jim kulrang */}
          <ScanLine
            className={cn(
              "absolute left-3 top-3 size-5",
              scanOn && crew.length
                ? "animate-pulse text-primary"
                : "text-muted-foreground",
            )}
          />
          <input
            ref={inputRef}
            disabled={!scanOn || mapOpen}
            // Maydon ichida tanlash QOLADI: skaner yozgan qiymatni qo'lda
            // to'g'rilash kerak bo'lib qolsa, ildizdagi `select-none` to'sib
            // qo'ymasin.
            className="h-12 w-full select-text rounded-full border-2 border-primary/40 bg-card pl-10 pr-4 font-mono text-sm outline-none focus:border-primary disabled:bg-muted"
            placeholder={crew.length ? "Skan tayyor" : "Beyjik kuting"}
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

        {/* Qulflash / Chiqish HEADERDA: ilgari 68px li chap ustunda turardi,
            9 postdan 7 tasida o'sha ustunda boshqa hech narsa yo'q edi —
            kontentdan bekorga joy olardi. Chap ustun endi faqat xarita
            toolbari bo'lganda (ARRA xarita, ROVER) chiziladi. */}
        {/* Qulf — faqat ikonka: qulf belgisi universal, matn 1366px headerda
            (2 kishilik brigada + chip + skan) sig'may CHIQISH ni kesardi */}
        <Button
          variant="outline"
          className="h-12 w-12 shrink-0 text-amber-700 hover:text-amber-800"
          aria-label="Qulflash"
          title="Qulflash"
          onClick={() => setLocked(true)}
        >
          <Lock className="size-6" />
        </Button>
        {/* Tsex hisobi bilan kirgan odam uchun bitta tugma: CHIQISH — hisobdan
            ham chiqaradi, smenani ham yopadi (backend `logout` o'zi yopadi).
            Sherikning smenasi sarlavhadagi chipini bosib yopiladi. Qurilma
            hisobida (TERMINAL) chiqish yo'q — monoblok bir marta, o'rnatishda
            kiradi; u yerda faqat smenani yakunlash. */}
        {isOperator ? (
          <Button
            variant="destructive"
            className="h-12 w-12 shrink-0"
            aria-label="Chiqish"
            title="Chiqish"
            onClick={() => setLogoutOpen(true)}
          >
            <LogOut className="size-6" />
          </Button>
        ) : crew.length ? (
          <Button
            variant="destructive"
            className="h-12 w-12 shrink-0"
            aria-label="Smenani yakunlash"
            title="Smenani yakunlash"
            onClick={() => setEndFor(crew[0] ?? null)}
          >
            <LogOut className="size-6" />
          </Button>
        ) : null}

        {!online && (
          <div className="flex items-center gap-1.5 rounded-lg bg-red-600 px-3 py-1.5 text-xs font-bold text-white">
            <WifiOff className="size-4" /> ALOQA YO'Q
          </div>
        )}
      </header>

      {/* Asosiy maydon — har postning O'Z ekrani: proyekt ro'yxati → post ekrani
          (ARRA'da kesish xaritasi). Umumiy vazifalar jadvali yo'q. */}
      <main
        className={cn(
          "flex min-h-0 flex-1 gap-1.5 p-3",
          leftColumn ? "pl-1.5" : "pl-3",
        )}
      >
        {/* Chap ustun FAQAT xarita toolbari bo'lganda: ARRA xarita ochiq,
            ROVER proyekt ichida (Xarita/Chop etish tugmalari + xarita
            toolbari portal bilan shu yerga). Qolgan postlarda ustun yo'q —
            kontent butun kenglikni oladi. Qulflash/Chiqish headerda. */}
        {leftColumn && (
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
          </div>
        )}
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
              picker("Proyektlar — detallar uchun proyektni tanlang")
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
              picker("Proyektlar — qadoqlash uchun proyektni tanlang")
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
              picker("Proyektlar — ish uchun proyektni tanlang")
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
              picker("Proyektlar — TMO uchun proyektni tanlang")
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
              picker("Proyektlar — detallar uchun proyektni tanlang")
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
        open={!!undoFor}
        onOpenChange={(v) => !v && setUndoFor(null)}
        title="Oxirgi scanni bekor qilish"
        description={
          undoFor
            ? `${undoFor.code} scan bekor qilinadi, qoldiq qaytariladi.`
            : ""
        }
        confirmText="Scanni bekor qilish"
        cancelText="Yopish"
        destructive
        loading={undoMutation.isPending}
        onConfirm={() => undoFor && undoMutation.mutate(undoFor.scanId)}
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
