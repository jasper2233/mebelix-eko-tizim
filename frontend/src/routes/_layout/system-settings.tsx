// Tizim sozlamalari: ish vaqtida admin o'zgartiradigan qiymatlar — nostandart
// detal belgisi, harakatsizlikdan keyin chiqish chegarasi va ish jadvali (smenalar,
// tanaffuslar, dam olish kunlari; OEE reja vaqti shundan hisoblanadi).

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { Plus, Trash2 } from "lucide-react"
import { useEffect, useState } from "react"

import {
  type Holiday,
  SettingsService,
  type SystemSettingRead,
  type WorkBreak,
  type WorkSchedule,
  type WorkShift,
} from "@/client"
import { Field } from "@/components/Common/Field"
import { PageHeader } from "@/components/Common/PageHeader"
import { QueryError } from "@/components/Common/QueryError"
import { Button } from "@/components/ui/button"
import { cardSurface } from "@/components/ui/card"
import { DatePicker } from "@/components/ui/date-picker"
import { Input } from "@/components/ui/input"
import { LoadingButton } from "@/components/ui/loading-button"
import { Skeleton } from "@/components/ui/skeleton"
import { requireAccess } from "@/lib/guards"
import { formatDate, isAdmin } from "@/lib/mes"
import { cn } from "@/lib/utils"
import { crudCallbacks } from "@/queries/mes"

export const Route = createFileRoute("/_layout/system-settings")({
  component: SystemSettingsPage,
  // `lib/mes` dagi `isAdmin` izohi shu sahifani nomma-nom sanab o'tadi
  beforeLoad: requireAccess(isAdmin),
  head: () => ({ meta: [{ title: "Tizim sozlamalari | MebeliX" }] }),
})

const SUFFIX_KEY = "custom_part_suffix"
// Backend `settings_service.IDLE_*` va `IDLE_MINUTES_RANGE` bilan bir xil
const IDLE_OPERATOR_KEY = "idle_logout_operator_minutes"
const IDLE_STAFF_KEY = "idle_logout_staff_minutes"
const IDLE_MIN = 10
const IDLE_MAX = 1440

function SystemSettingsPage() {
  const queryClient = useQueryClient()
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["system-settings"],
    queryFn: async () => (await SettingsService.readSystemSettings()).data,
  })
  const saqlangan = data?.find((s) => s.key === SUFFIX_KEY)?.value ?? ""
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
    <div>
      <PageHeader
        title="Tizim sozlamalari"
        description="Ish vaqtida o'zgaradigan qiymatlar — konteynerni qayta ishga tushirish shart emas."
      />
      {isLoading ? (
        <Skeleton className="h-32 w-full max-w-xl" />
      ) : isError ? (
        <QueryError onRetry={() => refetch()} />
      ) : (
        <div className="max-w-xl space-y-4 rounded-lg border bg-card p-4">
          <Field label="Nostandart detal belgisi">
            <Input
              value={suffix}
              maxLength={8}
              placeholder="#"
              onChange={(e) => setSuffix(e.target.value)}
            />
          </Field>
          <p className="text-sm text-muted-foreground">
            Bazisda detal nomi shu belgi bilan tugasa, u yuklashda{" "}
            <b>nostandart</b> deb belgilanadi va fayldan avtomatik marshrut
            olmaydi — marshrutini texnolog «Nostandart detallar» tabida chizadi.
            Belgi detal nomida qoladi, ya'ni chekda ham ko'rinadi. Qo'lda
            belgilash o'z joyida: matritsadagi «Nostandart» ustuni.
          </p>
          <p className="text-sm text-muted-foreground">
            Bo'sh qoldirilsa qoida <b>o'chadi</b> — hech bir detal avtomatik
            belgilanmaydi. Qoida faqat YANGI yuklashda ishlaydi, mavjud
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
      )}
      {data && <IdleLogoutCard settings={data} />}
      <WorkScheduleCard />
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
    <div className={cn(cardSurface, "mt-6 max-w-xl space-y-4 p-4")}>
      <div>
        <h2 className="text-lg font-semibold">
          Harakatsizlikdan keyin chiqish
        </h2>
        <p className="text-sm text-muted-foreground">
          Shuncha daqiqa hech narsa bosilmasa, ekran login sahifasiga qaytadi
          (tsexda smena ham yopiladi). Terminalda stanok skaneridan kelgan skan
          ham harakat hisoblanadi. Beyjikli postda qayta kirish — beyjikni
          skanerlash. Tsex — terminal va operator hisoblari; ofis — admin,
          direktor, menejer, texnolog.
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

function netWork(shift: Shift): string {
  const total =
    span(shift.start, shift.end) -
    shift.breaks.reduce((sum, b) => sum + span(b.start, b.end), 0)
  return `${Math.floor(total / 60)} soat ${total % 60} daqiqa`
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

  if (isLoading) return <Skeleton className="h-64 w-full max-w-3xl" />
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
    <div className={cn(cardSurface, "mt-6 max-w-3xl space-y-6 p-4")}>
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
