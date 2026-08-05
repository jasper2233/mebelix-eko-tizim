import { AxiosError } from "axios"
import { toast } from "sonner"
import type { ApiError } from "./client"

export function extractErrorMessage(err: ApiError): string {
  if (err instanceof AxiosError) {
    if (err.code === AxiosError.ERR_NETWORK) {
      return "Tarmoq xatosi — internet aloqasini tekshiring"
    }
    if (err.code === AxiosError.ECONNABORTED) {
      return "So'rov vaqti tugadi — qayta urinib ko'ring"
    }
    return err.message
  }

  const errDetail = (err.body as any)?.detail
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
  return typeof errDetail === "string" && errDetail
    ? errDetail
    : "Xatolik yuz berdi. Qayta urinib ko'ring."
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

export function detailMessage(err: unknown): string {
  const { code, message } = detailParts(err)
  return message ? `${code}: ${message}` : code
}

/** Mutatsiya xatosi toast bilan ko'rsatiladi. Usage: `onError: handleError`. */
export const handleError = (err: ApiError): void => {
  toast.error(extractErrorMessage(err))
}

export const getInitials = (name: string): string => {
  return name
    .split(" ")
    .slice(0, 2)
    .map((word) => word[0])
    .join("")
    .toUpperCase()
}
