// Tizim sozlamalari: ish vaqtida admin o'zgartiradigan qiymatlar — nostandart
// detal belgisi, harakatsizlikdan keyin chiqish chegarasi, to'xtash sabablari, ideal sikl
// (OEE Performance) va ish jadvali (smenalar,
// tanaffuslar, dam olish kunlari; OEE reja vaqti shundan hisoblanadi).

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { ArrowRightLeft, Plus, Trash2 } from "lucide-react"
import { type ReactNode, useEffect, useState } from "react"

import {
  type DowntimeReasonRead,
  type DowntimeReasonUpdate,
  type Holiday,
  type IdealCycle,
  SettingsService,
  type SystemSettingRead,
  type WorkBreak,
  type WorkSchedule,
  type WorkShift,
} from "@/client"
import { Field } from "@/components/Common/Field"
import { PageHeader } from "@/components/Common/PageHeader"
import { QueryError } from "@/components/Common/QueryError"
import { RowAction } from "@/components/Common/RowAction"
import { Button } from "@/components/ui/button"
import { cardSurface } from "@/components/ui/card"
import { Checkbox } from "@/components/ui/checkbox"
import { DatePicker } from "@/components/ui/date-picker"
import { Input } from "@/components/ui/input"
import { LoadingButton } from "@/components/ui/loading-button"
import { Skeleton } from "@/components/ui/skeleton"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { requireAccess } from "@/lib/guards"
import { formatDate, isAdmin } from "@/lib/mes"
import { cn } from "@/lib/utils"
import { crudCallbacks } from "@/queries/mes"

// Sozlamalar MAVZU bo'yicha tablarga bo'lingan (ilgari beshta karta bitta uzun ustunda, har xil kenglikda
// turardi). Tab URL'da (`?tab=`): sahifa yangilansa joyida qoladi va boshqa sahifadan aniq tabga havola
// berish mumkin (Hisobotlar → «Stanok vaqti» dagi izohlar).
const SETTINGS_TABS = [
  { value: "general", label: "Umumiy" },
  { value: "schedule", label: "Ish jadvali" },
  { value: "downtime", label: "To'xtash sabablari" },
  { value: "ideal", label: "Ideal sikl" },
  { value: "defect", label: "Brak sabablari" },
] as const
type SettingsTab = (typeof SETTINGS_TABS)[number]["value"]
const TAB_PANEL = "data-[state=inactive]:hidden"

export const Route = createFileRoute("/_layout/system-settings")({
  component: SystemSettingsPage,
  // Kalit DOIM qaytadi (noto'g'ri qiymatda `undefined`): router ota marshrutning XOM search'ini
  // natijaga qo'shadi, ya'ni `{}` qaytarilsa `?tab=xato` o'tib ketib, hech bir tab faol bo'lmay qolardi.
  validateSearch: (s: Record<string, unknown>): { tab?: SettingsTab } => ({
    tab: SETTINGS_TABS.some((t) => t.value === s.tab)
      ? (s.tab as SettingsTab)
      : undefined,
  }),
  // `lib/mes` dagi `isAdmin` izohi shu sahifani nomma-nom sanab o'tadi
  beforeLoad: requireAccess(isAdmin),
  head: () => ({ meta: [{ title: "Tizim sozlamalari | MebeliX" }] }),
})

const SUFFIX_KEY = "custom_part_suffix"
// Backend `settings_service.IDLE_*` va `INT_RANGES` bilan bir xil
const IDLE_OPERATOR_KEY = "idle_logout_operator_minutes"
const IDLE_STAFF_KEY = "idle_logout_staff_minutes"
const IDLE_MIN = 10
const IDLE_MAX = 1440

function SystemSettingsPage() {
  const tab = Route.useSearch().tab ?? "general"
  const navigate = Route.useNavigate()
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["system-settings"],
    queryFn: async () => (await SettingsService.readSystemSettings()).data,
  })
  // Kalit/qiymat sozlamalari uch kartaga kerak — kelmaguncha o'sha joyda skelet yoki xato
  const withSettings = (
    render: (settings: SystemSettingRead[]) => ReactNode,
  ) =>
    isLoading ? (
      <Skeleton className="h-48 w-full" />
    ) : isError || !data ? (
      <QueryError onRetry={() => refetch()} />
    ) : (
      render(data)
    )

  return (
    <div>
      <PageHeader
        title="Tizim sozlamalari"
        description="O'zgarish saqlangan zahoti kuchga kiradi — tizimni qayta ishga tushirish shart emas."
      />
      {/* Bitta kenglik (`max-w-5xl`) — kartalarning o'ng cheti tekis. Matn qatori o'qishga qulay
          uzunlikda qolsin deb paragraflar `max-w-prose`. */}
      <Tabs
        value={tab}
        onValueChange={(v) =>
          navigate({ search: { tab: v as SettingsTab }, replace: true })
        }
        className="max-w-5xl gap-4 [&_p]:max-w-prose"
      >
        <div className="max-w-full overflow-x-auto [scrollbar-width:none]">
          <TabsList className="h-9">
            {SETTINGS_TABS.map((t) => (
              <TabsTrigger key={t.value} value={t.value}>
                {t.label}
              </TabsTrigger>
            ))}
          </TabsList>
        </div>
        {/* `forceMount` + yashirish: tab almashganda kartadagi SAQLANMAGAN qoralama (masalan yarim
            kiritilgan ish jadvali) yo'qolmasin — Radix sukutda faol bo'lmagan tabni DOM'dan olib tashlaydi. */}
        <TabsContent value="general" forceMount className={TAB_PANEL}>
          <div className="grid items-start gap-4 lg:grid-cols-2">
            {withSettings((settings) => (
              <>
                <CustomSuffixCard settings={settings} />
                <IdleLogoutCard settings={settings} />
              </>
            ))}
          </div>
        </TabsContent>
        <TabsContent value="schedule" forceMount className={TAB_PANEL}>
          <div className="space-y-6">
            <WorkScheduleCard />
            <OeeStartCard />
          </div>
        </TabsContent>
        <TabsContent value="downtime" forceMount className={TAB_PANEL}>
          {withSettings((settings) => (
            <DowntimeReasonsCard settings={settings} />
          ))}
        </TabsContent>
        <TabsContent value="ideal" forceMount className={TAB_PANEL}>
          <div className="space-y-6">
            <IdealCycleCard />
            <KromkaCycleCard />
            <RoverCycleCard />
          </div>
        </TabsContent>
        <TabsContent value="defect" forceMount className={TAB_PANEL}>
          <div className="space-y-6">
            <DefectReasonsCard />
            {withSettings((settings) => (
              <KromkaBindCard settings={settings} />
            ))}
          </div>
        </TabsContent>
      </Tabs>
    </div>
  )
}

