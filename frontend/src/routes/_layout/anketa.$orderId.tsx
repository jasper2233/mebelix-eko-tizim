import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute, Link } from "@tanstack/react-router"
import { ArrowLeft, Plus, Save, Trash2, X } from "lucide-react"
import { useEffect, useRef, useState } from "react"

import {
  type OrderSurvey,
  OrdersService,
  type SurveyModule,
  type SurveyRoom,
} from "@/client"
import {
  CheckCard,
  CheckGrid,
  Choice,
  Field,
  Num,
  NumInput,
  Section,
  ShapeChoice,
} from "@/components/Anketa/fields"
import { RoomPhotos } from "@/components/Anketa/RoomPhotos"
import { RoomSummary } from "@/components/Anketa/RoomSummary"
import { ConfirmDialog } from "@/components/Common/ConfirmDialog"
import { PageHeader } from "@/components/Common/PageHeader"
import { QueryError } from "@/components/Common/QueryError"
import { Button } from "@/components/ui/button"
import { cardSurface } from "@/components/ui/card"
import { DatePicker } from "@/components/ui/date-picker"
import { Input } from "@/components/ui/input"
import { LoadingButton } from "@/components/ui/loading-button"
import { Skeleton } from "@/components/ui/skeleton"
import { Textarea } from "@/components/ui/textarea"
import { useCurrentUser } from "@/hooks/useCurrentUser"
import {
  CORPUS_MATERIALS,
  CORPUS_THICKNESS,
  COUNTERTOPS,
  EXTRA_SERVICES,
  FACADE_MATERIALS,
  FURNITURE_TYPES,
  HARDWARE_LEVELS,
  MAX_MODULES,
  MAX_ROOMS,
  ORDER_SERVICES,
  WALL_LETTERS,
} from "@/lib/anketa"
import { isManager } from "@/lib/mes"
import { cn } from "@/lib/utils"
import { getOrderQueryOptions } from "@/queries/mes"
import { handleError } from "@/utils"

export const Route = createFileRoute("/_layout/anketa/$orderId")({
  component: AnketaPage,
  head: () => ({ meta: [{ title: "Anketa | MebeliX" }] }),
})

const newRoom = (n: number): SurveyRoom => ({
  id: `r${Date.now()}${n}`,
  name: "", // bo'sh: tab va sarlavha `Xona N` zaxirasini ishlatadi va o'chirishdan keyin o'zi qayta raqamlanadi
  furniture_types: [],
  corpus_materials: [],
  facade_materials: [],
  extra_services: [],
  walls: WALL_LETTERS.map((l) => ({ letter: l })),
  modules: [],
})

