// Ombor va rezerv qoidalari (EKO TZ §4.3, Q13; EKO 2.4): backend `settings_service` kalitlari va
// `INT_RANGES` bilan qo'lda oynalangan — birini o'zgartirsang ikkinchisini ham.

import { useMutation, useQueryClient } from "@tanstack/react-query"
import { useEffect, useState } from "react"

import { SettingsService, type SystemSettingRead } from "@/client"
import { Field } from "@/components/Common/Field"
import { cardSurface } from "@/components/ui/card"
import { Checkbox } from "@/components/ui/checkbox"
import { Input } from "@/components/ui/input"
import { LoadingButton } from "@/components/ui/loading-button"
import { cn } from "@/lib/utils"
import { crudCallbacks } from "@/queries/mes"

const MUDDAT = "rezerv_muddat_kun"
const FOIZ = "eng_kam_avans_foiz"
const DARVOZA = "rezerv_darvoza"
const IKKI_KALIT = "ombor_ikki_kalit"
const KEYS = [MUDDAT, FOIZ, DARVOZA, IKKI_KALIT] as const
type Key = (typeof KEYS)[number]

export function OmborQoidalarCard({
  settings,
}: {
  settings: SystemSettingRead[]
}) {
  const queryClient = useQueryClient()
  const saved = Object.fromEntries(
    KEYS.map((k) => [k, settings.find((s) => s.key === k)?.value ?? ""]),
  ) as Record<Key, string>
  const [v, setV] = useState(saved)
  const savedJson = JSON.stringify(saved)
  useEffect(() => setV(JSON.parse(savedJson)), [savedJson])

  const mutation = useMutation({
    mutationFn: async () => {
      for (const k of KEYS)
        if (v[k] !== saved[k])
          await SettingsService.updateSystemSetting({
            path: { key: k },
            body: { value: v[k] },
          })
    },
    ...crudCallbacks(queryClient, ["system-settings"], "Sozlama saqlandi"),
  })
  const intOk = (s: string, lo: number, hi: number) =>
    /^\d+$/.test(s) && Number(s) >= lo && Number(s) <= hi
  const valid = intOk(v[MUDDAT], 1, 60) && intOk(v[FOIZ], 0, 100)
  const changed = KEYS.some((k) => v[k] !== saved[k])
  const flag = (k: Key, label: string, hint: string) => (
    <label htmlFor={k} className="flex items-start gap-3 text-sm">
      <Checkbox
        id={k}
        className="mt-0.5"
        checked={v[k] === "1"}
        onCheckedChange={(c) => setV({ ...v, [k]: c === true ? "1" : "0" })}
      />
      <span>
        <b>{label}</b>
        <span className="block text-muted-foreground">{hint}</span>
      </span>
    </label>
  )

  return (
    <div className={cn(cardSurface, "space-y-4 p-4")}>
      <div>
        <h2 className="text-lg font-semibold">Ombor va rezerv qoidalari</h2>
        <p className="text-sm text-muted-foreground">
          Kroy yuklanganda material buyurtmaga band qilinadi. Shu muddat ichida
          avans shu foizga yetsa — material buyurtmaniki, yetmasa — yana sotuvga
          ochiladi.
        </p>
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Rezerv muddati, kun (1–60)">
          <Input
            type="number"
            inputMode="numeric"
            value={v[MUDDAT]}
            aria-invalid={!intOk(v[MUDDAT], 1, 60)}
            onChange={(e) => setV({ ...v, [MUDDAT]: e.target.value })}
          />
        </Field>
        <Field label="Eng kam avans, % (0–100)">
          <Input
            type="number"
            inputMode="numeric"
            value={v[FOIZ]}
            aria-invalid={!intOk(v[FOIZ], 0, 100)}
            onChange={(e) => setV({ ...v, [FOIZ]: e.target.value })}
          />
        </Field>
      </div>
      {flag(
        DARVOZA,
        "Ishlab chiqarish darvozasi",
        "To'lov chegarasi bajarilmagan buyurtma ishlab chiqarishga o'tmaydi (doimiy mijozning kredit limiti yoki direktor ruxsati bundan mustasno).",
      )}
      {flag(
        IKKI_KALIT,
        "Ikki kalit qoidasi",
        "Ombor hujjatini yozgan xodim uni o'zi tasdiqlay olmaydi — qoralamani boshqa xodim tasdiqlaydi.",
      )}
      <LoadingButton
        loading={mutation.isPending}
        disabled={!valid || !changed}
        onClick={() => mutation.mutate()}
      >
        Saqlash
      </LoadingButton>
    </div>
  )
}