/** Nostandart detal belgisi (`backend/app/services/giblab/ingest.py`). */
function CustomSuffixCard({ settings }: { settings: SystemSettingRead[] }) {
  const queryClient = useQueryClient()
  const saqlangan = settings.find((x) => x.key === SUFFIX_KEY)?.value ?? ""
  const [suffix, setSuffix] = useState("")
  // Server qiymati kelgach maydon bir marta to'ldiriladi; keyin foydalanuvchi
  // yozayotganini 60s refetch bosib ketmasin.
  useEffect(() => setSuffix(saqlangan), [saqlangan])

  const mutation = useMutation({
    mutationFn: () =>
      SettingsService.updateSystemSetting({
        path: { key: SUFFIX_KEY },
        body: { value: suffix.trim() },
      }),
    ...crudCallbacks(queryClient, ["system-settings"], "Sozlama saqlandi"),
  })

  return (
    <div className={cn(cardSurface, "space-y-4 p-4")}>
      <div>
        <h2 className="text-lg font-semibold">Nostandart detal belgisi</h2>
        <p className="text-sm text-muted-foreground">
          Bazisda detal nomi shu belgi bilan tugasa, u yuklashda{" "}
          <b>nostandart</b> deb belgilanadi va marshrutini texnolog «Nostandart
          detallar» tabida chizadi.
        </p>
      </div>
      <Field label="Belgi">
        <Input
          value={suffix}
          maxLength={8}
          placeholder="#"
          className="w-40"
          onChange={(e) => setSuffix(e.target.value)}
        />
      </Field>
      <p className="text-sm text-muted-foreground">
        Belgi detal nomida qoladi, ya'ni chekda ham ko'rinadi. Qo'lda belgilash
        o'z joyida: matritsadagi «Nostandart» ustuni. Bo'sh qoldirilsa qoida{" "}
        <b>o'chadi</b>. Qoida faqat YANGI yuklashda ishlaydi, mavjud
        buyurtmalarga tegmaydi.
      </p>
      <LoadingButton
        loading={mutation.isPending}
        disabled={suffix.trim() === saqlangan.trim()}
        onClick={() => mutation.mutate()}
      >
        Saqlash
      </LoadingButton>
    </div>
  )
}

/** Harakatsizlikdan keyin chiqish (`hooks/useIdleLogout.ts`, `backend/app/services/activity.py`). */
function IdleLogoutCard({ settings }: { settings: SystemSettingRead[] }) {
  const queryClient = useQueryClient()
  const value = (key: string) =>
    settings.find((s) => s.key === key)?.value ?? ""
  const savedOperator = value(IDLE_OPERATOR_KEY)
  const savedStaff = value(IDLE_STAFF_KEY)
  const [operator, setOperator] = useState("")
  const [staff, setStaff] = useState("")
  useEffect(() => setOperator(savedOperator), [savedOperator])
  useEffect(() => setStaff(savedStaff), [savedStaff])

  const mutation = useMutation({
    mutationFn: async () => {
      if (operator !== savedOperator)
        await SettingsService.updateSystemSetting({
          path: { key: IDLE_OPERATOR_KEY },
          body: { value: operator },
        })
      if (staff !== savedStaff)
        await SettingsService.updateSystemSetting({
          path: { key: IDLE_STAFF_KEY },
          body: { value: staff },
        })
    },
    ...crudCallbacks(queryClient, ["system-settings"], "Sozlama saqlandi"),
  })

  const valid = (v: string) =>
    /^\d+$/.test(v) && Number(v) >= IDLE_MIN && Number(v) <= IDLE_MAX
  const field = (label: string, v: string, set: (v: string) => void) => (
    <Field label={label}>
      <Input
        type="number"
        inputMode="numeric"
        min={IDLE_MIN}
        max={IDLE_MAX}
        value={v}
        aria-invalid={!valid(v)}
        onChange={(e) => set(e.target.value)}
      />
    </Field>
  )

  return (
    <div className={cn(cardSurface, "space-y-4 p-4")}>
      <div>
        <h2 className="text-lg font-semibold">
          Harakatsizlikdan keyin chiqish
        </h2>
        <p className="text-sm text-muted-foreground">
          Shuncha daqiqa hech narsa bosilmasa, ekran login sahifasiga qaytadi
          (tsexda smena ham yopiladi). Terminalda stanok skaneridan kelgan skan
          ham harakat hisoblanadi. Beyjikli postda qayta kirish — beyjikni
          skanerlash. Tsex — terminal va operator hisoblari; ofis — admin,
          direktor, menejer, texnolog va mahsulot omborchisi.
        </p>
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        {field("Tsex, daqiqa", operator, setOperator)}
        {field("Ofis, daqiqa", staff, setStaff)}
      </div>
      <p className="text-sm text-muted-foreground">
        Ish jadvali tugashi hisobga olinmaydi — smena kechroq tugashi mumkin.
        Tablo ekrani chiqarilmaydi. Tsex chegarasi tushlik tanaffusidan uzun
        bo'lsin, aks holda tushlikda smena yopiladi. Oraliq: {IDLE_MIN}–
        {IDLE_MAX}.
      </p>
      <LoadingButton
        loading={mutation.isPending}
        disabled={
          !valid(operator) ||
          !valid(staff) ||
          (operator === savedOperator && staff === savedStaff)
        }
        onClick={() => mutation.mutate()}
      >
        Saqlash
      </LoadingButton>
    </div>
  )
}

// Backend `settings_service.STOP_PROMPT_IDLE_MINUTES` va `INT_RANGES` bilan bir xil
const STOP_PROMPT_KEY = "stop_prompt_idle_minutes"
const STOP_MIN = 1
const STOP_MAX = 120
// Backend `settings_service.KROMKA_IDLE_MINUTES` va `INT_RANGES` bilan bir xil
const KROMKA_IDLE_KEY = "kromka_idle_minutes"
const KROMKA_IDLE_MAX = 240
// Backend `settings_service.KROMKA_TOLERANCE_MM` / `KROMKA_BIND_WINDOW_S` va `INT_RANGES` bilan bir xil
const KROMKA_TOL_KEY = "kromka_tolerance_mm"
const KROMKA_TOL_MAX = 50
const KROMKA_BIND_KEY = "kromka_bind_window_s"
const KROMKA_BIND_MIN = 5
const KROMKA_BIND_MAX = 600

const REASONS_KEY = ["system-settings", "downtime-reasons"]

const reasonFlag = (checked: boolean, label: string, onChange: () => void) => (
  // biome-ignore lint/a11y/noLabelWithoutControl: Checkbox label ichida (Field bilan bir xil)
  <label className="flex items-center gap-1.5 whitespace-nowrap text-sm">
    <Checkbox checked={checked} onCheckedChange={onChange} />
    {label}
  </label>
)

/** Bitta guruh — egasining ro'yxatidagi ustun kabi: «Rejali» yoki «Rejasiz», o'z ro'yxati va o'z
 *  qo'shish maydoni bilan. `is_planned` ni GURUH beradi, shuning uchun qatorda «Rejali» belgisi
 *  yo'q — noto'g'ri tushgan sabab strelka bilan narigi guruhga o'tkaziladi (o'chirish yo'q). */
