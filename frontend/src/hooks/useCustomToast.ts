import { toast } from "sonner"

/**
 * Xabarning o'zi sarlavha bo'ladi.
 *
 * Avval sarlavha doim "Muvaffaqiyat!" / "Xatolik yuz berdi!" edi va haqiqiy
 * ma'lumot pastdagi kichik matnga tushardi — ya'ni eng katta yozuv hech narsa
 * aytmasdi. Sonner'ning ikonkasi va rangi kategoriyani o'zi bildiradi.
 */
const useCustomToast = () => {
  const showSuccessToast = (message: string) => toast.success(message)
  const showErrorToast = (message: string) => toast.error(message)

  return { showSuccessToast, showErrorToast }
}

export default useCustomToast
