// Anketa formasining o'z UI tili — qog'oz so'rovnomaning aksi: raqam katagi,
// belgilash to'ri, shakl tanlash. Bu primitivlar FAQAT anketada ishlatiladi
// (`Common/` ga chiqarilmagan): ular loyihaning umumiy forma uslubi emas,
// balki bitta hujjatning tashqi ko'rinishini takrorlaydi.

import { useState } from "react"
import { cardSurface } from "@/components/ui/card"
import { Checkbox } from "@/components/ui/checkbox"
import { Input } from "@/components/ui/input"
import { LAYOUT_SHAPES, type Option } from "@/lib/anketa"
import { cn } from "@/lib/utils"

/** Bo'sh qiymatlar tashlab yuboriladi — texnolog faqat kiritilganini ko'radi */
export function Facts({ items }: { items: [string, string][] }) {
  const filled = items.filter(([, v]) => v.trim())
  if (!filled.length)
    return <p className="text-muted-foreground text-sm">To'ldirilmagan.</p>
  return (
    <dl className="grid gap-x-6 gap-y-2 sm:grid-cols-[minmax(0,180px)_1fr]">
      {filled.map(([k, v]) => (
        <div key={k} className="contents">
          <dt className="text-muted-foreground text-sm">{k}</dt>
          <dd className="font-medium text-sm">{v}</dd>
        </div>
      ))}
    </dl>
  )
}

function numOrNull(v: string): number | null {
  // O'zbek/rus klaviaturasida o'nlik ajratgich vergul — "3,5" ni ham qabul qilamiz
  const n = Number(v.replace(",", "."))
  return v.trim() === "" || Number.isNaN(n) ? null : n
}

/** Raqamli maydon: yozilayotgan xom matn saqlanadi, aks holda "3," yozilganda
 *  qiymat null bo'lib maydon o'z-o'zidan tozalanadi. Blur'da normallashadi. */
export function NumInput({
  value,
  disabled,
  onChange,
  integer = false,
  "aria-label": ariaLabel,
}: {
  value: number | null | undefined
  disabled?: boolean
  onChange: (v: number | null) => void
  integer?: boolean
  /** O'lchov varag'idagi maydonlarda ko'rinadigan `<label>` yo'q (jadval
   *  kataklari), shuning uchun nom shu yerdan beriladi. */
  "aria-label"?: string
}) {
  const [raw, setRaw] = useState<string | null>(null)
  return (
    <Input
      inputMode={integer ? "numeric" : "decimal"}
      aria-label={ariaLabel}
      // raqamlar bir xil kenglikda va o'ngga tekis — ustunni ko'z bilan qo'shish mumkin
      className="num text-right"
      disabled={disabled}
      value={raw ?? value ?? ""}
      onChange={(e) => {
        setRaw(e.target.value)
        const n = numOrNull(e.target.value)
        onChange(n != null && integer ? Math.trunc(n) : n)
      }}
      onBlur={() => setRaw(null)}
    />
  )
}

export function Section({
  n,
  title,
  hint,
  children,
}: {
  /** Bo'lim raqami — qog'oz anketadagidek. Menejer mijozga "3-bo'limga o'tamiz"
   *  deb aytadi va telefonda qog'oz nusxa bilan gaplasha oladi. */
  n?: number
  title: string
  hint?: string
  children: React.ReactNode
}) {
  return (
    <section className={cn(cardSurface, "p-4")}>
      <h3 className="mb-3 text-base font-semibold">
        {n && <span className="mr-2 text-muted-foreground">{n}</span>}
        {title}
        {hint && (
          <span className="ml-2 font-normal text-muted-foreground text-sm">
            ({hint})
          </span>
        )}
      </h3>
      {/* Bo'shliq bitta joydan: bolalar orasida space-y, grid ichida esa gap */}
      <div className="space-y-3">{children}</div>
    </section>
  )
}

export function Field({
  label,
  children,
}: {
  label: string
  children: React.ReactNode
}) {
  return (
    // Margin YO'Q: grid ichida `first:mt-0` faqat birinchi katakka tegib, qolganini
    // pastga surar edi (input va tugmalar bir qatorda turmasdi). Bo'shliqni ota beradi.
    // biome-ignore lint/a11y/noLabelWithoutControl: input children orqali keladi — bosilganda fokus oladi
    <label className="block">
      <span className="mb-1 block min-h-5 leading-5 text-muted-foreground text-sm font-medium">
        {label}
      </span>
      {children}
    </label>
  )
}

export function Num({
  label,
  value,
  disabled,
  onChange,
}: {
  label: string
  value: number | null | undefined
  disabled?: boolean
  onChange: (v: number | null) => void
}) {
  return (
    <Field label={label}>
      <NumInput value={value} disabled={disabled} onChange={onChange} />
    </Field>
  )
}

/** Bitta belgilash katagi — sensorli ekranda butun katak bosiladi.
 *  Tanlangan holat grammatikasi FAQAT shu yerda: anketadagi har bir katakcha
 *  (to'rdagisi ham, buyurtma darajasidagisi ham) shu ko'rinishni oladi. */
