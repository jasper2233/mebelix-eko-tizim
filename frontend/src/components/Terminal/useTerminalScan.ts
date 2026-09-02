// Terminalning SKAN YO'NALTIRGICHI: bitta QR to'rt xil manzilga ketishi mumkin.
// Qoidalar terminal maketidan ajratilgan — bu domen mantiqi, joylashuv emas.
//
//   1. Beyjik UUID          -> smena ochish (2s duplikat to'sig'i ostida)
//   2. Ekranning o'z sinki  -> qadoqlash/TMO (detal qaysi qadoqqa tushishini,
//                              qabulmi yoki topshirishmi ekanini faqat o'sha
//                              ekran biladi; qadoq QR'i `PK-...` umumiy yo'lda
//                              "QR noto'g'ri formatda" bo'lib rad etilardi)
//   3. KROMKA/OVAL          -> yozishdan oldin lokal tekshiruv + 5s to'siq
//   4. Qolgani               -> umumiy skan (2s duplikat to'sig'i)

import type { RefObject } from "react"
import { useRef } from "react"
import { toast } from "sonner"

import { TerminalService } from "@/client"
import { playError, playWarning } from "@/components/Terminal/audio"
import { BADGE_RE } from "@/lib/mes"

/** Bir xil QR ikki marta o'qilganda: umumiy to'siq 2s, kromkada 5s.
 *  Kromkada tomon = skan, ya'ni skanerning takror o'qishi bitta tomonni ikki
 *  marta sanab yuborardi. */
const COOLDOWN_MS = 2000
const KROMKA_COOLDOWN_MS = 5000

export function useTerminalScan({
  postCode,
  online,
  locked,
  mapOrderId,
  viewScanRef,
  kromkaScanRef,
  onBadge,
  onScan,
  onOffline,
  openOrder,
}: {
  postCode?: string
  online: boolean
  /** Ekran qulflangan: faqat beyjik o'tadi, qolgan skanlar e'tiborsiz */
  locked: boolean
  mapOrderId: number | null
  /** Ekran o'zi yozadigan skan (qadoqlash, TMO) */
  viewScanRef: RefObject<((qr: string) => void) | null>
  /** KROMKA lokal tekshiruvi: null = yozish mumkin, "NOTFOUND" = bu proyektda
   *  yo'q, boshqa satr = ko'rsatiladigan xato */
  kromkaScanRef: RefObject<((qr: string) => string | null) | null>
  onBadge: (badgeId: string) => void
  onScan: (qr: string) => void
  onOffline: () => void
  openOrder: (orderId: number) => void
}) {
  const cooldownRef = useRef<Map<string, number>>(new Map())

  const cooled = (qr: string, ms: number) => {
    const now = Date.now()
    const last = cooldownRef.current.get(qr)
    if (last && now - last < ms) return true
    cooldownRef.current.set(qr, now)
    return false
  }

  return (raw: string) => {
    const value = raw.trim()
    if (!value) return
    if (BADGE_RE.test(value)) {
      // Skanerning takror o'qishi ikkita POST /terminal/session poygasini
      // berardi — ikkalasi ham eski smenani yopib yangisini ochardi.
      if (cooled(value, COOLDOWN_MS)) return
      onBadge(value)
      return
    }
    // Qulf ochilishi FAQAT beyjik bilan (yuqorida). Qolgan skanlar qulf ostida
    // yo'qoladi — detal skani ekran yopiqligini bilmagan operatorda hisobga
    // tushib ketmasin.
    if (locked) {
      playWarning()
      toast.error("Ekran qulflangan — beyjikni skanerlang")
      return
    }
    if (!online) {
      onOffline()
      return
    }
    if (viewScanRef.current) {
      if (cooled(value, COOLDOWN_MS)) return
      viewScanRef.current(value)
      return
    }

    if (postCode !== "KROMKA" && postCode !== "OVAL") {
      if (cooled(value, COOLDOWN_MS)) return
      onScan(value)
      return
    }

    // KROMKA/OVAL: har skan darhol yoziladi, lekin bir detal ustidagi har
    // urinish orasida 5s to'siq — rad etilgan QR ham to'siqni ishga tushiradi,
    // aks holda skanerning takror o'qishi yana bir so'rov va yana bir toast
    // beradi.
    if (cooled(value, KROMKA_COOLDOWN_MS)) {
      playWarning()
      toast.error(
        "Shu detal endigina skan qilindi — 5 soniyadan keyin qayta urining.",
      )
      return
    }
    if (mapOrderId !== null && kromkaScanRef.current) {
      const err = kromkaScanRef.current(value)
      if (err === "NOTFOUND") {
        playError()
        // Qaysi proyektga tegishli ekanini aniqlab, aniq xato ko'rsatamiz
        TerminalService.resolveTerminalQr({ path: { qr_text: value } })
          .then((r) =>
            toast.error(
              r.data.order_id === mapOrderId
                ? "Bu detal kromka bosqichiga kirmaydi."
                : `Bu detal bu proyektga tegishli emas — ${r.data.order_number} proyektining detali.`,
            ),
          )
          .catch(() =>
            toast.error(
              "Bu detal hech bir aktiv proyektda topilmadi. Chekni tekshiring.",
            ),
          )
        return
      }
      if (err) {
        playError()
        toast.error(err)
        return
      }
      onScan(value)
      return
    }
    // Picker ochiq: QR qaysi proyektga tegishli — o'sha proyekt ochiladi va
    // skan darhol yoziladi
    TerminalService.resolveTerminalQr({ path: { qr_text: value } })
      .then((r) => {
        openOrder(r.data.order_id)
        onScan(value)
      })
      .catch(() => {
        playError()
        toast.error("Bu QR uchun aktiv proyekt topilmadi.")
      })
  }
}
