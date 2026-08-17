import { UserRound, X } from "lucide-react"

import type { SessionRead, TerminalEmployee } from "@/client"
import { Button } from "@/components/ui/button"

/** "Kim ishlayapti?" — smenaning o'zi, login ekrani emas.
 *
 * Monoblok TERMINAL hisobi bilan bir marta, o'rnatishda kirgan va boshqa hech
 * qachon parol termaydi (tsexda klaviatura yo'q). Bu yerda esa KIM ishlayotgani
 * yoziladi — bu autentifikatsiya emas, atributsiya: qurilma allaqachon
 * tanitilgan, ekran ARRA ish markazida turibdi, ya'ni sir so'rashning ma'nosi yo'q.
 *
 * Beyjik ham shu ishni bajaradi (bitta harakat), lekin skaner faqat detal
 * skanlanadigan postda bor — ARRA da chek chiqarish skanning o'zi. */
export function ShiftGate({
  employees,
  pending,
  onStart,
}: {
  employees: TerminalEmployee[]
  pending: boolean
  onStart: (employeeId: number) => void
}) {
  return (
    <div className="absolute inset-0 z-30 flex flex-col items-center justify-center gap-6 bg-background/95 p-6 backdrop-blur-sm">
      <h2 className="text-3xl font-black">Kim ishlayapti?</h2>
      {employees.length ? (
        <div className="grid w-full max-w-3xl grid-cols-2 gap-3 sm:grid-cols-3">
          {employees.map((e) => (
            <Button
              key={e.id}
              variant="outline"
              disabled={pending}
              className="h-20 flex-col gap-0.5 text-lg font-bold"
              onClick={() => onStart(e.id)}
            >
              {e.full_name}
              {!!e.position && (
                <span className="text-2xs font-medium uppercase tracking-wider text-muted-foreground">
                  {e.position}
                </span>
              )}
            </Button>
          ))}
        </div>
      ) : (
        <p className="max-w-md text-center text-muted-foreground">
          Bu postga hodim biriktirilmagan. Admin Hodimlar bo'limida postni
          belgilashi kerak.
        </p>
      )}
      <p className="text-sm text-muted-foreground">Yoki beyjikni skanerlang</p>
    </div>
  )
}

/** Sarlavhadagi brigada. Ikki kishi bir ish markazida ishlashi mumkin va detalni
 * qaysi biri olganini bilib bo'lmaydi — shuning uchun ish ular orasida
 * bo'linadi. Ismlar doim ko'rinib turadi: ketgan odam o'chirishni unutsa,
 * qolgani begona ismni ko'radi va bosib qo'yadi — eng arzon nazorat. */
export function CrewChips({
  crew,
  onEnd,
  onAdd,
}: {
  crew: SessionRead[]
  onEnd: (session: SessionRead) => void
  onAdd: () => void
}) {
  return (
    <div className="hidden shrink-0 items-center gap-1.5 md:flex">
      <UserRound className="size-4 text-muted-foreground" />
      {crew.map((s) => (
        <button
          key={s.id}
          type="button"
          onClick={() => onEnd(s)}
          className="flex items-center gap-1.5 rounded-full border bg-card py-1.5 pl-3 pr-2 text-sm hover:border-destructive/50"
        >
          <span className="size-2 rounded-full bg-green-500" />
          <b className="max-w-32 truncate">{s.employee_name}</b>
          <X className="size-3.5 text-muted-foreground" />
        </button>
      ))}
      <Button
        variant="ghost"
        size="sm"
        className="rounded-full text-muted-foreground"
        onClick={onAdd}
      >
        + Qo'shish
      </Button>
    </div>
  )
}