function AnketaPage() {
  const { orderId } = Route.useParams()
  const id = Number(orderId)
  const queryClient = useQueryClient()
  const {
    data: order,
    isLoading,
    isError,
    refetch,
  } = useQuery(getOrderQueryOptions(id))
  const { currentUser } = useCurrentUser()

  // Backend ham AYNAN shu shartni qo'yadi (`orders/survey.py` `_editable_order`):
  // yakunlangan/bekor qilingan buyurtmada yozish yo'llari 403 qaytaradi. Shart
  // bu yerda bo'lmasa menejerga to'liq tahrirlanadigan forma ochilib, har
  // avtosaqlash 403 bilan yo'qolardi.
  const readOnlyStatus =
    order?.status === "delivered" || order?.status === "cancelled"
  const canEdit = isManager(currentUser) && !!order && !readOnlyStatus

  const [survey, setSurvey] = useState<OrderSurvey>({ version: 1, rooms: [] })
  const [active, setActive] = useState(0)
  const [dirty, setDirty] = useState(false)
  const [savedAt, setSavedAt] = useState<string | null>(null)
  // Qaysi xona o'chirilmoqda — faol xona emas: pilldagi × istalgan xonani
  // oldindan tanlamasdan o'chira oladi.
  const [removeIdx, setRemoveIdx] = useState<number | null>(null)

  // Serverdan FAQAT BIR MARTA yuklanadi. Aks holda saqlashdan keyingi refetch
  // menejer yozayotgan matn ustiga tushadi.
  const loaded = useRef(false)
  useEffect(() => {
    if (!order || loaded.current) return
    loaded.current = true
    const saved = order.survey as OrderSurvey | null
    if (!saved?.rooms?.length) {
      setSurvey({ version: 1, measured_by: "", rooms: [newRoom(1)] })
      return
    }
    // Eski anketalarda "yetkazish"/"montaj" xona ichidagi extra_services da
    // edi. Ular buyurtma darajasiga ko'chirildi: biror xonada belgilangan
    // bo'lsa — buyurtma bayrog'ini yoqamiz va xona ro'yxatidan olib tashlaymiz.
    // Avtosaqlash keyingi tahrirda yangi shaklni yozadi; ma'lumot yo'qolmaydi.
    const hasLegacy = (code: string) =>
      saved.rooms?.some((r) => (r.extra_services ?? []).includes(code))
    setSurvey({
      ...saved,
      delivery: saved.delivery || hasLegacy("yetkazish"),
      installation: saved.installation || hasLegacy("montaj"),
      rooms: saved.rooms.map((r) => ({
        ...r,
        extra_services: (r.extra_services ?? []).filter(
          (s) => s !== "yetkazish" && s !== "montaj",
        ),
      })),
    })
  }, [order])

  // Avtosaqlash: menejer bilmasdan chiqib ketsa ham ma'lumot yo'qolmaydi.
  // Anketa o'zi qoralama — alohida "chop etish" bosqichi yo'q.
  const surveyRef = useRef(survey)
  surveyRef.current = survey

  const save = useMutation({
    // Bir xil scope'li mutatsiyalar KETMA-KET bajariladi. Debounce taymeri
    // oldingi so'rov hali ketayotganda yangisini boshlashi mumkin; har biri
    // anketaning TO'LIQ nusxasini yuboradi, shuning uchun javoblar tartibi
    // buzilsa eskiroq nusxa serverda oxirgi bo'lib qolardi (jimgina yo'qotish).
    scope: { id: `order-survey-${id}` },
    mutationFn: (body: OrderSurvey) =>
      OrdersService.saveOrderSurvey({ path: { order_id: id }, body }),
    onSuccess: (_data, body) => {
      // Faqat yuborilgan nusxa hali ham joriy bo'lsa "toza" deb belgilaymiz.
      // Aks holda saqlash uchayotganda yozilgan matn dirty=false tufayli
      // kutayotgan taymer bilan birga yo'qolardi (jimgina ma'lumot yo'qotish).
      if (surveyRef.current === body) setDirty(false)
      setSavedAt(
        new Date().toLocaleTimeString("uz-Latn-UZ", { timeStyle: "short" }),
      )
      queryClient.invalidateQueries({ queryKey: ["orders", id] })
    },
    onError: handleError,
  })

  const dirtyRef = useRef(dirty)
  dirtyRef.current = dirty

  // biome-ignore lint/correctness/useExhaustiveDependencies: survey ataylab — har tahrirda taymer qaytadan boshlanadi
  useEffect(() => {
    if (!dirty || !canEdit) return
    const t = setTimeout(() => save.mutate(surveyRef.current), 1500)
    return () => clearTimeout(t)
  }, [survey, dirty, canEdit, save.mutate])

  // Sahifadan chiqishda (1.5s kutmasdan) va tab yopilishida ogohlantirish
  useEffect(() => {
    if (!canEdit) return
    const warn = (e: BeforeUnloadEvent) => {
      if (dirtyRef.current) e.preventDefault()
    }
    window.addEventListener("beforeunload", warn)
    return () => {
      window.removeEventListener("beforeunload", warn)
      if (dirtyRef.current) {
        // fire-and-forget: komponent yo'q bo'lyapti, javob kutilmaydi
        OrdersService.saveOrderSurvey({
          path: { order_id: id },
          body: surveyRef.current,
        }).catch(() => {})
      }
    }
  }, [id, canEdit])

  if (isError)
    return (
      <QueryError
        message="Anketani ochib bo'lmadi."
        onRetry={() => refetch()}
      />
    )
  if (isLoading || !order) return <Skeleton className="h-96 w-full" />

  const rooms = survey.rooms ?? []
  const room = rooms[active]

  // Xona rasmlari OrderFile'da saqlanadi (meta.room_id) — anketa JSON'ida emas,
  // shuning uchun avtosaqlash bilan aralashmaydi
  const photosOf = (roomId: string) =>
    (order.files ?? []).filter(
      (f) => f.kind === "document" && f.meta?.room_id === roomId,
    )

  const patch = (changes: Partial<SurveyRoom>) => {
    setSurvey((s) => ({
      ...s,
      rooms: (s.rooms ?? []).map((r, i) =>
        i === active ? { ...r, ...changes } : r,
      ),
    }))
    setDirty(true)
  }

  // Buyurtma darajasidagi maydonlar (xona ichida emas) — `patch` ning juftligi
  const patchSurvey = (changes: Partial<OrderSurvey>) => {
    setSurvey((s) => ({ ...s, ...changes }))
    setDirty(true)
  }

  const addRoom = () => {
    setSurvey((s) => ({
      ...s,
      rooms: [...(s.rooms ?? []), newRoom((s.rooms?.length ?? 0) + 1)],
    }))
    setActive(rooms.length)
    setDirty(true)
  }

  const removeRoom = (idx: number) => {
    setSurvey((s) => ({
      ...s,
      rooms: (s.rooms ?? []).filter((_, i) => i !== idx),
    }))
    setActive((a) => (a >= idx && a > 0 ? a - 1 : a))
    setDirty(true)
  }

  return (
    <div>
      <Link
        to="/orders/$orderId"
        params={{ orderId }}
        className="mb-3 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="size-4" /> Buyurtma {order.number}
      </Link>
      <PageHeader
        title="Buyurtma anketasi"
        description={`${order.client_name} · har bir xona uchun alohida to'ldiriladi`}
      />
      {readOnlyStatus && (
        <p className="mb-4 text-muted-foreground text-sm">
          Buyurtma yakunlangan yoki bekor qilingan — anketa faqat o'qish uchun.
        </p>
      )}

      <div className="mb-4 flex flex-wrap items-center gap-2">
        {rooms.map((r, i) => {
          const label = r.name || `Xona ${i + 1}`
          // O'chirish pilldagi × da: obyekt va uni o'chirish tugmasi bir joyda
          // (brauzer tablari naqshi). Bitta xona qolganda × yo'q — anketa
          // xonasiz ma'nosiz. Ichma-ich <button> bo'lmasligi uchun pill
          // konteyner div, ichida ikkita alohida tugma.
          const canRemove = canEdit && rooms.length > 1
          return (
            <div
              key={r.id}
              className={`flex items-center rounded-lg border text-sm font-medium transition-colors ${
                i === active
                  ? "border-primary bg-primary text-primary-foreground"
                  : "bg-card hover:border-primary/50"
              }`}
            >
              <button
                type="button"
                onClick={() => setActive(i)}
                className={`rounded-l-lg py-2 pl-4 focus-visible:outline-2 focus-visible:outline-ring focus-visible:outline-offset-2 ${
                  canRemove ? "pr-2" : "rounded-r-lg pr-4"
                }`}
              >
                {label}
              </button>
              {canRemove && (
                <button
                  type="button"
                  aria-label={`${label} — o'chirish`}
                  onClick={() => setRemoveIdx(i)}
                  className="rounded-r-lg py-2 pr-2.5 pl-1 opacity-60 transition-opacity hover:opacity-100 focus-visible:outline-2 focus-visible:outline-ring focus-visible:outline-offset-2"
                >
                  <X className="size-4" />
                </button>
              )}
            </div>
          )
        })}
        {canEdit && (
          <>
            {/* Chegara backend bilan bir xil: oshib ketsa butun anketaning
                avtosaqlashi 422 bilan yiqilardi. */}
            <Button
              variant="outline"
              onClick={addRoom}
              disabled={rooms.length >= MAX_ROOMS}
            >
              <Plus /> Xona qo'shish
            </Button>
            {rooms.length >= MAX_ROOMS && (
              <span className="text-muted-foreground text-xs">
                Eng ko'pi {MAX_ROOMS} xona
              </span>
            )}
          </>
        )}
      </div>

      {/* Buyurtma darajasi: tsex bitta .project fayl ustida ishlaydi va xona
          degan tushunchani ko'rmaydi, logistika ham butun buyurtmani bitta
          mashinada olib ketadi. Shuning uchun bu maydonlar raqamlangan xona
          bo'limlaridan TASHQARIDA — xona almashganda o'zgarmaydi. */}
      {canEdit && (
        <div className={cn(cardSurface, "mb-4 p-4")}>
          <div className="mb-3 font-semibold text-sm">Butun buyurtma uchun</div>
          <div className="grid gap-2 sm:grid-cols-3">
            {ORDER_SERVICES.map((svc) => (
              <CheckCard
                key={svc.key}
                checked={survey[svc.key] ?? false}
                onToggle={() => patchSurvey({ [svc.key]: !survey[svc.key] })}
              >
                {svc.label}
              </CheckCard>
            ))}
          </div>
          <div className="mt-3 grid items-start gap-3 sm:grid-cols-2">
            <Field label="O'lchov sanasi">
              <DatePicker
                value={survey.measured_at ?? ""}
                className="w-full"
                aria-label="O'lchov sanasi"
                onChange={(v) => patchSurvey({ measured_at: v || null })}
              />
            </Field>
            <Field label="O'lchagan usta">
              <Input
                value={survey.measured_by ?? ""}
                maxLength={120}
                onChange={(e) => patchSurvey({ measured_by: e.target.value })}
              />
            </Field>
          </div>
        </div>
      )}

      {/* Texnolog/direktor: forma emas, o'qish uchun jamlanma — matn nusxa olinadi */}
      {room && !canEdit && (
        <RoomSummary
          room={room}
          survey={survey}
          orderId={id}
          photos={photosOf(room.id)}
        />
      )}

      {room && canEdit && (
        <div className="space-y-5">
          {/* Chapda xona nomi, o'ngda rasmlar — menejer nomni yozib, darhol
              mijozning suratini shu yerga tashlaydi */}
          <Section n={1} title="Xona va rasmlar">
            <div className="grid items-start gap-5 lg:grid-cols-[minmax(0,1fr)_minmax(0,26rem)]">
              <div className="space-y-3">
                <Field label="Nomi">
                  {/* Qisqa qiymat ("Oshxona") — butun ustun kengligini egallamasin */}
                  <Input
                    className="max-w-xs"
                    value={room.name ?? ""}
                    maxLength={60}
                    placeholder="Oshxona, Yotoqxona, Mehmonxona…"
                    onChange={(e) => patch({ name: e.target.value })}
                  />
                </Field>
              </div>
              <RoomPhotos
                orderId={id}
                roomId={room.id}
                photos={photosOf(room.id)}
                canEdit
              />
            </div>
          </Section>

          <Section n={2} title="Qanday mebel kerak">
            <CheckGrid
              options={FURNITURE_TYPES}
              values={room.furniture_types ?? []}
              onChange={(v) => patch({ furniture_types: v })}
            />
            <Field label="Boshqa">
              <Input
                value={room.furniture_other ?? ""}
                maxLength={120}
                onChange={(e) => patch({ furniture_other: e.target.value })}
              />
            </Field>
          </Section>

          <Section n={3} title="Xonadagi shakli va o'lchamlari">
            <ShapeChoice
              value={room.shape ?? null}
              onChange={(v) => patch({ shape: v })}
            />
            <div className="grid items-start gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <Num
                label="Xona uzunligi (mm)"
                value={room.room_length}
                onChange={(v) => patch({ room_length: v })}
              />
              <Num
                label="Xona kengligi (mm)"
                value={room.room_width}
                onChange={(v) => patch({ room_width: v })}
              />
              <Num
                label="Xona balandligi (mm)"
                value={room.room_height}
                onChange={(v) => patch({ room_height: v })}
              />
              <Num
                label="Mebel devori uzunligi (mm)"
                value={room.furniture_wall_length}
                onChange={(v) => patch({ furniture_wall_length: v })}
              />
            </div>
          </Section>

          <Section n={4} title="Korpus materiali" hint="mebelning ichki qismi">
            <CheckGrid
              options={CORPUS_MATERIALS}
              values={room.corpus_materials ?? []}
              onChange={(v) => patch({ corpus_materials: v })}
            />
            <div className="grid items-start gap-3 sm:grid-cols-2">
              <Field label="Rang / dekor">
                <Input
                  value={room.corpus_color ?? ""}
                  maxLength={120}
                  onChange={(e) => patch({ corpus_color: e.target.value })}
                />
              </Field>
              <Field label="Qalinligi">
                <Choice
                  options={CORPUS_THICKNESS}
                  value={room.corpus_thickness ?? null}
                  onChange={(v) => patch({ corpus_thickness: v })}
                />
              </Field>
            </div>
            <Field label="Korpus izohi">
              <Input
                value={room.corpus_note ?? ""}
                maxLength={300}
                onChange={(e) => patch({ corpus_note: e.target.value })}
              />
            </Field>
          </Section>

          <Section n={5} title="Fasad materiali" hint="old eshik va tortmalar">
            <CheckGrid
              options={FACADE_MATERIALS}
              values={room.facade_materials ?? []}
              onChange={(v) => patch({ facade_materials: v })}
            />
            <div className="grid items-start gap-3 sm:grid-cols-2">
              <Field label="Rang / tekstura">
                <Input
                  value={room.facade_color ?? ""}
                  maxLength={120}
                  onChange={(e) => patch({ facade_color: e.target.value })}
                />
              </Field>
              <Field label="Stol usti">
                <Choice
                  options={COUNTERTOPS}
                  value={room.countertop ?? null}
                  onChange={(v) => patch({ countertop: v })}
                />
              </Field>
            </div>
            <Field label="Fasad izohi">
              <Input
                value={room.facade_note ?? ""}
                maxLength={300}
                onChange={(e) => patch({ facade_note: e.target.value })}
              />
            </Field>
          </Section>

          <Section n={6} title="Furnitura va qo'shimcha xizmat">
            <Field label="Furnitura darajasi">
              <Choice
                options={HARDWARE_LEVELS}
                value={room.hardware_level ?? null}
                onChange={(v) => patch({ hardware_level: v })}
              />
            </Field>
            <div>
              <CheckGrid
                options={EXTRA_SERVICES}
                values={room.extra_services ?? []}
                onChange={(v) => patch({ extra_services: v })}
              />
            </div>
          </Section>

          <Section n={7} title="Qo'shimcha izoh">
            <Textarea
              rows={3}
              value={room.note ?? ""}
              maxLength={1000}
              placeholder="Mijozning qo'shimcha talab va izohlari"
              onChange={(e) => patch({ note: e.target.value })}
            />
          </Section>

          {/* O'lchov varag'i — zamerdan keyin to'ldiriladi, shuning uchun yopiq turadi */}
          <details className={cardSurface}>
            <summary className="cursor-pointer px-4 py-3 font-semibold">
              <span className="mr-2 text-muted-foreground">8</span>
              O'lchov varag'i{" "}
              <span className="font-normal text-muted-foreground text-sm">
                (usta to'ldiradi)
              </span>
            </summary>
            <div className="space-y-5 border-t p-4">
              {/* O'lchov sanasi/ustasi bu yerda EMAS: ular butun buyurtmaga
                  tegishli va yuqoridagi "Butun buyurtma uchun" blokida.
                  Avval shu xona bo'limida turgani uchun menejer 3-xonada
                  turib o'zgartirsa, jimgina butun buyurtma uchun o'zgarardi. */}
              <div>
                <div className="mb-2 font-medium text-sm">
                  Devor o'lchamlari (mm) — A dan soat yo'nalishi bo'yicha
                </div>
                <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                  {WALL_LETTERS.map((letter, wi) => {
                    const w = (room.walls ?? [])[wi] ?? { letter }
                    const setWall = (
                      k: "length" | "height",
                      v: number | null,
                    ) =>
                      patch({
                        walls: WALL_LETTERS.map((l, i) =>
                          i === wi
                            ? { ...w, letter: l, [k]: v }
                            : ((room.walls ?? [])[i] ?? { letter: l }),
                        ),
                      })
                    return (
                      <div
                        key={letter}
                        className="flex items-center gap-2 rounded-lg border p-2"
                      >
                        <span className="w-6 shrink-0 text-center font-bold text-primary">
                          {letter}
                        </span>
                        <span className="shrink-0 text-muted-foreground text-xs">
                          uz
                        </span>
                        <NumInput
                          value={w.length}
                          onChange={(v) => setWall("length", v)}
                          aria-label={`${letter} devor — uzunligi (mm)`}
                        />
                        <span className="shrink-0 text-muted-foreground text-xs">
                          bal
                        </span>
                        <NumInput
                          value={w.height}
                          onChange={(v) => setWall("height", v)}
                          aria-label={`${letter} devor — balandligi (mm)`}
                        />
                      </div>
                    )
                  })}
                </div>
              </div>

              <div>
                <div className="mb-2 font-medium text-sm">
                  Yasaladigan mebel o'lchamlari
                </div>
                <div className="overflow-x-auto">
                  {/* biome-ignore lint/correctness/noRestrictedElements: anketa jadvali reyestr emas — kataklarida kiritish maydonlari turadi, o'z ustun kengliklari bilan */}
                  <table className="w-full min-w-[720px] border-collapse text-sm">
                    <thead>
                      <tr className="border-b text-left text-muted-foreground text-xs font-semibold uppercase tracking-wider">
                        <th className="w-8 py-2">№</th>
                        <th className="py-2">Modul / bo'lim</th>
                        <th className="w-20 py-2">Devor</th>
                        <th className="w-24 py-2">Eni (mm)</th>
                        <th className="w-24 py-2">Chuqurlik (mm)</th>
                        <th className="w-24 py-2">Balandlik (mm)</th>
                        <th className="w-16 py-2">Soni</th>
                        <th className="py-2">Izoh</th>
                        <th className="w-10 py-2" />
                      </tr>
                    </thead>
                    <tbody>
                      {(room.modules ?? []).map((m, mi) => {
                        const setMod = (changes: Partial<SurveyModule>) =>
                          patch({
                            modules: (room.modules ?? []).map((x, i) =>
                              i === mi ? { ...x, ...changes } : x,
                            ),
                          })
                        return (
                          <tr key={mi} className="border-b">
                            <td className="py-1 text-muted-foreground">
                              {mi + 1}
                            </td>
                            <td className="py-1 pr-1">
                              <Input
                                value={m.name ?? ""}
                                maxLength={120}
                                onChange={(e) =>
                                  setMod({ name: e.target.value })
                                }
                              />
                            </td>
                            <td className="py-1 pr-1">
                              <Input
                                value={m.wall ?? ""}
                                maxLength={2}
                                onChange={(e) =>
                                  setMod({ wall: e.target.value })
                                }
                              />
                            </td>
                            <td className="py-1 pr-1">
                              <NumInput
                                value={m.width}
                                integer={true}
                                onChange={(v) => setMod({ width: v })}
                                aria-label={`${mi + 1}-modul — eni (mm)`}
                              />
                            </td>
                            <td className="py-1 pr-1">
                              <NumInput
                                value={m.depth}
                                integer={true}
                                onChange={(v) => setMod({ depth: v })}
                                aria-label={`${mi + 1}-modul — chuqurligi (mm)`}
                              />
                            </td>
                            <td className="py-1 pr-1">
                              <NumInput
                                value={m.height}
                                integer={true}
                                onChange={(v) => setMod({ height: v })}
                                aria-label={`${mi + 1}-modul — balandligi (mm)`}
                              />
                            </td>
                            <td className="py-1 pr-1">
                              <NumInput
                                value={m.count}
                                integer={true}
                                onChange={(v) => setMod({ count: v })}
                                aria-label={`${mi + 1}-modul — soni`}
                              />
                            </td>
                            <td className="py-1 pr-1">
                              <Input
                                value={m.note ?? ""}
                                maxLength={200}
                                onChange={(e) =>
                                  setMod({ note: e.target.value })
                                }
                              />
                            </td>
                            <td className="py-1">
                              <Button
                                variant="ghost"
                                size="icon"
                                className="text-destructive"
                                aria-label={`${m.name || `${mi + 1}-modul`} — o'chirish`}
                                onClick={() =>
                                  patch({
                                    modules: (room.modules ?? []).filter(
                                      (_, i) => i !== mi,
                                    ),
                                  })
                                }
                              >
                                <Trash2 />
                              </Button>
                            </td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                </div>
                <div className="mt-2 flex items-center gap-2">
                  <Button
                    variant="outline"
                    disabled={(room.modules ?? []).length >= MAX_MODULES}
                    onClick={() =>
                      patch({
                        modules: [...(room.modules ?? []), { name: "" }],
                      })
                    }
                  >
                    <Plus /> Qator qo'shish
                  </Button>
                  {(room.modules ?? []).length >= MAX_MODULES && (
                    <span className="text-muted-foreground text-xs">
                      Eng ko'pi {MAX_MODULES} modul
                    </span>
                  )}
                </div>
                <div className="grid items-start gap-3 sm:grid-cols-2">
                  <Num
                    label="Umumiy uzunlik (pm)"
                    value={room.total_running_meters}
                    onChange={(v) => patch({ total_running_meters: v })}
                  />
                  <Num
                    label="Umumiy balandlik (mm)"
                    value={room.total_height}
                    onChange={(v) => patch({ total_height: v })}
                  />
                </div>
              </div>
            </div>
          </details>
        </div>
      )}

      {/* Xona o'chirish qaytarilmaydi: avtosaqlash 1.5s da serverga yozadi va
          backend shu xonaning rasmlarini diskdan ham o'chiradi */}
      <ConfirmDialog
        open={removeIdx !== null}
        onOpenChange={(open) => !open && setRemoveIdx(null)}
        title={`${(removeIdx !== null && rooms[removeIdx]?.name) || `Xona ${(removeIdx ?? 0) + 1}`} o'chirilsinmi?`}
        description="Shu xonaning materiali, o'lchamlari, modullari va rasmlari o'chadi. Qaytarib bo'lmaydi."
        confirmText="O'chirish"
        destructive
        onConfirm={() => {
          if (removeIdx !== null) removeRoom(removeIdx)
          setRemoveIdx(null)
        }}
      />

      {/* Saqlash paneli — sahifa uzun, tugma doim ko'rinib tursin.
          sticky (fixed emas): sidebar ustiga chiqmaydi, main padding'ini teskari margin bilan qoplaydi */}
      {canEdit && (
        <div className="-mx-6 md:-mx-8 -mb-6 md:-mb-8 sticky bottom-0 z-10 mt-5 border-t bg-background/95 px-6 py-3 backdrop-blur md:px-8">
          <div className="flex items-center justify-end gap-3">
            <span
              className={cn(
                "text-sm",
                save.isError
                  ? "font-medium text-destructive"
                  : "text-muted-foreground",
              )}
              role={save.isError ? "alert" : undefined}
            >
              {save.isPending
                ? "Saqlanmoqda..."
                : save.isError
                  ? "Saqlanmadi — qayta urinib ko'ring"
                  : dirty
                    ? "O'zgarishlar avtomatik saqlanadi"
                    : savedAt
                      ? `Saqlandi ${savedAt}`
                      : "Hammasi saqlangan"}
            </span>
            <LoadingButton
              loading={save.isPending}
              disabled={!dirty}
              onClick={() => save.mutate(surveyRef.current)}
            >
              <Save /> Saqlash
            </LoadingButton>
          </div>
        </div>
      )}
    </div>
  )
}
