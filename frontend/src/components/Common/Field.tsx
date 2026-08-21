import type { ReactNode } from "react"

/**
 * Dialog maydoni yorlig'i — react-hook-form ishlatmaydigan formalar uchun.
 *
 * `ui/form.tsx` dagi `FormField`/`FormLabel` rhf konteksti talab qiladi;
 * qo'lda `useState` bilan yozilgan dialoglarda (ish markazi, hodim)
 * shu komponent o'sha rolni bajaradi. Ilgari u uchta faylda bayt-ba-bayt
 * takrorlanardi.
 *
 * Maydon `<label>` ICHIDA turadi (implicit bog'lanish) — yorliqni bosish
 * fokusni maydonga beradi. Ilgari yorliq `<span>` edi, ya'ni bosish hech
 * narsa qilmasdi.
 */
export function Field({
  label,
  children,
}: {
  label: string
  children: ReactNode
}) {
  return (
    // biome-ignore lint/a11y/noLabelWithoutControl: maydon children orqali keladi
    <label className="grid gap-1.5">
      <span className="text-2xs font-medium uppercase tracking-wider text-muted-foreground">
        {label}
      </span>
      {children}
    </label>
  )
}
