// Stanok sozlamalari — OEE va o'lchov hukmini belgilaydigan kartalar. Ikki joyda
// ko'rsatiladi: Tizim sozlamalari sahifasida (mavzu bo'yicha tablar) va Ish markazlari
// jadvalida stanok nomi bosilganda chiqadigan oynada (`MachineSettingsDialog`) — tsexda
// odam stanokdan izlaydi, sozlamalar sahifasidan emas.
//
// DIQQAT: qiymatlar GLOBAL (`system_setting`), ya'ni bitta stanokniki emas — o'zgartirish
// o'sha TURDAGI hamma stanokka tegadi. Oynada shu haqda qator turadi.

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useEffect, useState } from "react"

import {
  type IdealCycle,
  MachinesService,
  SettingsService,
  type SystemSettingRead,
} from "@/client"
import { Field } from "@/components/Common/Field"
import { QueryError } from "@/components/Common/QueryError"
import { cardSurface } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { LoadingButton } from "@/components/ui/loading-button"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { formatDateTime } from "@/lib/mes"
import { cn } from "@/lib/utils"
import { crudCallbacks } from "@/queries/mes"

//: Kromka bo'sh yurishi va to'xtash chegarasining pastki qiymati (`INT_RANGES`)
const KROMKA_IDLE_MIN = 1

