// Chek amallari — chiqarish va bekor qilish. ARRA xaritasi (CutmapView) va
// ROVER/PRISADKA sahifasi (PrisadkaView) baham ko'radi: bir xil mutationFn +
// toast + xato. scope — qaysi terminal so'rovi yangilanadi (["terminal", scope]).

import { useMutation, useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"

import { TerminalService } from "@/client"
import { handleError } from "@/utils"

export function usePrintLabel(scope: "cutmap" | "prisadka") {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (instanceId: number) =>
      (
        await TerminalService.printInstanceLabel({
          path: { instance_id: instanceId },
        })
      ).data,
    onSuccess: (r) => toast.success(r.message),
    onError: handleError,
    onSettled: () =>
      queryClient.invalidateQueries({ queryKey: ["terminal", scope] }),
  })
}

/** Noto'g'ri chiqarilgan chekni bekor qilish: `label_printed_at` tozalanadi va
 *  chop etish YOZGAN avto-skan ham qaytariladi (kesish postlarida chek = skan).
 *  Ikkala kesh ham yangilanadi — bir xil nusxa xaritada ham, detallar
 *  ro'yxatida ham ko'rinishi mumkin. */
export function useCancelLabel() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (instanceId: number) =>
      (
        await TerminalService.cancelInstanceLabel({
          path: { instance_id: instanceId },
        })
      ).data,
    onSuccess: (r) => toast.success(r.message),
    onError: handleError,
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["terminal", "cutmap"] })
      queryClient.invalidateQueries({ queryKey: ["terminal", "prisadka"] })
      queryClient.invalidateQueries({ queryKey: ["admin", "cutmap"] })
    },
  })
}
