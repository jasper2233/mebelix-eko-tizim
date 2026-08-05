// Yorliq chop etish mutatsiyasi — ARRA xaritasi (CutmapView) va ROVER/PRISADKA
// sahifasi (PrisadkaView) baham ko'radi: bir xil mutationFn + toast + xato.
// scope — qaysi terminal so'rovi yangilanadi (["terminal", scope] kesh kaliti).

import { useMutation, useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"

import { TerminalService } from "@/client"
import { handleError } from "@/utils"

export function usePrintLabel(scope: "cutmap" | "prisadka") {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (instanceId: number) =>
      TerminalService.printInstanceLabel({ instanceId }),
    onSuccess: (r) => toast.success(r.message),
    onError: handleError,
    onSettled: () =>
      queryClient.invalidateQueries({ queryKey: ["terminal", scope] }),
  })
}
