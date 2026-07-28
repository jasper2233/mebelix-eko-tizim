import { AxiosError } from "axios"
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

type ToastFn = (message: string) => void

/** Usage: `onError: handleError(showErrorToast)`. */
export const handleError =
  (showToast: ToastFn) =>
  (err: ApiError): void => {
    showToast(extractErrorMessage(err))
  }

export const getInitials = (name: string): string => {
  return name
    .split(" ")
    .slice(0, 2)
    .map((word) => word[0])
    .join("")
    .toUpperCase()
}
