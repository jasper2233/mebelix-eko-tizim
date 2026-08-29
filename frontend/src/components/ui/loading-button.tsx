import type { VariantProps } from "class-variance-authority"
import { Loader2 } from "lucide-react"
import { cn } from "@/lib/utils"
// button.tsx bilan BITTA manba — copy-paste nusxa allaqachon divergensiya bergan edi
import { buttonVariants } from "./button"

interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
  VariantProps<typeof buttonVariants> {
  loading?: boolean
}

function LoadingButton({
  className,
  loading = false,
  children,
  disabled,
  variant,
  size,
  ...props
}: ButtonProps) {
  return (
    <button
      className={cn(buttonVariants({ variant, size, className }))}
      disabled={loading || disabled}
      {...props}
    >
      {/* Oraliqni buttonVariants dagi `gap-2` beradi — spinner o'z marjinini
          qo'shsa, ikonkali oddiy Button bilan bir xil bo'lmay qolardi. */}
      {loading && <Loader2 className="h-5 w-5 animate-spin" />}
      {children}
    </button>
  )
}

export { LoadingButton }