export function CheckCard({
  checked,
  disabled,
  onToggle,
  children,
}: {
  checked: boolean
  disabled?: boolean
  onToggle: () => void
  children: React.ReactNode
}) {
  return (
    // biome-ignore lint/a11y/noLabelWithoutControl: Checkbox (Radix) ichida — butun katak bosiladi
    <label
      className={cn(
        "flex cursor-pointer items-center gap-2 rounded-lg border px-3 py-2 text-sm transition-colors",
        checked ? "border-primary bg-primary/5" : "hover:border-primary/40",
        disabled && "cursor-default opacity-70",
      )}
    >
      <Checkbox
        checked={checked}
        disabled={disabled}
        onCheckedChange={onToggle}
      />
      {children}
    </label>
  )
}

/** Ko'p tanlovli katakchalar to'ri */
export function CheckGrid({
  options,
  values,
  disabled,
  onChange,
}: {
  options: Option[]
  values: string[]
  disabled?: boolean
  onChange: (v: string[]) => void
}) {
  return (
    <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
      {options.map((o) => {
        const checked = values.includes(o.value)
        return (
          <CheckCard
            key={o.value}
            checked={checked}
            disabled={disabled}
            onToggle={() =>
              onChange(
                checked
                  ? values.filter((v) => v !== o.value)
                  : [...values, o.value],
              )
            }
          >
            {o.label}
          </CheckCard>
        )
      })}
    </div>
  )
}

/** Planirovka silueti — qog'oz anketadagi chizmalar (uploads/forma/...html:90-103).
 *  Bu sahifadagi yagona savol javobi matn emas, SHAKL: mijoz siluetni tanidi-yu,
 *  "П-shakl (U)" jargonini o'qimaydi. Xato bu yerda eng qimmat — texnolog
 *  butun planirovkani shunga qarab yasaydi. */
export function ShapeChoice({
  value,
  disabled,
  onChange,
}: {
  value: string | null
  disabled?: boolean
  onChange: (v: string | null) => void
}) {
  return (
    <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
      {LAYOUT_SHAPES.map((o) => {
        const on = value === o.value
        return (
          <button
            key={o.value}
            type="button"
            disabled={disabled}
            aria-pressed={on}
            onClick={() => onChange(on ? null : o.value)}
            // Tanlangan holat Choice bilan AYNAN bir xil token — sahifada bitta grammatika
            className={`flex flex-col items-center gap-2 rounded-md border p-3 text-sm shadow-xs transition-colors focus-visible:outline-2 focus-visible:outline-ring focus-visible:outline-offset-2 ${
              on
                ? "border-primary bg-primary text-primary-foreground"
                : "text-muted-foreground hover:border-primary/40 hover:text-foreground"
            } ${disabled ? "opacity-70" : ""}`}
          >
            <svg
              viewBox="0 0 52 34"
              aria-hidden="true"
              className="h-auto w-full max-w-24"
              fill="currentColor"
            >
              <title>{o.label}</title>
              {SHAPE_ART[o.value]}
            </svg>
            <span className="font-medium">{o.label}</span>
          </button>
        )
      })}
    </div>
  )
}

/** Siluetlar: mebel tepadan ko'rilgan holatda, xona devorlari bo'ylab */
const SHAPE_ART: Record<string, React.ReactNode> = {
  togri: <rect x="4" y="6" width="44" height="8" rx="2" />,
  burchak: (
    <>
      <rect x="4" y="6" width="34" height="8" rx="2" />
      <rect x="4" y="14" width="8" height="16" rx="2" />
    </>
  ),
  p_shakl: (
    <>
      <rect x="4" y="6" width="44" height="8" rx="2" />
      <rect x="4" y="14" width="8" height="16" rx="2" />
      <rect x="40" y="14" width="8" height="16" rx="2" />
    </>
  ),
  orolchali: (
    <>
      <rect x="4" y="5" width="44" height="6" rx="2" />
      <rect x="16" y="20" width="20" height="9" rx="2" />
    </>
  ),
}

/** Bitta tanlov — qayta bosilsa bekor qilinadi (radio'da bu imkonsiz) */
export function Choice({
  options,
  value,
  disabled,
  onChange,
}: {
  options: Option[]
  value: string | null
  disabled?: boolean
  onChange: (v: string | null) => void
}) {
  return (
    <div className="flex min-h-9 flex-wrap items-center gap-2">
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          disabled={disabled}
          aria-pressed={value === o.value}
          onClick={() => onChange(value === o.value ? null : o.value)}
          // h-9 — Input bilan bir xil balandlik, yonma-yon turganda qator buzilmaydi
          className={`inline-flex h-9 items-center rounded-md border px-3 text-sm shadow-xs transition-colors focus-visible:outline-2 focus-visible:outline-ring focus-visible:outline-offset-2 ${
            value === o.value
              ? "border-primary bg-primary text-primary-foreground"
              : "hover:border-primary/40"
          } ${disabled ? "opacity-70" : ""}`}
        >
          {o.label}
        </button>
      ))}
    </div>
  )
}