function ReasonGroup({
  planned,
  reasons,
  onUpdate,
}: {
  planned: boolean
  reasons: DowntimeReasonRead[]
  onUpdate: (id: number, body: DowntimeReasonUpdate) => void
}) {
  const queryClient = useQueryClient()
  const [name, setName] = useState("")
  const callbacks = crudCallbacks(queryClient, REASONS_KEY, "Sabab qo'shildi")
  const create = useMutation({
    mutationFn: () =>
      SettingsService.createDowntimeReason({
        body: { name: name.trim(), is_planned: planned, needs_note: false },
      }),
    ...callbacks,
    onSuccess: () => {
      callbacks.onSuccess()
      setName("")
    },
  })
  const canAdd = name.trim() !== "" && !create.isPending

  return (
    <div className="space-y-2">
      <div>
        <div className="flex items-baseline justify-between">
          <h3 className="font-semibold">{planned ? "Rejali" : "Rejasiz"}</h3>
          <span className="num text-xs text-muted-foreground">
            {reasons.length} ta
          </span>
        </div>
        <p className="text-xs text-muted-foreground">
          {planned
            ? "OEE reja vaqtidan chiqariladi — Availability'ni tushirmaydi."
            : "Reja vaqti ichidagi yo'qotish — Availability'ni tushiradi."}
        </p>
      </div>
      {reasons.length === 0 && (
        <p className="text-sm text-muted-foreground">Hali sabab yo'q.</p>
      )}
      {reasons.map((r) => (
        <div
          key={r.id}
          className={cn(
            "flex flex-wrap items-center gap-x-3 gap-y-1 rounded-lg border px-3 py-2",
            !r.is_active && "opacity-50",
          )}
        >
          <Input
            defaultValue={r.name}
            maxLength={60}
            className="h-9 min-w-40 flex-1"
            onBlur={(e) => {
              const next = e.target.value.trim()
              if (next && next !== r.name) onUpdate(r.id, { name: next })
            }}
          />
          {reasonFlag(r.needs_note, "Izoh majburiy", () =>
            onUpdate(r.id, { needs_note: !r.needs_note }),
          )}
          {reasonFlag(r.is_active, "Faol", () =>
            onUpdate(r.id, { is_active: !r.is_active }),
          )}
          <RowAction
            icon={ArrowRightLeft}
            title={planned ? "Rejasizga o'tkazish" : "Rejaliga o'tkazish"}
            onClick={() => onUpdate(r.id, { is_planned: !planned })}
          />
        </div>
      ))}
      <div className="flex items-center gap-2 rounded-lg border border-dashed px-3 py-2">
        <Input
          value={name}
          maxLength={60}
          placeholder={planned ? "Masalan: Tushlik" : "Masalan: Elektr yo'q"}
          className="h-9 flex-1"
          onChange={(e) => setName(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && canAdd) create.mutate()
          }}
        />
        <LoadingButton
          size="sm"
          loading={create.isPending}
          disabled={!canAdd}
          onClick={() => create.mutate()}
        >
          <Plus /> Qo'shish
        </LoadingButton>
      </div>
    </div>
  )
}

/** To'xtash sabablari: terminal oynasi qachon chiqadi va qaysi sabablar tanlanadi
 *  (`components/Terminal/DowntimeReason.tsx`, `backend/app/services/downtimes.py`). */
function DowntimeReasonsCard({ settings }: { settings: SystemSettingRead[] }) {
  const queryClient = useQueryClient()
  const saved = settings.find((s) => s.key === STOP_PROMPT_KEY)?.value ?? ""
  const [minutes, setMinutes] = useState("")
  useEffect(() => setMinutes(saved), [saved])
  const savedIdle = settings.find((s) => s.key === KROMKA_IDLE_KEY)?.value ?? ""
  const [idle, setIdle] = useState("")
  useEffect(() => setIdle(savedIdle), [savedIdle])
  const idleValid =
    /^\d+$/.test(idle) &&
    Number(idle) >= STOP_MIN &&
    Number(idle) <= KROMKA_IDLE_MAX
  const saveIdle = useMutation({
    mutationFn: () =>
      SettingsService.updateSystemSetting({
        path: { key: KROMKA_IDLE_KEY },
        body: { value: idle },
      }),
    ...crudCallbacks(queryClient, ["system-settings"], "Sozlama saqlandi"),
  })
  const saveMinutes = useMutation({
    mutationFn: () =>
      SettingsService.updateSystemSetting({
        path: { key: STOP_PROMPT_KEY },
        body: { value: minutes },
      }),
    ...crudCallbacks(queryClient, ["system-settings"], "Sozlama saqlandi"),
  })
  const minutesValid =
    /^\d+$/.test(minutes) &&
    Number(minutes) >= STOP_MIN &&
    Number(minutes) <= STOP_MAX

  const {
    data: reasons = [],
    isError,
    refetch,
  } = useQuery({
    queryKey: REASONS_KEY,
    queryFn: async () => (await SettingsService.readDowntimeReasons()).data,
  })
  const update = useMutation({
    mutationFn: (v: { id: number; body: DowntimeReasonUpdate }) =>
      SettingsService.updateDowntimeReason({
        path: { reason_id: v.id },
        body: v.body,
      }),
    ...crudCallbacks(queryClient, REASONS_KEY, "Sabab o'zgardi"),
  })

  return (
    <div className={cn(cardSurface, "space-y-5 p-4")}>
      <div>
        <h2 className="text-lg font-semibold">To'xtash sabablari</h2>
        <p className="text-sm text-muted-foreground">
          Pico ulangan stanokda terminal to'xtash sababini o'zi so'raydi —
          to'xtash quyidagi chegaradan uzoq davom etsa. Qoida hamma turga bir
          xil: qizil chiroq (avariya), hamma chiroq o'chgani, sariq chiroq,
          kromka va rover lentasining to'xtashi. Qulf tugmasi ham avval sababni
          so'raydi. Sababni smenada ishlayotgan hodim tanlaydi.
        </p>
      </div>
      <div className="flex items-end gap-3">
        <Field label="Stanok ishlamasa sabab so'ralsin, daqiqa">
          <Input
            type="number"
            inputMode="numeric"
            min={STOP_MIN}
            max={STOP_MAX}
            value={minutes}
            aria-invalid={!minutesValid}
            onChange={(e) => setMinutes(e.target.value)}
            className="w-full"
          />
        </Field>
        <LoadingButton
          loading={saveMinutes.isPending}
          disabled={!minutesValid || minutes === saved}
          onClick={() => saveMinutes.mutate()}
        >
          Saqlash
        </LoadingButton>
      </div>
      <p className="text-sm text-muted-foreground">
        Vaqt to'xtash BOSHLANGAN paytdan sanaladi: prisadkada chiroq o'zgargan
        lahzadan, kromka va roverda lenta/shpindel to'xtagan paytdan (RUN
        kirishi). Juda kichik qiymat (1–2 daqiqa) detal almashtirish kabi oddiy
        kutishlarda ham oyna chiqaradi. Chegaradan qisqa to'xtash hisobdan
        chiqmaydi — Availability oraliqlardan hisoblanadi, faqat sababi
        so'ralmaydi. Oraliq: {STOP_MIN}–{STOP_MAX}.
      </p>

      {/* Kromkada IKKINCHI holat bor: lenta yuryapti, lekin detal o'tmayapti.
          RUN kirishi buni aytmaydi — o'lchovlar orasidagi tirqish aytadi. */}
      <div className="flex items-end gap-3">
        <Field label="Kromka bo'sh yursa (detal o'tmasa), daqiqa">
          <Input
            type="number"
            inputMode="numeric"
            min={STOP_MIN}
            max={KROMKA_IDLE_MAX}
            value={idle}
            aria-invalid={!idleValid}
            onChange={(e) => setIdle(e.target.value)}
            className="w-40"
          />
        </Field>
        <LoadingButton
          loading={saveIdle.isPending}
          disabled={!idleValid || idle === savedIdle}
          onClick={() => saveIdle.mutate()}
        >
          Saqlash
        </LoadingButton>
      </div>
      <p className="text-sm text-muted-foreground">
        Lenta yuryapti-yu, shuncha daqiqa bitta ham detal o'tmasa — bu ham
        to'xtash (material yo'q, buyurtma yo'q, operator ketgan): sabab
        so'raladi va o'sha vaqt «ishladi» dan chiqadi. To'xtash chegarasidan
        uzunroq bo'lgani ma'qul — detal almashtirish ritmi jazolanmasin. Oraliq:{" "}
        {STOP_MIN}–{KROMKA_IDLE_MAX}.
      </p>

      <section className="space-y-3">
        {isError ? (
          <QueryError onRetry={() => refetch()} />
        ) : (
          <div className="grid gap-4 lg:grid-cols-2">
            {[true, false].map((planned) => (
              <ReasonGroup
                key={String(planned)}
                planned={planned}
                reasons={reasons.filter((r) => r.is_planned === planned)}
                onUpdate={(id, body) => update.mutate({ id, body })}
              />
            ))}
          </div>
        )}
        <p className="text-sm text-muted-foreground">
          Ikkala ro'yxat ham bo'sh bo'lsa terminal sabab so'ramaydi, qulf esa
          sababsiz ishlaydi. Sabab o'chirilmaydi — eski to'xtashlar sababini
          yo'qotmasin; kerak bo'lmasa "Faol" belgisini oling.
        </p>
      </section>
    </div>
  )
}

