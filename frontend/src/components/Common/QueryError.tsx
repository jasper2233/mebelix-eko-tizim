import { AlertTriangle } from "lucide-react"

import { Button } from "@/components/ui/button"

/**
 * So'rov yiqilganda ko'rsatiladigan blok.
 *
 * Busiz sahifalar faqat `isLoading` ni tekshirardi va xato holatida `data`
 * undefined qolib, ekran abadiy skeletonda qotib turardi — foydalanuvchi nima
 * bo'lganini bilmasdi va qayta urinish yo'li ham yo'q edi.
 */
export function QueryError({
  message = "Ma'lumotni olishda xatolik yuz berdi.",
  onRetry,
}: {
  message?: string
  onRetry?: () => void
}) {
  return (
    <div
      role="alert"
      className="flex flex-col items-center gap-3 rounded-lg border border-destructive/30 bg-destructive/5 p-8 text-center"
    >
      <AlertTriangle className="size-8 text-destructive" />
      <p className="font-medium text-destructive">{message}</p>
      {onRetry && (
        <Button variant="outline" onClick={onRetry}>
          Qayta urinish
        </Button>
      )}
    </div>
  )
}