// Backend `settings_service.KROMKA_IDLE_MINUTES` va `INT_RANGES` bilan bir xil
const KROMKA_IDLE_KEY = "kromka_idle_minutes"
const KROMKA_IDLE_MAX = 240
// Backend `settings_service.KROMKA_TOLERANCE_MM` / `KROMKA_BIND_WINDOW_S` va `INT_RANGES` bilan bir xil
const KROMKA_TOL_KEY = "kromka_tolerance_mm"
const KROMKA_TOL_MAX = 50
const KROMKA_BIND_KEY = "kromka_bind_window_s"
// Kirishdan OLDINGI qism (2026-10-16); yuqoridagisi — KEYINGI qism
const KROMKA_BEFORE_KEY = "kromka_bind_before_s"
const KROMKA_BIND_MIN = 5
const KROMKA_BIND_MAX = 600
// Backend `settings_service.KROMKA_SHORT_MM` / `KROMKA_FILLER_MM` va `INT_RANGES` bilan bir xil
const KROMKA_SHORT_KEY = "kromka_short_mm"
const KROMKA_FILLER_KEY = "kromka_filler_mm"
const KROMKA_PAKET_MAX = 500

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
export function IdealCycleCard() {
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

/** Kromka o'lchovining DOPUSKI va skanga bog'lash oynasi
 *  (`backend/app/services/kromka.py`). Ikkalasi ham brak qachon e'lon qilinishini
 *  hal qiladi, shuning uchun brak sabablari bilan bitta tabda. */
export function KromkaBindCard({
  settings,
}: {
  settings: SystemSettingRead[]
}) {
  const queryClient = useQueryClient()
  const savedTol = settings.find((x) => x.key === KROMKA_TOL_KEY)?.value ?? ""
  const savedBind = settings.find((x) => x.key === KROMKA_BIND_KEY)?.value ?? ""
  const savedBefore =
    settings.find((x) => x.key === KROMKA_BEFORE_KEY)?.value ?? ""
  const savedShort =
    settings.find((x) => x.key === KROMKA_SHORT_KEY)?.value ?? ""
  const savedFiller =
    settings.find((x) => x.key === KROMKA_FILLER_KEY)?.value ?? ""
  const [tol, setTol] = useState("")
  const [bind, setBind] = useState("")
  const [before, setBefore] = useState("")
  const [short, setShort] = useState("")
  const [filler, setFiller] = useState("")
  useEffect(() => setTol(savedTol), [savedTol])
  useEffect(() => setBind(savedBind), [savedBind])
  useEffect(() => setBefore(savedBefore), [savedBefore])
  useEffect(() => setShort(savedShort), [savedShort])
  useEffect(() => setFiller(savedFiller), [savedFiller])
  const ok = (v: string, min: number, max: number) =>
    /^\d+$/.test(v) && Number(v) >= min && Number(v) <= max
  const saqla = (key: string, value: string) =>
    SettingsService.updateSystemSetting({ path: { key }, body: { value } })
  const saveTol = useMutation({
    mutationFn: () => saqla(KROMKA_TOL_KEY, tol),
    ...crudCallbacks(queryClient, ["system-settings"], "Sozlama saqlandi"),
  })
  const saveBind = useMutation({
    mutationFn: async () => {
      if (before !== savedBefore) await saqla(KROMKA_BEFORE_KEY, before)
      if (bind !== savedBind) await saqla(KROMKA_BIND_KEY, bind)
    },
    ...crudCallbacks(queryClient, ["system-settings"], "Sozlama saqlandi"),
  })
  const savePaket = useMutation({
    mutationFn: async () => {
      if (short !== savedShort) await saqla(KROMKA_SHORT_KEY, short)
      if (filler !== savedFiller) await saqla(KROMKA_FILLER_KEY, filler)
    },
    ...crudCallbacks(queryClient, ["system-settings"], "Sozlama saqlandi"),
  })
  const bindOk =
    ok(bind, KROMKA_BIND_MIN, KROMKA_BIND_MAX) &&
    ok(before, KROMKA_BIND_MIN, KROMKA_BIND_MAX)
  const paketOk =
    ok(short, 0, KROMKA_PAKET_MAX) && ok(filler, 0, KROMKA_PAKET_MAX)

  return (
    <div className={cn(cardSurface, "space-y-5 p-4")}>
      <div>
        <h2 className="text-lg font-semibold">Kromka o'lchovi</h2>
        <p className="text-sm text-muted-foreground">
          Stansiya o'lchagan uzunlik detalning kutilgan tomoni bilan
          solishtiriladi. Tomonlar <b>guruh</b> bo'yicha sanaladi (uzunlik va
          eni), tartib ahamiyatsiz: operator qaysi tomonni oldin qo'ysa, o'sha
          guruhdan bitta joy yopiladi. Mos kelmasa faqat ko'rsatiladi — brak deb
          belgilanmaydi (datchik ishonchsiz, docs/12 §4.10); brakni operator
          BRAK tugmasi bilan yozadi.
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
        <Field label="Kirishdan oldin, s">
          <Input
            type="number"
            inputMode="numeric"
            min={KROMKA_BIND_MIN}
            max={KROMKA_BIND_MAX}
            value={before}
            aria-invalid={!ok(before, KROMKA_BIND_MIN, KROMKA_BIND_MAX)}
            className="w-32"
            onChange={(e) => setBefore(e.target.value)}
          />
        </Field>
        <Field label="Kirishdan keyin, s">
          <Input
            type="number"
            inputMode="numeric"
            min={KROMKA_BIND_MIN}
            max={KROMKA_BIND_MAX}
            value={bind}
            aria-invalid={!ok(bind, KROMKA_BIND_MIN, KROMKA_BIND_MAX)}
            className="w-32"
            onChange={(e) => setBind(e.target.value)}
          />
        </Field>
        <LoadingButton
          loading={saveBind.isPending}
          disabled={!bindOk || (bind === savedBind && before === savedBefore)}
          onClick={() => saveBind.mutate()}
        >
          Saqlash
        </LoadingButton>
      </div>
      <p className="text-sm text-muted-foreground">
        Detal birinchi datchikka <b>kirgan lahza</b> hisoblanadi (o'lchov
        vaqtidan datchiklar orasidagi yurish va detalning ikkinchi datchikdan
        o'tish vaqti ayiriladi). Shu lahzadan «oldin» va «keyin» oralig'idagi
        skanlar nomzod bo'ladi — operator odatda detalni lentaga qo'yishdan
        oldin, ba'zan bir necha detal oldindan skanerlaydi (stansiya egasining
        tavsiyasi: 60 s oldin, 20 s keyin). Ular orasidan o'lchamga mos va
        qirrasi hali yopilmagan ENG ESKI skan tanlanadi. Oxirgi skanga bog'lash
        XATO berardi: detal datchiklar orasida 8–15 soniya yuradi, operator esa
        4–10 soniyada bir marta skanerlaydi — o'lchov keyingi detalga yopishib
        qolardi. Skan topilmasa o'lchov «skansiz» bo'lib yoziladi va hech kimni
        ayblamaydi. Oraliq: {KROMKA_BIND_MIN}–{KROMKA_BIND_MAX}.
      </p>
      <div className="flex items-end gap-3">
        <Field label="Kichik detal, mm dan kichik">
          <Input
            type="number"
            inputMode="numeric"
            min={0}
            max={KROMKA_PAKET_MAX}
            value={short}
            aria-invalid={!ok(short, 0, KROMKA_PAKET_MAX)}
            className="w-44"
            onChange={(e) => setShort(e.target.value)}
          />
        </Field>
        <Field label="To'ldiruvchi bo'lak, mm">
          <Input
            type="number"
            inputMode="numeric"
            min={0}
            max={KROMKA_PAKET_MAX}
            value={filler}
            aria-invalid={!ok(filler, 0, KROMKA_PAKET_MAX)}
            className="w-44"
            onChange={(e) => setFiller(e.target.value)}
          />
        </Field>
        <LoadingButton
          loading={savePaket.isPending}
          disabled={
            !paketOk || (short === savedShort && filler === savedFiller)
          }
          onClick={() => savePaket.mutate()}
        >
          Saqlash
        </LoadingButton>
      </div>
      <p className="text-sm text-muted-foreground">
        <b>Paket.</b> Shu chegaradan <b>kichik</b> detal lentada qaltiraydi,
        shuning uchun 4 tagacha detal zich tiqilib birga o'tkaziladi; yolg'iz
        qolsa ustiga to'ldiruvchi bo'lak qo'shiladi. Chegaraning O'ZI (sukut
        bo'yicha 150 mm) yakka o'tadi va paketga qo'shilmaydi. Stansiya paketni
        BITTA detal deb o'lchaydi — uzunlik yig'indi bo'ladi. MES yig'indini
        oynadagi skanerlangan kichik qirralardan qidiradi va aynan bitta javob
        chiqsa har qirrani yopadi; chiqmasa o'lchov «shubhali» bo'lib qoladi va
        brak so'ralmaydi. Operator tartibi:{" "}
        <b>har bir detalni skanerla → paketni o'tkaz</b>. To'ldiruvchi
        skanerlanmaydi, shuning uchun uzunligi har safar AYNAN shu bo'lishi
        kerak (markerlab, stanok yonida saqlanadi). Nol — qoida o'chadi.
      </p>
    </div>
  )
}

/** Kromka bo'sh yurishi: lenta yuryapti, lekin detal o'tmayapti — RUN kirishi buni
 *  aytmaydi, o'lchovlar orasidagi tirqish aytadi (`services/andon.split_idle`). */
export function KromkaIdleCard({
  settings,
}: {
  settings: SystemSettingRead[]
}) {
  const queryClient = useQueryClient()
  const saved = settings.find((s) => s.key === KROMKA_IDLE_KEY)?.value ?? ""
  const [idle, setIdle] = useState("")
  useEffect(() => setIdle(saved), [saved])
  const valid =
    /^\d+$/.test(idle) &&
    Number(idle) >= KROMKA_IDLE_MIN &&
    Number(idle) <= KROMKA_IDLE_MAX
  const save = useMutation({
    mutationFn: () =>
      SettingsService.updateSystemSetting({
        path: { key: KROMKA_IDLE_KEY },
        body: { value: idle },
      }),
    ...crudCallbacks(queryClient, ["system-settings"], "Sozlama saqlandi"),
  })

  return (
    <div className={cn(cardSurface, "space-y-4 p-4")}>
      <div>
        <h2 className="text-lg font-semibold">Kromka bo'sh yurishi</h2>
        <p className="text-sm text-muted-foreground">
          Kromkada IKKINCHI to'xtash holati bor: lenta yuryapti, lekin detal
          o'tmayapti. RUN kirishi buni aytmaydi — o'lchovlar orasidagi tirqish
          aytadi.
        </p>
      </div>
      <div className="flex items-end gap-3">
        <Field label="Detal o'tmasa, daqiqa">
          <Input
            type="number"
            inputMode="numeric"
            min={KROMKA_IDLE_MIN}
            max={KROMKA_IDLE_MAX}
            value={idle}
            aria-invalid={!valid}
            onChange={(e) => setIdle(e.target.value)}
            className="w-40"
          />
        </Field>
        <LoadingButton
          loading={save.isPending}
          disabled={!valid || idle === saved}
          onClick={() => save.mutate()}
        >
          Saqlash
        </LoadingButton>
      </div>
      <p className="text-sm text-muted-foreground">
        Lenta yuryapti-yu, shuncha daqiqa bitta ham detal o'tmasa — bu ham
        to'xtash (material yo'q, buyurtma yo'q, operator ketgan): sabab
        so'raladi va o'sha vaqt «ishladi» dan chiqadi. To'xtash chegarasidan
        uzunroq bo'lgani ma'qul — detal almashtirish ritmi jazolanmasin. Oraliq:{" "}
        {KROMKA_IDLE_MIN}–{KROMKA_IDLE_MAX}.
      </p>
    </div>
  )
}

/** Kromka ideal sikli. Prisadkadan FARQI: u yerda beshta taxminiy koeffitsiyent bor,
 *  bu yerda esa ideal vaqtni lenta belgilaydi va uzunlikni stansiya O'LCHAYDI —
 *  sozlanadigan yagona narsa detallar orasidagi bo'shliq
 *  (`backend/app/services/performance.py: kromka_ideal_seconds`). */
export function KromkaCycleCard() {
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
export function RoverCycleCard() {
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

// Pico `KAL` kalitlari (kromka-stansiya-OYY: pico/main.py) — birligi va ma'nosi
const KAL_FIELDS: { key: string; label: string; unit: string }[] = [
  { key: "D", label: "D — datchiklar orasi", unit: "mm" },
  { key: "V10", label: "V10 — 10 m/min tezlik", unit: "m/min" },
  { key: "V18", label: "V18 — 18 m/min tezlik", unit: "m/min" },
  { key: "B1", label: "B1 — 1-datchik siljishi", unit: "mm" },
  { key: "B2", label: "B2 — 2-datchik siljishi", unit: "mm" },
  { key: "K1", label: "K1 — 1-datchik kechikishi", unit: "ms" },
  { key: "K2", label: "K2 — 2-datchik kechikishi", unit: "ms" },
  { key: "C", label: "C — markazlar tuzatmasi", unit: "ms" },
  { key: "TD", label: "TD — datchiklar farqi chegarasi", unit: "mm" },
  { key: "AO", label: "AO — avariya lampasi o'chiq", unit: "" },
]

/** Kromka Pico'sidagi JORIY kalibrlash — faqat o'qish (docs/12 §4.18, 1-qadam). Agent 1.11.0
 *  `HOLAT` javobidan qiymatlar o'zgarganda yuboradi; eski agentli stanokda «hali kelmagan». */
export function KromkaKalCard({ machineId }: { machineId?: number }) {
  const {
    data: hammasi,
    isLoading,
    isError,
    refetch,
  } = useQuery({
    queryKey: ["system-settings", "kromka-calibration"],
    queryFn: async () => (await MachinesService.readKromkaCalibration()).data,
  })
  if (isLoading) return <Skeleton className="h-48 w-full" />
  if (isError || !hammasi) return <QueryError onRetry={() => refetch()} />
  // Stanok oynasida faqat o'sha stanokning ustuni; sozlamalar sahifasida hammasi
  const data =
    machineId == null
      ? hammasi
      : hammasi.filter((m) => m.machine_id === machineId)

  return (
    <div className={cn(cardSurface, "space-y-4 p-4")}>
      <div>
        <h2 className="text-lg font-semibold">Pico'dagi kalibrlash</h2>
        <p className="text-sm text-muted-foreground">
          Kromka stansiyasi Pico'sining hozirgi o'lchash parametrlari — Pico
          o'zi aytgan qiymatlar (har ulanishda va o'zgarganda yangilanadi).
          Yangi qiymatlar quyidagi «Kalibrlash sessiyasi» dan qo'llanadi.
        </p>
      </div>
      {data.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          Kromka ish markazi yo'q.
        </p>
      ) : (
        <div className="overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Parametr</TableHead>
                {data.map((m) => (
                  <TableHead key={m.machine_id} className="text-right">
                    {m.machine_name}
                  </TableHead>
                ))}
              </TableRow>
            </TableHeader>
            <TableBody>
              {KAL_FIELDS.map((f) => (
                <TableRow key={f.key}>
                  <TableCell>
                    {f.label}
                    {f.unit && (
                      <span className="text-muted-foreground"> · {f.unit}</span>
                    )}
                  </TableCell>
                  {data.map((m) => (
                    <TableCell key={m.machine_id} className="num text-right">
                      {m.values[f.key] ?? "—"}
                    </TableCell>
                  ))}
                </TableRow>
              ))}
              <TableRow>
                <TableCell className="text-muted-foreground">
                  Proshivka · yangilangan
                </TableCell>
                {data.map((m) => (
                  <TableCell
                    key={m.machine_id}
                    className="text-right text-muted-foreground"
                  >
                    {m.at
                      ? `v${m.ver ?? "?"} · ${formatDateTime(m.at)}`
                      : "hali kelmagan (agent 1.11.0 kerak)"}
                  </TableCell>
                ))}
              </TableRow>
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  )
}