type Shift = WorkShift & { breaks: WorkBreak[] }
type Schedule = { shifts: Shift[]; days_off: number[]; holidays: Holiday[] }

const MAX_SHIFTS = 4
const MAX_BREAKS = 10
// ISO: 1 = dushanba ... 7 = yakshanba (backend `WorkSchedule.days_off` bilan bir xil)
const WEEKDAYS = [
  "Dushanba",
  "Seshanba",
  "Chorshanba",
  "Payshanba",
  "Juma",
  "Shanba",
  "Yakshanba",
]

const toSchedule = (d: WorkSchedule): Schedule => ({
  shifts: (d.shifts ?? []).map((s) => ({ ...s, breaks: s.breaks ?? [] })),
  days_off: d.days_off ?? [],
  holidays: d.holidays ?? [],
})

const minutes = (clock: string) => {
  const [h, m] = clock.split(":").map(Number)
  return h * 60 + m
}
// Sutka aylanasida: 22:00 -> 06:00 = 8 soat (tungi smena)
const span = (start: string, end: string) =>
  (minutes(end) - minutes(start) + 1440) % 1440

const plusHours = (clock: string, hours: number) => {
  const t = (minutes(clock) + hours * 60) % 1440
  return `${String(Math.floor(t / 60)).padStart(2, "0")}:${String(t % 60).padStart(2, "0")}`
}

// ---------- Ideal sikl (OEE Performance, Prisadka) ----------

// Backend `schemas/settings.py: IdealCycle` / `Seconds` bilan bir xil (0..600 s)
// Backend `schemas/settings.py: DefectReasons` bilan bir xil (30 ta, har biri `Name` — 40 belgi)
const MAX_DEFECT_REASONS = 30

const IDEAL_MAX = 600
const IDEAL_FIELDS: { key: keyof IdealCycle; label: string; hint: string }[] = [
  {
    key: "load_s",
    label: "Har detalga, s",
    hint: "Skan, qo'yish, qisish, olish",
  },
  { key: "bore_s", label: "Yuza teshik, s", hint: "Har bir teshikka" },
  { key: "edge_bore_s", label: "Qirra teshik, s", hint: "Har bir teshikka" },
  { key: "groove_s", label: "Paz, s", hint: "Har bir pazga" },
  { key: "mill_s", label: "Freza, s", hint: "Har bir konturga" },
]

/** Prisadka ideal sikli: detalning ideal vaqti = har detalga + ishlovlar soni × soniya
 *  (`backend/app/services/performance.py`). Hisobotlar → «Stanok vaqti» dagi Performance shundan. */
function IdealCycleCard() {
  const queryClient = useQueryClient()
  const queryKey = ["system-settings", "ideal-cycle"]
  const { data, isError, refetch } = useQuery({
    queryKey,
    queryFn: async () => (await SettingsService.readIdealCycle()).data,
  })
  const [draft, setDraft] = useState<Record<string, string>>({})
  useEffect(() => {
    if (data)
      setDraft(
        Object.fromEntries(
          IDEAL_FIELDS.map((f) => [f.key, String(data[f.key] ?? 0)]),
        ),
      )
  }, [data])
  const num = (key: string) => Number(draft[key])
  const fieldValid = (key: string) =>
    (draft[key] ?? "").trim() !== "" &&
    Number.isFinite(num(key)) &&
    num(key) >= 0 &&
    num(key) <= IDEAL_MAX
  const valid = IDEAL_FIELDS.every((f) => fieldValid(f.key))
  const dirty =
    !!data && IDEAL_FIELDS.some((f) => num(f.key) !== (data[f.key] ?? 0))
  const save = useMutation({
    mutationFn: () =>
      SettingsService.updateIdealCycle({
        body: Object.fromEntries(
          IDEAL_FIELDS.map((f) => [f.key, num(f.key)]),
        ) as IdealCycle,
      }),
    ...crudCallbacks(queryClient, queryKey, "Ideal sikl saqlandi"),
  })
  // Jonli misol — raqam qanchalik ma'noli ekanini sekundomer bilan solishtirish uchun
  const sample = (b: number, e: number, g: number, m: number) =>
    valid
      ? `${Math.round((num("load_s") + b * num("bore_s") + e * num("edge_bore_s") + g * num("groove_s") + m * num("mill_s")) * 10) / 10} s`
      : "—"

  return (
    <div className={cn(cardSurface, "space-y-4 p-4")}>
      <div>
        <h2 className="text-lg font-semibold">Ideal sikl (Prisadka)</h2>
        <p className="text-sm text-muted-foreground">
          OEE Performance shundan hisoblanadi: detalning ideal vaqti = har
          detalga vaqt + teshik, paz va frezalar soni × soniya. Detaldagi
          ishlovlar soni loyiha faylidan olinadi. Boshlang'ich qiymatlar
          TAXMINIY — tsexda sekundomer bilan 5–10 detalni o'lchab to'g'rilang.
        </p>
      </div>
      {isError ? (
        <QueryError onRetry={() => refetch()} />
      ) : (
        <>
          <div className="grid gap-3 sm:grid-cols-3 lg:grid-cols-5">
            {IDEAL_FIELDS.map((f) => (
              <Field key={f.key} label={f.label}>
                <Input
                  type="number"
                  inputMode="decimal"
                  min={0}
                  max={IDEAL_MAX}
                  step={0.5}
                  value={draft[f.key] ?? ""}
                  title={f.hint}
                  aria-invalid={!fieldValid(f.key)}
                  onChange={(e) =>
                    setDraft((d) => ({ ...d, [f.key]: e.target.value }))
                  }
                />
              </Field>
            ))}
          </div>
          <p className="text-sm text-muted-foreground">
            Misol: 6 yuza teshikli detal — {sample(6, 0, 0, 0)}; 10 yuza va 4
            qirra teshik, 1 paz, 1 freza — {sample(10, 4, 1, 1)}. Oraliq: 0–
            {IDEAL_MAX} s. O'zgartirilsa hisobot o'tgan kunlarni ham yangi
            qiymat bilan qayta hisoblaydi. Performance 100% dan oshsa —
            qiymatlar yumshoq; Hisobotlar → «Stanok vaqti» da ideal vaqt Pico
            o'lchagan sikl vaqti bilan yonma-yon turadi.
          </p>
          <LoadingButton
            loading={save.isPending}
            disabled={!valid || !dirty}
            onClick={() => save.mutate()}
          >
            Saqlash
          </LoadingButton>
        </>
      )}
    </div>
  )
}

