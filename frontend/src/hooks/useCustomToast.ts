import { toast } from "sonner"

const useCustomToast = () => {
  const showSuccessToast = (description: string) => {
    toast.success("Muvaffaqiyat!", {
      description,
    })
  }

  const showErrorToast = (description: string) => {
    toast.error("Xatolik yuz berdi!", {
      description,
    })
  }

  return { showSuccessToast, showErrorToast }
}

export default useCustomToast
