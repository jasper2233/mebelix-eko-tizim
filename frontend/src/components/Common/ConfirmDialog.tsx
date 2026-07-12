import type { ReactNode } from "react"

import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { LoadingButton } from "@/components/ui/loading-button"

interface ConfirmDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  title: ReactNode
  description?: ReactNode
  confirmText?: string
  cancelText?: string
  destructive?: boolean
  loading?: boolean
  onConfirm: () => void
}

/**
 * Generic "Are you sure?" dialog. Caller owns the trigger and the open state so the trigger
 * can be a button, a menu item, or anything else; the dialog only renders the modal body.
 */
export const ConfirmDialog = ({
  open,
  onOpenChange,
  title,
  description,
  confirmText = "Tasdiqlash",
  cancelText = "Bekor qilish",
  destructive = false,
  loading = false,
  onConfirm,
}: ConfirmDialogProps) => (
  <Dialog open={open} onOpenChange={onOpenChange}>
    <DialogContent className="sm:max-w-md">
      <DialogHeader>
        <DialogTitle>{title}</DialogTitle>
        {description ? (
          <DialogDescription>{description}</DialogDescription>
        ) : null}
      </DialogHeader>
      {/* h-11 = 44px: terminal (touch) va admin uchun bir xil minimal barmoq o'lchami */}
      <DialogFooter className="mt-4 gap-3">
        <DialogClose asChild>
          <Button variant="outline" className="h-11 px-5" disabled={loading}>
            {cancelText}
          </Button>
        </DialogClose>
        <LoadingButton
          variant={destructive ? "destructive" : "default"}
          className="h-11 px-5"
          loading={loading}
          onClick={onConfirm}
        >
          {confirmText}
        </LoadingButton>
      </DialogFooter>
    </DialogContent>
  </Dialog>
)