// ---------- Brak sabablari (OEE Quality) ----------

/** Brak sabablari — terminaldagi BRAK oynasida tugma bo'lib chiqadi. Alohida jadval EMAS:
 *  sabab brak yozuviga MATN bo'lib ko'chiriladi (`part_defect.reason`), ya'ni ro'yxatdan
 *  olib tashlangan sabab eski yozuvlarda o'qilaveradi va "nofaol" belgisi kerak emas. */
function DefectReasonsCard() {
  const queryClient = useQueryClient()
  const queryKey = ["system-settings", "defect-reasons"]
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey,
    queryFn: async () => (await SettingsService.readDefectReasons()).data,
  })
  const [draft, setDraft] = useState<string[]>([])
  const [yangi, setYangi] = useState("")
  useEffect(() => {
    if (data) setDraft(data.reasons ?? [])
  }, [data])

  const save = useMutation({
    mutationFn: () =>
      SettingsService.updateDefectReasons({ body: { reasons: draft } }),
    ...crudCallbacks(queryClient, queryKey, "Brak sabablari saqlandi"),
  })
  const nom = yangi.trim()
  const canAdd =
    nom !== "" && !draft.includes(nom) && draft.length < MAX_DEFECT_REASONS
  const add = () => {
    setDraft((d) => [...d, nom])
    setYangi("")
  }
  const changed = JSON.stringify(draft) !== JSON.stringify(data?.reasons ?? [])

  if (isLoading) return <Skeleton className="h-48 w-full" />
  if (isError) return <QueryError onRetry={() => refetch()} />

  return (
    <div className={cn(cardSurface, "space-y-4 p-4")}>
      <div>
        <h2 className="text-lg font-semibold">Brak sabablari</h2>
        <p className="text-sm text-muted-foreground">
          Operator detalni skanerlab, skan tasmasidagi BRAK tugmasini bosganda
          shu tugmalar chiqadi. OEE Quality shundan hisoblanadi: (detallar −
          brak) ÷ detallar; brak kiritilmasa 100%.
        </p>
      </div>
      {draft.length === 0 && (
        <p className="text-sm text-muted-foreground">
          Hali sabab yo'q — terminalda BRAK tugmasi umuman ko'rinmaydi.
        </p>
      )}
      <ul className="grid gap-2 sm:grid-cols-2">
        {draft.map((r) => (
          <li
            key={r}
            className="flex items-center justify-between gap-2 rounded-lg border px-3 py-1.5"
          >
            <span className="truncate font-medium">{r}</span>
            <Button
              variant="ghost"
              size="icon-sm"
              aria-label={`${r} sababini o'chirish`}
              onClick={() => setDraft((d) => d.filter((x) => x !== r))}
            >
              <Trash2 />
            </Button>
          </li>
        ))}
      </ul>
      <div className="flex items-center gap-2 rounded-lg border border-dashed px-3 py-2">
        <Input
          value={yangi}
          maxLength={40}
          placeholder="Masalan: O'lcham noto'g'ri"
          className="h-9 flex-1"
          onChange={(e) => setYangi(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && canAdd) add()
          }}
        />
        <Button size="sm" disabled={!canAdd} onClick={add}>
          <Plus /> Qo'shish
        </Button>
      </div>
      <p className="text-sm text-muted-foreground">
        Sabab o'chirilsa ESKI brak yozuvlari o'zgarmaydi — ularda sabab matn
        bo'lib saqlangan. Ko'pi bilan {MAX_DEFECT_REASONS} ta. Brak skanni bekor
        qilmaydi va marshrutni qayta ochmaydi: hozircha faqat o'lchanadi.
      </p>
      <LoadingButton
        loading={save.isPending}
        disabled={!changed}
        onClick={() => save.mutate()}
      >
        Saqlash
      </LoadingButton>
    </div>
  )
}

/** Kromka o'lchovining DOPUSKI va skanga bog'lash oynasi
 *  (`backend/app/services/kromka.py`). Ikkalasi ham brak qachon e'lon qilinishini
 *  hal qiladi, shuning uchun brak sabablari bilan bitta tabda. */
function KromkaBindCard({ settings }: { settings: SystemSettingRead[] }) {
  const queryClient = useQueryClient()
  const savedTol = settings.find((x) => x.key === KROMKA_TOL_KEY)?.value ?? ""
  const savedBind = settings.find((x) => x.key === KROMKA_BIND_KEY)?.value ?? ""
  const [tol, setTol] = useState("")
  const [bind, setBind] = useState("")
  useEffect(() => setTol(savedTol), [savedTol])
  useEffect(() => setBind(savedBind), [savedBind])
  const ok = (v: string, min: number, max: number) =>
    /^\d+$/.test(v) && Number(v) >= min && Number(v) <= max
  const saqla = (key: string, value: string) =>
    SettingsService.updateSystemSetting({ path: { key }, body: { value } })
  const saveTol = useMutation({
    mutationFn: () => saqla(KROMKA_TOL_KEY, tol),
    ...crudCallbacks(queryClient, ["system-settings"], "Sozlama saqlandi"),
  })
  const saveBind = useMutation({
    mutationFn: () => saqla(KROMKA_BIND_KEY, bind),
    ...crudCallbacks(queryClient, ["system-settings"], "Sozlama saqlandi"),
  })

  return (
    <div className={cn(cardSurface, "space-y-5 p-4")}>
      <div>
        <h2 className="text-lg font-semibold">Kromka o'lchovi</h2>
        <p className="text-sm text-muted-foreground">
          Stansiya o'lchagan uzunlik detalning kutilgan tomoni bilan
          solishtiriladi. Tomonlar <b>guruh</b> bo'yicha sanaladi (uzunlik va
          eni), tartib ahamiyatsiz: operator qaysi tomonni oldin qo'ysa, o'sha
          guruhdan bitta joy yopiladi. Mos kelmasa terminalda brak oynasi
          ochiladi va operator sababni tanlaydi.
        </p>
      </div>
      <div className="flex items-end gap-3">
        <Field label="Dopusk, mm">
          <Input
            type="number"
            inputMode="numeric"
            min={1}
            max={KROMKA_TOL_MAX}
            value={tol}
            aria-invalid={!ok(tol, 1, KROMKA_TOL_MAX)}
            className="w-40"
            onChange={(e) => setTol(e.target.value)}
          />
        </Field>
        <LoadingButton
          loading={saveTol.isPending}
          disabled={!ok(tol, 1, KROMKA_TOL_MAX) || tol === savedTol}
          onClick={() => saveTol.mutate()}
        >
          Saqlash
        </LoadingButton>
      </div>
      <p className="text-sm text-muted-foreground">
        Lenta detalni HARAKATDA o'lchaydi — tezlik va datchik kechikishi bir
        necha millimetr beradi. Juda kichik dopusk har detalni brak qilib
        ko'rsatadi, juda kattasi haqiqiy xatoni o'tkazib yuboradi. Oraliq: 1–
        {KROMKA_TOL_MAX}.
      </p>
      <div className="flex items-end gap-3">
        <Field label="Skanga bog'lash oynasi, soniya">
          <Input
            type="number"
            inputMode="numeric"
            min={KROMKA_BIND_MIN}
            max={KROMKA_BIND_MAX}
            value={bind}
            aria-invalid={!ok(bind, KROMKA_BIND_MIN, KROMKA_BIND_MAX)}
            className="w-40"
            onChange={(e) => setBind(e.target.value)}
          />
        </Field>
        <LoadingButton
          loading={saveBind.isPending}
          disabled={
            !ok(bind, KROMKA_BIND_MIN, KROMKA_BIND_MAX) || bind === savedBind
          }
          onClick={() => saveBind.mutate()}
        >
          Saqlash
        </LoadingButton>
      </div>
      <p className="text-sm text-muted-foreground">
        Detal birinchi datchikka <b>kirgan lahza</b> hisoblanadi (o'lchov
        vaqtidan lenta yurish vaqti ayiriladi) va shu lahza atrofidagi skanlar
        nomzod bo'ladi; ular orasidan o'lchamga mos keladigani tanlanadi. Oxirgi
        skanga bog'lash XATO berardi: detal datchiklar orasida 8–15 soniya
        yuradi, operator esa 4–10 soniyada bir marta skanerlaydi — o'lchov
        keyingi detalga yopishib qolardi. Skan topilmasa o'lchov «skansiz»
        bo'lib yoziladi va hech kimni ayblamaydi. Oraliq: {KROMKA_BIND_MIN}–
        {KROMKA_BIND_MAX}.
      </p>
    </div>
  )
}

