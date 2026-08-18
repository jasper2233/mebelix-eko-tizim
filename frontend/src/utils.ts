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
  // FastAPI validatsiya xatosi: [{msg, loc, ...}]
  if (Array.isArray(errDetail) && errDetail.length > 0) {
    return errDetail[0].msg
  }
  // MES tuzilmali xatosi: {code: "E003", message: "..."} — skan va terminal
  // oqimlari shu konvertni qaytaradi. Busiz toast'ga "[object Object]" tushardi.
  if (errDetail && typeof errDetail === "object") {
    const { code, message } = errDetail as { code?: string; message?: string }
    if (message) return code ? `${code}: ${message}` : message
    if (code) return code
  }
  if (typeof errDetail === "string" && errDetail) return errDetail
  // Tanada `detail` yo'q (5xx, HTML sahifa, proxy xatosi) — axios matni qoladi.
  if (err instanceof AxiosError) return err.message
  return "Xatolik yuz berdi. Qayta urinib ko'ring."
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
  const detail = errorDetail(err)
  // FastAPI validatsiya xatosi: [{msg, loc, ...}] — massiv ham `object`, shuning
  // uchun u tuzilmali konvertdan OLDIN tekshiriladi.
  if (Array.isArray(detail) && detail.length > 0)
    return { code: "XATO", message: String(detail[0]?.msg ?? "") }
  if (typeof detail === "object" && detail) {
    const { code, message } = detail as { code?: string; message?: string }
    return { code: code ?? "XATO", message: message ?? "" }
  }
  return {
    code: "XATO",
    message: typeof detail === "string" ? detail : "Xatolik yuz berdi",
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
