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
  onCancel,
}: {
  employees: TerminalEmployee[]
  pending: boolean
  onStart: (employeeId: number) => void
  /** "+ Qo'shish" bilan ochilganda - orqaga yo'l. Qurilma hisobida ekran
   *  smenasiz ishlay olmaydi, o'shanda bekor qilish berilmaydi. */
  onCancel?: () => void
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
      {onCancel && (
        <Button
          variant="ghost"
          className="h-14 px-8 text-lg font-bold"
          onClick={onCancel}
        >
          Bekor qilish
        </Button>
      )}
    </div>
  )
}

/** Sarlavhadagi brigada - faqat QO'SHILGAN sheriklar.
 *
 * Ikki kishi bir ish markazida ishlashi mumkin; skan smenani ochgan odamga
 * yoziladi (brigada bo'linishi yo'q — hisobot smena vaqtiga qaramaydi).
 *
 * Kirgan odamning O'ZI ro'yxatda ko'rinmaydi (`is_me`): u kimligini login
 * allaqachon aytgan va o'z ismini ko'rish unga hech narsa qo'shmaydi. Sherik
 * ismi esa ko'rinishi shart - ketgan odam o'chirishni unutsa, qolgani begona
 * ismni ko'radi va bosib qo'yadi, bu eng arzon nazorat.
 *
 * Qurilma hisobida (TERMINAL) hech kim `is_me` bo'lmaydi, ya'ni u yerda hamma
 * ism ko'rinadi - monoblokda kim ishlayotganini faqat shu ro'yxat aytadi. */
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
      {crew
        .filter((s) => !s.is_me)
        .map((s) => (
          <button
            key={s.id}
            type="button"
            onClick={() => onEnd(s)}
            className="flex h-10 items-center gap-1.5 rounded-full border bg-card pl-3 pr-2 text-sm hover:border-destructive/50"
          >
            <span className="size-2 rounded-full bg-green-500" />
            <b className="max-w-32 truncate">{s.employee_name}</b>
            <X className="size-3.5 text-muted-foreground" />
          </button>
        ))}
      <Button
        variant="ghost"
        className="h-10 rounded-full text-muted-foreground"
        onClick={onAdd}
      >
        + Qo'shish
      </Button>
    </div>
  )
}
