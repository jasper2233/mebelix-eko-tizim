import { AxiosError } from "axios"
import { toast } from "sonner"

/** Server javob tanasidagi `detail` — FastAPI xatosining yagona konverti.
 * Klient (`@hey-api/client-axios`) HAR QANDAY xatoni `AxiosError` qilib
 * tashlaydi, ya'ni 4xx tanasi `err.response.data` da keladi. */
function errorDetail(err: unknown): unknown {
  return err instanceof AxiosError
    ? (err.response?.data as { detail?: unknown } | undefined)?.detail
    : undefined
}

/** Server TUZILMALI xato bermagan holat uchun xabar.
 *
 * Backendning o'z xatolari (`{code, message}` yoki `detail`) allaqachon
 * o'zbekcha va nima qilishni aytadi — ular shu funksiyagacha yetib kelmaydi.
 * Bu yerga faqat konvertsiz holatlar tushadi: 500 da FastAPI JSON emas, oddiy
 * matn qaytaradi; 502/504 esa Caddy'ning HTML sahifasi. Ilgari ikkalasi ham
 * axiosning inglizcha matniga tushardi — tsexdagi operator "Request failed with
 * status code 500" ni ko'rardi va na sababini, na nima qilishni bilardi.
 *
 * Har xabar ikki savolga javob beradi: nima bo'ldi va endi nima qilay.
 */
function holatXabari(status: number | undefined): string {
  if (status === undefined) return "Server javob bermadi — qayta urinib ko'ring"
  if (status === 401 || status === 403)
    return "Sessiya tugadi — qaytadan kiring"
  if (status === 404) return "Ma'lumot topilmadi — sahifani yangilang"
  if (status === 413) return "Fayl juda katta"
  if (status === 429) return "Juda ko'p so'rov — biroz kutib qayta urining"
  // Deploy paytida API qayta ishga tushadi: bu o'z-o'zidan tuzaladi
  if (status === 502 || status === 503 || status === 504)
    return "Server yangilanmoqda — bir necha soniyadan keyin qayta urining"
  if (status >= 500)
    return "Serverda xatolik — qayta urining. Takrorlansa texnologga ayting"
  return "So'rov bajarilmadi — qayta urinib ko'ring"
}

/** Har qanday xatoni {code, message} ga keltiradi — YAGONA zinapoya. `code` skan oqimi uchun (E001
 *  → ovoz); `structured` — server haqiqiy MES konvertini qaytargan, shundagina kod matnga qo'shiladi. */
export function detailParts(err: unknown): {
  code: string
  message: string
  structured: boolean
} {
  const plain = (code: string, message: string) => ({
    code,
    message,
    structured: false,
  })

  if (err instanceof AxiosError && err.code === AxiosError.ERR_NETWORK)
    return plain("TARMOQ", "Tarmoq xatosi — internet aloqasini tekshiring")
  // Muddat tugashi skan oqimida ham tutilishi shart: aks holda sekin tarmoqda
  // "Xatolik yuz berdi" ko'rsatilardi.
  if (err instanceof AxiosError && err.code === AxiosError.ECONNABORTED)
    return plain("KUTISH", "So'rov vaqti tugadi — qayta urinib ko'ring")

  const detail = errorDetail(err)
  // FastAPI (pydantic) validatsiya xatosi: [{msg, loc, ...}]. `msg` INGLIZCHA
  // ("Field required") va pydantic versiyasi bilan o'zgaradi — uni operatorga
  // ko'rsatishning ma'nosi yo'q. Massiv ham `object`, shuning uchun tuzilmali
  // konvertdan OLDIN tekshiriladi.
  if (Array.isArray(detail) && detail.length > 0)
    return plain(
      "XATO",
      "Kiritilgan ma'lumot noto'g'ri — tekshirib qayta yuboring",
    )
  // MES tuzilmali xatosi: {code: "E003", message: "..."} — skan va terminal
  // oqimlari shu konvertni qaytaradi. Busiz toast'ga "[object Object]" tushardi.
  if (typeof detail === "object" && detail) {
    const { code, message } = detail as { code?: string; message?: string }
    // Bo'sh obyekt konvert emas — zinapoya holat xabariga tushsin
    if (code || message)
      return {
        code: code ?? "XATO",
        message: message ?? "",
        structured: typeof code === "string",
      }
  }
  if (typeof detail === "string" && detail) return plain("XATO", detail)
  // Tanada `detail` yo'q (5xx, HTML sahifa, proxy xatosi)
  if (err instanceof AxiosError)
    return plain("XATO", holatXabari(err.response?.status))
  // Umuman so'rov emas — komponentdagi JS xatosi
  return plain("XATO", "Xatolik yuz berdi — qayta urinib ko'ring")
}

/** Toast va xato sahifalari uchun bir qatorlik matn — kodsiz, agar kod
 * serverdan kelmagan bo'lsa. */
export function extractErrorMessage(err: unknown): string {
  const { code, message, structured } = detailParts(err)
  if (!message) return code
  return structured ? `${code}: ${message}` : message
}

/** Skan/terminal xatosi TOAST'i: ishchi XABARni o'qiydi, kod — kichik ikkinchi
 * qatorda («Kod E008»; operator uni adminga aytadi, Loglar sahifasi izohlaydi).
 * Ilgari sarlavha «E008: …» edi — kod ishchiga hech narsa demasdi. */
export function toastScanError(err: unknown): void {
  const { code, message, structured } = detailParts(err)
  toast.error(
    message || code,
    structured ? { description: `Kod ${code}` } : undefined,
  )
}

/** Skan/terminal uchun bir qatorlik matn — kod oldinda (holat sahifasi, log). */
export function detailMessage(err: unknown): string {
  const { code, message } = detailParts(err)
  return message ? `${code}: ${message}` : code
}

/** Mutatsiya xatosi toast bilan ko'rsatiladi. Usage: `onError: handleError`. */
export const handleError = (err: unknown): void => {
  toast.error(extractErrorMessage(err))
}

/** API bazasi — klient konfiguratsiyasi (`main.tsx`) va xom URL quruvchi
 * joylar (fayl yuklab olish havolalari, WebSocket) shu yagona qiymatni oladi.
 * Ilgari `OpenAPI.BASE` edi; zamonaviy klientda bunday global yo'q. */
export const API_BASE: string =
  import.meta.env.VITE_API_URL ?? "http://localhost:8000"

export const getInitials = (name: string): string => {
  return name
    .split(" ")
    .slice(0, 2)
    .map((word) => word[0])
    .join("")
    .toUpperCase()
}