/** Kromka ideal sikli. Prisadkadan FARQI: u yerda beshta taxminiy koeffitsiyent bor,
 *  bu yerda esa ideal vaqtni lenta belgilaydi va uzunlikni stansiya O'LCHAYDI —
 *  sozlanadigan yagona narsa detallar orasidagi bo'shliq
 *  (`backend/app/services/performance.py: kromka_ideal_seconds`). */
function KromkaCycleCard() {
  const queryClient = useQueryClient()
  const queryKey = ["system-settings", "ideal-cycle-kromka"]
  const { data, isError, refetch } = useQuery({
    queryKey,
    queryFn: async () => (await SettingsService.readIdealCycleKromka()).data,
  })
  const [gap, setGap] = useState("")
  useEffect(() => {
    if (data) setGap(String(data.gap_s ?? 0))
  }, [data])
  const n = Number(gap)
  const valid =
    gap.trim() !== "" && Number.isFinite(n) && n >= 0 && n <= IDEAL_MAX
  const save = useMutation({
    mutationFn: () =>
      SettingsService.updateIdealCycleKromka({ body: { gap_s: n } }),
    ...crudCallbacks(queryClient, queryKey, "Kromka sikli saqlandi"),
  })
  // Jonli misol: 2000 mm li detal 18 m/min da — lenta vaqti + oraliq
  const misol = (mm: number, v: number) =>
    valid ? `${Math.round((mm / ((v * 1000) / 60) + n) * 10) / 10} s` : "—"

  return (
    <div className={cn(cardSurface, "space-y-4 p-4")}>
      <div>
        <h2 className="text-lg font-semibold">Ideal sikl (Kromka)</h2>
        <p className="text-sm text-muted-foreground">
          Kromkada ideal vaqtni lenta belgilaydi:{" "}
          <b>ideal = uzunlik ÷ tezlik + oraliq</b>. Uzunlikni stansiyaning o'zi
          o'lchaydi, tezlikni (10 yoki 18 m/min) Pico yuboradi — shuning uchun
          taxminiy koeffitsiyent yo'q. Sozlanadigan yagona qiymat: operator
          keyingi detalni qo'yguncha ketadigan bo'shliq.
        </p>
      </div>
      {isError ? (
        <QueryError onRetry={() => refetch()} />
      ) : (
        <>
          <Field label="Detallar orasidagi bo'shliq, s">
            <Input
              type="number"
              inputMode="decimal"
              min={0}
              max={IDEAL_MAX}
              step={0.5}
              value={gap}
              aria-invalid={!valid}
              className="w-40"
              onChange={(e) => setGap(e.target.value)}
            />
          </Field>
          <p className="text-sm text-muted-foreground">
            Misol: 2000 mm detal 18 m/min da — {misol(2000, 18)}; 800 mm detal
            10 m/min da — {misol(800, 10)}. Har qirra alohida o'tish: to'rt
            qirrali detal to'rt marta sanaladi. Tsexda sekundomer bilan
            o'lchang.
          </p>
          <LoadingButton
            loading={save.isPending}
            disabled={!valid || n === (data?.gap_s ?? 0)}
            onClick={() => save.mutate()}
          >
            Saqlash
          </LoadingButton>
        </>
      )}
    </div>
  )
}

/** ROVER (CNC 2130) ideal sikli: detalning ideal vaqti = har detalga + perimetr (m) × metrga
 *  soniya (`backend/app/services/performance.py: rover_ideal_seconds`). Birlik — DETAL. */
