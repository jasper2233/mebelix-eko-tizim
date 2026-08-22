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

export function extractErrorMessage(err: unknown): string {
  if (err instanceof AxiosError) {
    if (err.code === AxiosError.ERR_NETWORK) {
      return "Tarmoq xatosi — internet aloqasini tekshiring"
    }
    if (err.code === AxiosError.ECONNABORTED) {
      return "So'rov vaqti tugadi — qayta urinib ko'ring"
    }
  }

  const errDetail = errorDetail(err)
  // FastAPI (pydantic) validatsiya xatosi: [{msg, loc, ...}]. `msg` INGLIZCHA
  // ("Field required", "String should have at least 3 characters") va pydantic
  // versiyasi bilan o'zgaradi — uni operatorga ko'rsatishning ma'nosi yo'q.
  // Adminda ham zarari kam: gap qaysi maydonda ekani formada ko'rinib turadi.
  if (Array.isArray(errDetail) && errDetail.length > 0) {
    return "Kiritilgan ma'lumot noto'g'ri — tekshirib qayta yuboring"
  }
  // MES tuzilmali xatosi: {code: "E003", message: "..."} — skan va terminal
  // oqimlari shu konvertni qaytaradi. Busiz toast'ga "[object Object]" tushardi.
  if (errDetail && typeof errDetail === "object") {
    const { code, message } = errDetail as { code?: string; message?: string }
    if (message) return code ? `${code}: ${message}` : message
    if (code) return code
  }
  if (typeof errDetail === "string" && errDetail) return errDetail
  // Tanada `detail` yo'q (5xx, HTML sahifa, proxy xatosi)
  if (err instanceof AxiosError) return holatXabari(err.response?.status)
  return "Xatolik yuz berdi — qayta urinib ko'ring"
}

/** MES tuzilmali xato konverti {code, message} ni ajratadi (skan/terminal oqimi).
 * extractErrorMessage'dan farqi: code ALOHIDA kerak bo'lganda (E001 ga qarab ovoz). */
export function detailParts(err: unknown): { code: string; message: string } {
  if (err instanceof AxiosError && err.code === AxiosError.ERR_NETWORK) {
    return {
      code: "TARMOQ",
      message: "Tarmoq xatosi — internet aloqasini tekshiring",
    }
  }
  // Muddat tugashi ilgari FAQAT `extractErrorMessage` da tutilardi: skan oqimi
  // shu funksiyadan o'tadi va sekin tarmoqda "Xatolik yuz berdi" ko'rsatardi.
  if (err instanceof AxiosError && err.code === AxiosError.ECONNABORTED) {
    return { code: "KUTISH", message: "Server javob bermadi — qayta urining" }
  }
  const detail = errorDetail(err)
  // FastAPI validatsiya xatosi: [{msg, loc, ...}] — massiv ham `object`, shuning
  // uchun u tuzilmali konvertdan OLDIN tekshiriladi.
  if (Array.isArray(detail) && detail.length > 0)
    return {
      code: "XATO",
      message: "Kiritilgan ma'lumot noto'g'ri — tekshirib qayta yuboring",
    }
  if (typeof detail === "object" && detail) {
    const { code, message } = detail as { code?: string; message?: string }
    return { code: code ?? "XATO", message: message ?? "" }
  }
  if (typeof detail === "string" && detail)
    return { code: "XATO", message: detail }
  return {
    code: "XATO",
    message: holatXabari(
      err instanceof AxiosError ? err.response?.status : undefined,
    ),
  }
}

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
