import { AxiosError } from "axios"
import type { ApiError } from "./client"

function extractErrorMessage(err: ApiError): string {
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
  if (Array.isArray(errDetail) && errDetail.length > 0) {
    return errDetail[0].msg
  }
  return errDetail || "Xatolik yuz berdi. Qayta urinib ko'ring."
}

type ToastFn = (message: string) => void

/**
 * Build a TanStack Query `onError` handler that pipes the API error message into the given toast function.
 *
 * Usage: `onError: handleError(showErrorToast)`.
 */
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