function RoverCycleCard() {
  const queryClient = useQueryClient()
  const queryKey = ["system-settings", "ideal-cycle-rover"]
  const { data, isError, refetch } = useQuery({
    queryKey,
    queryFn: async () => (await SettingsService.readIdealCycleRover()).data,
  })
  const [load, setLoad] = useState("")
  const [perM, setPerM] = useState("")
  useEffect(() => {
    if (data) {
      setLoad(String(data.load_s ?? 0))
      setPerM(String(data.cut_s_per_m ?? 0))
    }
  }, [data])
  const ok = (s: string) =>
    s.trim() !== "" &&
    Number.isFinite(Number(s)) &&
    Number(s) >= 0 &&
    Number(s) <= IDEAL_MAX
  const valid = ok(load) && ok(perM)
  const dirty =
    !!data &&
    (Number(load) !== (data.load_s ?? 0) ||
      Number(perM) !== (data.cut_s_per_m ?? 0))
  const save = useMutation({
    mutationFn: () =>
      SettingsService.updateIdealCycleRover({
        body: { load_s: Number(load), cut_s_per_m: Number(perM) },
      }),
    ...crudCallbacks(queryClient, queryKey, "Rover sikli saqlandi"),
  })
  // Jonli misol: detal o'lchami (mm) — perimetr metrda
  const misol = (l: number, w: number) =>
    valid
      ? `${Math.round((Number(load) + ((2 * (l + w)) / 1000) * Number(perM)) * 10) / 10} s`
      : "—"

  return (
    <div className={cn(cardSurface, "space-y-4 p-4")}>
      <div>
        <h2 className="text-lg font-semibold">Ideal sikl (Rover)</h2>
        <p className="text-sm text-muted-foreground">
          Roverda ish hajmini kontur uzunligi belgilaydi:{" "}
          <b>ideal = har detalga + perimetr (m) × metrga soniya</b>. Perimetr
          detal o'lchamidan olinadi. Metrga soniya = 60 ÷ surish (m/min): 10
          m/min — 6 s. Boshlang'ich qiymatlar TAXMINIY — tsexda sekundomer bilan
          5–10 detalni o'lchab to'g'rilang.
        </p>
      </div>
      {isError ? (
        <QueryError onRetry={() => refetch()} />
      ) : (
        <>
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label="Har detalga, s">
              <Input
                type="number"
                inputMode="decimal"
                min={0}
                max={IDEAL_MAX}
                step={0.5}
                value={load}
                title="List qo'yish, nolga keltirish, detalni olishning ulushi"
                aria-invalid={!ok(load)}
                onChange={(e) => setLoad(e.target.value)}
              />
            </Field>
            <Field label="Kontur metriga, s">
              <Input
                type="number"
                inputMode="decimal"
                min={0}
                max={IDEAL_MAX}
                step={0.5}
                value={perM}
                title="60 ÷ surish tezligi (m/min)"
                aria-invalid={!ok(perM)}
                onChange={(e) => setPerM(e.target.value)}
              />
            </Field>
          </div>
          <p className="text-sm text-muted-foreground">
            Misol: 600×400 mm detal — {misol(600, 400)}; 2000×600 mm detal —{" "}
            {misol(2000, 600)}. Oraliq: 0–{IDEAL_MAX} s. O'zgartirilsa hisobot
            o'tgan kunlarni ham yangi qiymat bilan qayta hisoblaydi.
          </p>
          <LoadingButton
            loading={save.isPending}
            disabled={!valid || !dirty}
            onClick={() => save.mutate()}
          >
            Saqlash
          </LoadingButton>
        </>
      )}
    </div>
  )
}

function netWork(shift: Shift): string {
  const total =
    span(shift.start, shift.end) -
    shift.breaks.reduce((sum, b) => sum + span(b.start, b.end), 0)
  return `${Math.floor(total / 60)} soat ${total % 60} daqiqa`
}

/** OEE qaysi KUNDAN hisoblanadi. Sozlamalar (ish jadvali, to'xtash sabablari, ideal sikl)
 *  kiritilgungacha yig'ilgan qayd o'rtachani pastga tortadi — tsex raqamga ishonmay qo'yadi.
 *  Ma'lumot o'chirilmaydi, faqat «Stanok vaqti» hisobotidan tashqarida qoladi. */
function OeeStartCard() {
  const queryClient = useQueryClient()
  const queryKey = ["system-settings", "oee-start"]
  const { data, isError, refetch } = useQuery({
    queryKey,
    queryFn: async () => (await SettingsService.readOeeStart()).data,
  })
  const saved = data?.start ?? ""
  const [day, setDay] = useState("")
  useEffect(() => setDay(saved), [saved])
  const save = useMutation({
    mutationFn: () =>
      SettingsService.updateOeeStart({ body: { start: day || null } }),
    ...crudCallbacks(queryClient, queryKey, "Sozlama saqlandi"),
  })
  const bugun = new Date().toLocaleDateString("sv-SE")

  return (
    <div className={cn(cardSurface, "space-y-4 p-4")}>
      <div>
        <h2 className="text-lg font-semibold">OEE qaysi kundan hisoblanadi</h2>
        <p className="text-sm text-muted-foreground">
          Shu kundan OLDINGI kunlar «Stanok vaqti» hisobotiga umuman kirmaydi.
          OEE ish jadvali, to'xtash sabablari va ideal sikl kiritilgandan keyin
          ma'noga ega — undan oldingi qayd (yarim ulangan stansiya, jadvalsiz
          kun, sinov ma'lumoti) ko'rsatkichni pastga tortadi. Qayddlarning o'zi
          o'chirilmaydi, ular joyida qoladi.
        </p>
      </div>
      {isError ? (
        <QueryError onRetry={() => refetch()} />
      ) : (
        <>
          <div className="flex flex-wrap items-end gap-3">
            <Field label="Boshlanish sanasi">
              <DatePicker
                value={day}
                onChange={setDay}
                placeholder="Cheklov yo'q"
                className="w-56"
              />
            </Field>
            <Button
              variant="outline"
              disabled={day === bugun}
              onClick={() => setDay(bugun)}
            >
              Bugundan
            </Button>
            {day && (
              <Button variant="ghost" onClick={() => setDay("")}>
                Cheklovni olib tashlash
              </Button>
            )}
          </div>
          <p className="text-sm text-muted-foreground">
            Bo'sh qoldirilsa butun tarix hisoblanadi. Sana keyin ham
            o'zgartiriladi — hisobot har safar qaytadan hisoblanadi.
          </p>
          <LoadingButton
            loading={save.isPending}
            disabled={day === saved}
            onClick={() => save.mutate()}
          >
            Saqlash
          </LoadingButton>
        </>
      )}
    </div>
  )
}

