// Stanok sozlamalari oynasi — Ish markazlari jadvalida stanok nomi bosilganda ochiladi.
// Tsexda odam sozlamani STANOKDAN izlaydi («kromkaning dopuski qayerda?»), sozlamalar
// sahifasining tablaridan emas. Kartalar `Settings/MachineCards` dan — bitta kod, ikki joy.
//
// Qiymatlar GLOBAL (`system_setting`): o'zgartirish o'sha TURDAGI hamma stanokka tegadi.
// Shuning uchun oynada shu haqda qator turadi va karta sarlavhalari o'zgarmaydi.

import { useQuery } from "@tanstack/react-query"
import { Link } from "@tanstack/react-router"

import { type PostCode, SettingsService } from "@/client"
import { QueryError } from "@/components/Common/QueryError"
import {
  IdealCycleCard,
  KromkaBindCard,
  KromkaCycleCard,
  KromkaIdleCard,
  KromkaKalCard,
  RoverCycleCard,
} from "@/components/Settings/MachineCards"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Skeleton } from "@/components/ui/skeleton"

/** Qaysi postda sozlanadigan narsa bor. Boshqa postlarda stanokka bog'liq sozlama yo'q —
 *  ish jadvali, to'xtash sabablari va brak sabablari hammaga umumiy. */
const SOZLAMALI: PostCode[] = ["KROMKA", "PRISADKA", "ROVER"]

export const hasMachineSettings = (code?: PostCode) =>
  !!code && SOZLAMALI.includes(code)

export function MachineSettingsDialog({
  machineId,
  machineName,
  postCode,
  open,
  onOpenChange,
}: {
  machineId: number
  machineName: string
  postCode?: PostCode
  open: boolean
  onOpenChange: (v: boolean) => void
}) {
  // Kalit/qiymat sozlamalari — kartalar ro'yxatdan o'z kalitini oladi
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["system-settings"],
    queryFn: async () => (await SettingsService.readSystemSettings()).data,
    enabled: open,
  })

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-3xl">
        <DialogHeader>
          <DialogTitle>{machineName} — sozlamalar</DialogTitle>
          <DialogDescription>
            Bu qiymatlar {postCode} turidagi HAMMA stanokka tegishli: bittasini
            o'zgartirsang, qolganlari ham shu bo'yicha ishlaydi. O'zgarish
            saqlangan zahoti kuchga kiradi.
          </DialogDescription>
        </DialogHeader>

        {isLoading ? (
          <Skeleton className="h-64 w-full" />
        ) : isError || !data ? (
          <QueryError onRetry={() => refetch()} />
        ) : (
          <div className="space-y-4 [&_p]:max-w-prose">
            {postCode === "KROMKA" && (
              <>
                <KromkaBindCard settings={data} />
                <KromkaIdleCard settings={data} />
                <KromkaCycleCard />
                <KromkaKalCard machineId={machineId} />
                <p className="text-sm text-muted-foreground">
                  Kalibrlash sessiyasi (etalon o'tkazib Pico'ga yangi qiymat
                  yozish) alohida sahifada:{" "}
                  <Link
                    to="/system-settings"
                    search={{ tab: "kalib" }}
                    className="underline underline-offset-4"
                  >
                    Tizim sozlamalari → Kalibrlash
                  </Link>
                  .
                </p>
              </>
            )}
            {postCode === "PRISADKA" && <IdealCycleCard />}
            {postCode === "ROVER" && <RoverCycleCard />}
          </div>
        )}
      </DialogContent>
    </Dialog>
  )
}