function WorkScheduleCard() {
  const queryClient = useQueryClient()
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["system-settings", "work-schedule"],
    queryFn: async () =>
      toSchedule((await SettingsService.readWorkSchedule()).data),
  })
  const [draft, setDraft] = useState<Schedule>({
    shifts: [],
    days_off: [],
    holidays: [],
  })
  const [newDay, setNewDay] = useState("")
  const [newName, setNewName] = useState("")
  // Server javobi kelganda (va saqlashdan keyingi refetch'da) forma shu bilan to'ladi
  useEffect(() => {
    if (data) setDraft(data)
  }, [data])

  const mutation = useMutation({
    mutationFn: () => SettingsService.updateWorkSchedule({ body: draft }),
    ...crudCallbacks(
      queryClient,
      ["system-settings", "work-schedule"],
      "Ish jadvali saqlandi",
    ),
  })

  if (isLoading) return <Skeleton className="h-64 w-full" />
  if (isError) return <QueryError onRetry={() => refetch()} />

  const setShift = (i: number, patch: Partial<Shift>) =>
    setDraft((d) => ({
      ...d,
      shifts: d.shifts.map((s, j) => (j === i ? { ...s, ...patch } : s)),
    }))
  const setBreak = (i: number, k: number, patch: Partial<WorkBreak>) =>
    setShift(i, {
      breaks: draft.shifts[i].breaks.map((b, j) =>
        j === k ? { ...b, ...patch } : b,
      ),
    })
  const toggleDay = (day: number) =>
    setDraft((d) => ({
      ...d,
      days_off: d.days_off.includes(day)
        ? d.days_off.filter((x) => x !== day)
        : [...d.days_off, day].sort((a, b) => a - b),
    }))
  const addHoliday = () => {
    setDraft((d) => ({
      ...d,
      holidays: [...d.holidays, { day: newDay, name: newName.trim() }].sort(
        (a, b) => a.day.localeCompare(b.day),
      ),
    }))
    setNewDay("")
    setNewName("")
  }

  // Bo'sh nom yoki vaqt serverda umumiy 422 bo'lardi — tugma shu yerda o'chadi
  const incomplete = draft.shifts.some(
    (s) =>
      !s.name.trim() ||
      !s.start ||
      !s.end ||
      s.breaks.some((b) => !b.name.trim() || !b.start || !b.end),
  )
  const changed = JSON.stringify(draft) !== JSON.stringify(data)

  return (
    <div className={cn(cardSurface, "space-y-6 p-4")}>
      <div>
        <h2 className="text-lg font-semibold">Ish jadvali</h2>
        <p className="text-sm text-muted-foreground">
          Smenalar, tanaffuslar va dam olish kunlari — hamma ish markaziga
          umumiy. OEE reja vaqti shundan hisoblanadi: smena vaqti minus
          tanaffuslar, dam olish kunlarida reja yo'q.
        </p>
      </div>

      <section className="space-y-3">
        <h3 className="font-medium">Smenalar ({draft.shifts.length})</h3>
        {draft.shifts.length === 0 && (
          <p className="text-sm text-muted-foreground">Smena kiritilmagan.</p>
        )}
        {draft.shifts.map((shift, i) => (
          <div key={i} className="space-y-3 rounded-lg border p-3">
            <div className="grid grid-cols-2 items-end gap-2 sm:grid-cols-[1fr_9rem_9rem_auto]">
              <Field label="Smena nomi">
                <Input
                  value={shift.name}
                  maxLength={40}
                  onChange={(e) => setShift(i, { name: e.target.value })}
                />
              </Field>
              <Field label="Boshlanishi">
                <Input
                  type="time"
                  value={shift.start}
                  onChange={(e) => setShift(i, { start: e.target.value })}
                />
              </Field>
              <Field label="Tugashi">
                <Input
                  type="time"
                  value={shift.end}
                  onChange={(e) => setShift(i, { end: e.target.value })}
                />
              </Field>
              <Button
                variant="ghost"
                size="icon"
                aria-label={`${shift.name} smenasini o'chirish`}
                onClick={() =>
                  setDraft((d) => ({
                    ...d,
                    shifts: d.shifts.filter((_, j) => j !== i),
                  }))
                }
              >
                <Trash2 />
              </Button>
            </div>

            <div className="space-y-2 pl-3">
              {shift.breaks.map((brk, k) => (
                <div
                  key={k}
                  className="grid grid-cols-2 items-end gap-2 sm:grid-cols-[1fr_9rem_9rem_auto]"
                >
                  <Field label="Tanaffus">
                    <Input
                      value={brk.name}
                      maxLength={40}
                      onChange={(e) => setBreak(i, k, { name: e.target.value })}
                    />
                  </Field>
                  <Field label="Boshlanishi">
                    <Input
                      type="time"
                      value={brk.start}
                      onChange={(e) =>
                        setBreak(i, k, { start: e.target.value })
                      }
                    />
                  </Field>
                  <Field label="Tugashi">
                    <Input
                      type="time"
                      value={brk.end}
                      onChange={(e) => setBreak(i, k, { end: e.target.value })}
                    />
                  </Field>
                  <Button
                    variant="ghost"
                    size="icon"
                    aria-label={`${brk.name} tanaffusini o'chirish`}
                    onClick={() =>
                      setShift(i, {
                        breaks: shift.breaks.filter((_, j) => j !== k),
                      })
                    }
                  >
                    <Trash2 />
                  </Button>
                </div>
              ))}
              <div className="flex flex-wrap items-center justify-between gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={shift.breaks.length >= MAX_BREAKS}
                  onClick={() =>
                    setShift(i, {
                      breaks: [
                        ...shift.breaks,
                        { name: "Tanaffus", start: "12:00", end: "13:00" },
                      ],
                    })
                  }
                >
                  <Plus /> Tanaffus qo'shish
                </Button>
                {shift.start && shift.end && (
                  <span className="text-sm text-muted-foreground">
                    Sof ish vaqti: <b className="num">{netWork(shift)}</b>
                  </span>
                )}
              </div>
            </div>
          </div>
        ))}
        <Button
          variant="outline"
          disabled={draft.shifts.length >= MAX_SHIFTS}
          onClick={() =>
            setDraft((d) => ({
              ...d,
              shifts: [
                ...d.shifts,
                // Keyingi smena oldingisi tugagan joydan boshlanadi — aks holda
                // ikkinchi smena birinchisi bilan ustma-ust tushib, darhol xato berardi
                {
                  name: `${d.shifts.length + 1}-smena`,
                  start: d.shifts[d.shifts.length - 1]?.end ?? "08:00",
                  end: plusHours(
                    d.shifts[d.shifts.length - 1]?.end ?? "08:00",
                    d.shifts.length ? 8 : 9,
                  ),
                  breaks: [],
                },
              ],
            }))
          }
        >
          <Plus /> Smena qo'shish
        </Button>
      </section>

      <section className="space-y-3">
        <h3 className="font-medium">Haftalik dam olish kunlari</h3>
        <div className="flex flex-wrap gap-2">
          {WEEKDAYS.map((label, idx) => {
            const day = idx + 1
            const off = draft.days_off.includes(day)
            return (
              <Button
                key={day}
                size="sm"
                variant={off ? "default" : "outline"}
                aria-pressed={off}
                onClick={() => toggleDay(day)}
              >
                {label}
              </Button>
            )
          })}
        </div>
      </section>

      <section className="space-y-3">
        <h3 className="font-medium">Bayram va ishlanmaydigan kunlar</h3>
        <div className="grid grid-cols-1 items-end gap-2 sm:grid-cols-[12rem_1fr_auto]">
          <Field label="Sana">
            <DatePicker value={newDay} onChange={setNewDay} />
          </Field>
          <Field label="Nomi (ixtiyoriy)">
            <Input
              value={newName}
              maxLength={60}
              placeholder="Navro'z"
              onChange={(e) => setNewName(e.target.value)}
            />
          </Field>
          <Button
            variant="outline"
            disabled={!newDay || draft.holidays.some((h) => h.day === newDay)}
            onClick={addHoliday}
          >
            <Plus /> Qo'shish
          </Button>
        </div>
        {draft.holidays.length === 0 ? (
          <p className="text-sm text-muted-foreground">Sana kiritilmagan.</p>
        ) : (
          <ul className="divide-y rounded-lg border">
            {draft.holidays.map((h) => (
              <li
                key={h.day}
                className="flex items-center justify-between gap-2 px-3 py-1.5"
              >
                <span>
                  <span className="num font-medium">{formatDate(h.day)}</span>
                  {h.name && (
                    <span className="text-muted-foreground"> — {h.name}</span>
                  )}
                </span>
                <Button
                  variant="ghost"
                  size="icon-sm"
                  aria-label={`${formatDate(h.day)} sanasini o'chirish`}
                  onClick={() =>
                    setDraft((d) => ({
                      ...d,
                      holidays: d.holidays.filter((x) => x.day !== h.day),
                    }))
                  }
                >
                  <Trash2 />
                </Button>
              </li>
            ))}
          </ul>
        )}
      </section>

      <div className="flex flex-wrap items-center gap-3">
        <LoadingButton
          loading={mutation.isPending}
          disabled={!changed || incomplete}
          onClick={() => mutation.mutate()}
        >
          Saqlash
        </LoadingButton>
        {incomplete && (
          <span className="text-sm text-destructive">
            Har smena va tanaffusning nomi va vaqti to'ldirilsin.
          </span>
        )}
      </div>
    </div>
  )
}
