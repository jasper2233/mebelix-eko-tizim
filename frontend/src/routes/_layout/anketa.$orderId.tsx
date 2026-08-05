import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute, Link } from "@tanstack/react-router"
import { ArrowLeft, ImagePlus, Plus, Save, Trash2, X } from "lucide-react"
import { useEffect, useRef, useState } from "react"
import { toast } from "sonner"

import {
  OpenAPI,
  type OrderFileRead,
  type OrderSurvey,
  OrdersService,
  type SurveyModule,
  type SurveyRoom,
} from "@/client"
import { ConfirmDialog } from "@/components/Common/ConfirmDialog"
import { PageHeader } from "@/components/Common/PageHeader"
import { QueryError } from "@/components/Common/QueryError"
import { Button } from "@/components/ui/button"
import { cardSurface } from "@/components/ui/card"
import { Checkbox } from "@/components/ui/checkbox"
import { DatePicker } from "@/components/ui/date-picker"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
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
  LAYOUT_SHAPES,
  labelOf,
  labelsOf,
  type Option,
  WALL_LETTERS,
} from "@/lib/anketa"
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

const emptyModule = (): SurveyModule => ({ name: "" })

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

  const role = currentUser?.role
  const canEdit =
    currentUser?.is_superuser || role === "admin" || role === "manager"

  const [survey, setSurvey] = useState<OrderSurvey>({ version: 1, rooms: [] })
  const [active, setActive] = useState(0)
  const [dirty, setDirty] = useState(false)
  const [savedAt, setSavedAt] = useState<string | null>(null)
  const [removeOpen, setRemoveOpen] = useState(false)

  // Serverdan FAQAT BIR MARTA yuklanadi. Aks holda saqlashdan keyingi refetch
  // menejer yozayotgan matn ustiga tushadi.
  const loaded = useRef(false)
  useEffect(() => {
    if (!order || loaded.current) return
    loaded.current = true
    const saved = order.survey as OrderSurvey | null
    setSurvey(
      saved?.rooms?.length
        ? saved
        : { version: 1, measured_by: "", rooms: [newRoom(1)] },
    )
  }, [order])

  // Avtosaqlash: menejer bilmasdan chiqib ketsa ham ma'lumot yo'qolmaydi.
  // Anketa o'zi qoralama — alohida "chop etish" bosqichi yo'q.
  const surveyRef = useRef(survey)
  surveyRef.current = survey

  const save = useMutation({
    mutationFn: (body: OrderSurvey) =>
      OrdersService.saveOrderSurvey({ orderId: id, requestBody: body }),
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
          orderId: id,
          requestBody: surveyRef.current,
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

      {/* Xona tanlash + qo'shish */}
      <div className="mb-4 flex flex-wrap items-center gap-2">
        {rooms.map((r, i) => (
          <button
            key={r.id}
            type="button"
            onClick={() => setActive(i)}
            className={`rounded-lg border px-4 py-2 text-sm font-medium transition-colors focus-visible:outline-2 focus-visible:outline-ring focus-visible:outline-offset-2 ${
              i === active
                ? "border-primary bg-primary text-primary-foreground"
                : "bg-card hover:border-primary/50"
            }`}
          >
            {r.name || `Xona ${i + 1}`}
          </button>
        ))}
        {canEdit && (
          <Button variant="outline" onClick={addRoom}>
            <Plus /> Xona qo'shish
          </Button>
        )}
      </div>

      {/* Upakovka — butun buyurtmaga tegishli, bitta xonaga emas, shuning uchun
          raqamlangan xona bo'limlaridan tashqarida, xona tanlagichdan keyin. */}
      {canEdit && (
        // biome-ignore lint/a11y/noLabelWithoutControl: Checkbox (Radix) ichida — butun katak bosiladi
        <label
          className={cn(
            cardSurface,
            "mb-4 flex cursor-pointer items-start gap-3 p-4",
          )}
        >
          <Checkbox
            checked={survey.packaging ?? false}
            onCheckedChange={(v) => {
              setSurvey((s) => ({ ...s, packaging: v === true }))
              setDirty(true)
            }}
          />
          <span>
            <span className="font-medium text-sm">
              To'liq loyihani upakovka qilish
            </span>
            <span className="block text-muted-foreground text-sm">
              Tayyor mahsulot yetkazishdan oldin qadoqlanadi
            </span>
          </span>
        </label>
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
                    disabled={!canEdit}
                    maxLength={60}
                    placeholder="Oshxona, Yotoqxona, Mehmonxona…"
                    onChange={(e) => patch({ name: e.target.value })}
                  />
                </Field>
                {canEdit && rooms.length > 1 && (
                  <Button
                    variant="ghost"
                    className="-ml-3 text-destructive"
                    onClick={() => setRemoveOpen(true)}
                  >
                    <Trash2 /> Bu xonani o'chirish
                  </Button>
                )}
              </div>
              <RoomPhotos
                orderId={id}
                roomId={room.id}
                photos={photosOf(room.id)}
                canEdit={!!canEdit}
              />
            </div>
          </Section>

          <Section n={2} title="Qanday mebel kerak">
            <CheckGrid
              options={FURNITURE_TYPES}
              values={room.furniture_types ?? []}
              disabled={!canEdit}
              onChange={(v) => patch({ furniture_types: v })}
            />
            <Field label="Boshqa">
              <Input
                value={room.furniture_other ?? ""}
                maxLength={120}
                disabled={!canEdit}
                onChange={(e) => patch({ furniture_other: e.target.value })}
              />
            </Field>
          </Section>

          <Section n={3} title="Xonadagi shakli va o'lchamlari">
            <ShapeChoice
              value={room.shape ?? null}
              disabled={!canEdit}
              onChange={(v) => patch({ shape: v })}
            />
            <div className="grid items-start gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <Num
                label="Xona uzunligi (mm)"
                value={room.room_length}
                disabled={!canEdit}
                onChange={(v) => patch({ room_length: v })}
              />
              <Num
                label="Xona kengligi (mm)"
                value={room.room_width}
                disabled={!canEdit}
                onChange={(v) => patch({ room_width: v })}
              />
              <Num
                label="Xona balandligi (mm)"
                value={room.room_height}
                disabled={!canEdit}
                onChange={(v) => patch({ room_height: v })}
              />
              <Num
                label="Mebel devori uzunligi (mm)"
                value={room.furniture_wall_length}
                disabled={!canEdit}
                onChange={(v) => patch({ furniture_wall_length: v })}
              />
            </div>
          </Section>

          <Section n={4} title="Korpus materiali" hint="mebelning ichki qismi">
            <CheckGrid
              options={CORPUS_MATERIALS}
              values={room.corpus_materials ?? []}
              disabled={!canEdit}
              onChange={(v) => patch({ corpus_materials: v })}
            />
            <div className="grid items-start gap-3 sm:grid-cols-2">
              <Field label="Rang / dekor">
                <Input
                  value={room.corpus_color ?? ""}
                  maxLength={120}
                  disabled={!canEdit}
                  onChange={(e) => patch({ corpus_color: e.target.value })}
                />
              </Field>
              <Field label="Qalinligi">
                <Choice
                  options={CORPUS_THICKNESS}
                  value={room.corpus_thickness ?? null}
                  disabled={!canEdit}
                  onChange={(v) => patch({ corpus_thickness: v })}
                />
              </Field>
            </div>
            <Field label="Korpus izohi">
              <Input
                value={room.corpus_note ?? ""}
                maxLength={300}
                disabled={!canEdit}
                onChange={(e) => patch({ corpus_note: e.target.value })}
              />
            </Field>
          </Section>

          <Section n={5} title="Fasad materiali" hint="old eshik va tortmalar">
            <CheckGrid
              options={FACADE_MATERIALS}
              values={room.facade_materials ?? []}
              disabled={!canEdit}
              onChange={(v) => patch({ facade_materials: v })}
            />
            <div className="grid items-start gap-3 sm:grid-cols-2">
              <Field label="Rang / tekstura">
                <Input
                  value={room.facade_color ?? ""}
                  maxLength={120}
                  disabled={!canEdit}
                  onChange={(e) => patch({ facade_color: e.target.value })}
                />
              </Field>
              <Field label="Stol usti">
                <Choice
                  options={COUNTERTOPS}
                  value={room.countertop ?? null}
                  disabled={!canEdit}
                  onChange={(v) => patch({ countertop: v })}
                />
              </Field>
            </div>
            <Field label="Fasad izohi">
              <Input
                value={room.facade_note ?? ""}
                maxLength={300}
                disabled={!canEdit}
                onChange={(e) => patch({ facade_note: e.target.value })}
              />
            </Field>
          </Section>

          <Section n={6} title="Furnitura va qo'shimcha xizmat">
            <Field label="Furnitura darajasi">
              <Choice
                options={HARDWARE_LEVELS}
                value={room.hardware_level ?? null}
                disabled={!canEdit}
                onChange={(v) => patch({ hardware_level: v })}
              />
            </Field>
            <div>
              <CheckGrid
                options={EXTRA_SERVICES}
                values={room.extra_services ?? []}
                disabled={!canEdit}
                onChange={(v) => patch({ extra_services: v })}
              />
            </div>
          </Section>

          <Section n={7} title="Qo'shimcha izoh">
            <Textarea
              rows={3}
              value={room.note ?? ""}
              maxLength={1000}
              disabled={!canEdit}
              placeholder="Mijozning qo'shimcha talab va izohlari"
              onChange={(e) => patch({ note: e.target.value })}
            />
          </Section>

          {/* O'lchov varag'i — zamerdan keyin to'ldiriladi, shuning uchun yopiq turadi */}
          <details className={cn(cardSurface)}>
            <summary className="cursor-pointer px-4 py-3 font-semibold">
              <span className="mr-2 text-muted-foreground">8</span>
              O'lchov varag'i{" "}
              <span className="font-normal text-muted-foreground text-sm">
                (usta to'ldiradi)
              </span>
            </summary>
            <div className="space-y-5 border-t p-4">
              <div className="grid items-start gap-3 sm:grid-cols-2">
                <Field label="O'lchov sanasi">
                  <DatePicker
                    value={survey.measured_at ?? ""}
                    className="w-full"
                    aria-label="O'lchov sanasi"
                    onChange={(v) => {
                      setSurvey((s) => ({ ...s, measured_at: v || null }))
                      setDirty(true)
                    }}
                  />
                </Field>
                <Field label="O'lchagan usta">
                  <Input
                    value={survey.measured_by ?? ""}
                    maxLength={120}
                    disabled={!canEdit}
                    onChange={(e) => {
                      setSurvey((s) => ({ ...s, measured_by: e.target.value }))
                      setDirty(true)
                    }}
                  />
                </Field>
              </div>

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
                          disabled={!canEdit}
                          onChange={(v) => setWall("length", v)}
                          aria-label={`${letter} devor — uzunligi (mm)`}
                        />
                        <span className="shrink-0 text-muted-foreground text-xs">
                          bal
                        </span>
                        <NumInput
                          value={w.height}
                          disabled={!canEdit}
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
                                disabled={!canEdit}
                                onChange={(e) =>
                                  setMod({ name: e.target.value })
                                }
                              />
                            </td>
                            <td className="py-1 pr-1">
                              <Input
                                value={m.wall ?? ""}
                                maxLength={2}
                                disabled={!canEdit}
                                onChange={(e) =>
                                  setMod({ wall: e.target.value })
                                }
                              />
                            </td>
                            <td className="py-1 pr-1">
                              <NumInput
                                value={m.width}
                                disabled={!canEdit}
                                integer={true}
                                onChange={(v) => setMod({ width: v })}
                                aria-label={`${mi + 1}-modul — eni (mm)`}
                              />
                            </td>
                            <td className="py-1 pr-1">
                              <NumInput
                                value={m.depth}
                                disabled={!canEdit}
                                integer={true}
                                onChange={(v) => setMod({ depth: v })}
                                aria-label={`${mi + 1}-modul — chuqurligi (mm)`}
                              />
                            </td>
                            <td className="py-1 pr-1">
                              <NumInput
                                value={m.height}
                                disabled={!canEdit}
                                integer={true}
                                onChange={(v) => setMod({ height: v })}
                                aria-label={`${mi + 1}-modul — balandligi (mm)`}
                              />
                            </td>
                            <td className="py-1 pr-1">
                              <NumInput
                                value={m.count}
                                disabled={!canEdit}
                                integer={true}
                                onChange={(v) => setMod({ count: v })}
                                aria-label={`${mi + 1}-modul — soni`}
                              />
                            </td>
                            <td className="py-1 pr-1">
                              <Input
                                value={m.note ?? ""}
                                maxLength={200}
                                disabled={!canEdit}
                                onChange={(e) =>
                                  setMod({ note: e.target.value })
                                }
                              />
                            </td>
                            <td className="py-1">
                              {canEdit && (
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
                              )}
                            </td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                </div>
                {canEdit && (
                  <Button
                    variant="outline"
                    className="mt-2"
                    onClick={() =>
                      patch({
                        modules: [...(room.modules ?? []), emptyModule()],
                      })
                    }
                  >
                    <Plus /> Qator qo'shish
                  </Button>
                )}
                <div className="grid items-start gap-3 sm:grid-cols-2">
                  <Num
                    label="Umumiy uzunlik (pm)"
                    value={room.total_running_meters}
                    disabled={!canEdit}
                    onChange={(v) => patch({ total_running_meters: v })}
                  />
                  <Num
                    label="Umumiy balandlik (mm)"
                    value={room.total_height}
                    disabled={!canEdit}
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
        open={removeOpen}
        onOpenChange={setRemoveOpen}
        title={`${room?.name || `Xona ${active + 1}`} o'chirilsinmi?`}
        description="Shu xonaning materiali, o'lchamlari, modullari va rasmlari o'chadi. Qaytarib bo'lmaydi."
        confirmText="O'chirish"
        destructive
        onConfirm={() => {
          removeRoom(active)
          setRemoveOpen(false)
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

const MAX_PHOTOS = 6
const MAX_PHOTO_MB = 5

/** Xona uchun taxminiy ko'rinish rasmlari — mijoz ko'rsatgan namuna/render.
 *  Butun panel drop-zona; rasm bosilsa to'liq hajmda ochiladi. */
function RoomPhotos({
  orderId,
  roomId,
  photos,
  canEdit,
}: {
  orderId: number
  roomId: string
  photos: OrderFileRead[]
  canEdit: boolean
}) {
  const queryClient = useQueryClient()
  const input = useRef<HTMLInputElement>(null)
  const [dragOver, setDragOver] = useState(false)
  const [preview, setPreview] = useState<OrderFileRead | null>(null)
  const [toRemove, setToRemove] = useState<OrderFileRead | null>(null)
  const refresh = () =>
    queryClient.invalidateQueries({ queryKey: ["orders", orderId] })

  const upload = useMutation({
    mutationFn: (file: File) =>
      OrdersService.uploadRoomPhoto({
        orderId,
        formData: { room_id: roomId, file: file as unknown as string },
      }),
    onSuccess: refresh,
    onError: handleError,
  })
  const remove = useMutation({
    mutationFn: (fileId: number) =>
      OrdersService.deleteRoomPhoto({ orderId, fileId }),
    onSuccess: () => {
      setToRemove(null)
      refresh()
    },
    onError: handleError,
  })

  // Serverga bormasdan tekshiramiz — menejer xatoni darhol ko'rsin
  const add = (files: FileList | null) => {
    const list = Array.from(files ?? [])
    let free = MAX_PHOTOS - photos.length
    for (const f of list) {
      if (!f.type.startsWith("image/")) {
        toast.error(`${f.name}: faqat rasm qo'shish mumkin`)
        continue
      }
      if (f.size > MAX_PHOTO_MB * 1024 * 1024) {
        toast.error(`${f.name}: ${MAX_PHOTO_MB} MB dan katta`)
        continue
      }
      if (free <= 0) {
        toast.error(`Bitta xonaga ${MAX_PHOTOS} tadan ko'p rasm sig'maydi`)
        break
      }
      free--
      upload.mutate(f)
    }
  }

  if (!canEdit && !photos.length) return null

  const src = (fileId: number) =>
    `${OpenAPI.BASE}/api/v1/orders/${orderId}/files/${fileId}`
  const full = photos.length >= MAX_PHOTOS

  return (
    <div>
      <div className="mb-1 flex items-baseline justify-between gap-2">
        <span className="text-muted-foreground text-sm">
          Xona rasmi{" "}
          <span className="text-xs">(mijoz ko'rsatgan taxminiy ko'rinish)</span>
        </span>
        {photos.length > 0 && (
          <span className="text-muted-foreground text-xs num">
            {photos.length}/{MAX_PHOTOS}
          </span>
        )}
      </div>

      {/* Butun panel drop-zona: rasm panelning istalgan yeriga tashlanadi */}
      {/* biome-ignore lint/a11y/noStaticElementInteractions: faqat drag&drop — klaviatura yo'li "Rasm qo'shish" tugmasi */}
      <div
        onDragOver={
          canEdit
            ? (e) => {
                e.preventDefault()
                setDragOver(true)
              }
            : undefined
        }
        onDragLeave={canEdit ? () => setDragOver(false) : undefined}
        onDrop={
          canEdit
            ? (e) => {
                e.preventDefault()
                setDragOver(false)
                add(e.dataTransfer.files)
              }
            : undefined
        }
        className={`rounded-lg border-2 border-dashed p-3 transition-colors ${
          dragOver ? "border-primary bg-primary/5" : "border-transparent"
        }`}
      >
        <div className="grid grid-cols-3 gap-2 sm:grid-cols-4">
          {photos.map((p) => (
            <div key={p.id} className="group relative">
              <button
                type="button"
                onClick={() => setPreview(p)}
                className="block w-full overflow-hidden rounded-md border focus-visible:outline-2 focus-visible:outline-ring focus-visible:outline-offset-2"
                aria-label={`${p.filename} — kattalashtirish`}
              >
                <img
                  src={src(p.id)}
                  alt={p.filename}
                  crossOrigin="use-credentials"
                  className="aspect-square w-full object-cover transition-transform duration-200 group-hover:scale-105"
                />
              </button>
              {canEdit && (
                <button
                  type="button"
                  aria-label={`${p.filename} — o'chirish`}
                  onClick={() => setToRemove(p)}
                  className="absolute top-1 right-1 rounded-full border bg-background/90 p-1.5 text-destructive shadow-sm backdrop-blur focus-visible:outline-2 focus-visible:outline-ring focus-visible:outline-offset-2"
                >
                  <X className="size-4" />
                </button>
              )}
            </div>
          ))}

          {canEdit && !full && (
            <>
              <input
                ref={input}
                type="file"
                accept="image/*"
                multiple
                className="hidden"
                onChange={(e) => {
                  add(e.target.files)
                  e.target.value = ""
                }}
              />
              <button
                type="button"
                disabled={upload.isPending}
                onClick={() => input.current?.click()}
                className="flex aspect-square flex-col items-center justify-center gap-1 rounded-md border border-dashed p-1 text-center text-muted-foreground text-xs transition-colors hover:border-primary/60 hover:text-foreground focus-visible:outline-2 focus-visible:outline-ring focus-visible:outline-offset-2 disabled:opacity-50"
              >
                {upload.isPending ? (
                  "Yuklanmoqda..."
                ) : (
                  <>
                    <ImagePlus className="size-5" />
                    Rasm qo'shish
                  </>
                )}
              </button>
            </>
          )}
        </div>

        {canEdit && (
          <p className="mt-2 text-muted-foreground text-xs">
            {full
              ? `Xonaga ${MAX_PHOTOS} ta rasm yuklangan — yangisini qo'shish uchun birortasini o'chiring.`
              : `Sudrab tashlang yoki tanlang · JPG, PNG, WEBP · ${MAX_PHOTO_MB} MB gacha`}
          </p>
        )}
      </div>

      {/* Kattalashtirilgan ko'rinish */}
      <Dialog open={!!preview} onOpenChange={(v) => !v && setPreview(null)}>
        <DialogContent className="gap-2 p-3 sm:max-w-4xl">
          <DialogHeader className="px-1">
            <DialogTitle className="truncate text-base">
              {preview?.filename}
            </DialogTitle>
          </DialogHeader>
          {preview && (
            <img
              src={src(preview.id)}
              alt={preview.filename}
              crossOrigin="use-credentials"
              className="max-h-[75vh] w-full rounded-md object-contain"
            />
          )}
          <a
            href={preview ? src(preview.id) : "#"}
            target="_blank"
            rel="noreferrer"
            className="px-1 text-muted-foreground text-xs underline-offset-2 hover:underline"
          >
            Asl hajmda yangi oynada ochish
          </a>
        </DialogContent>
      </Dialog>

      <ConfirmDialog
        open={!!toRemove}
        onOpenChange={(v) => !v && setToRemove(null)}
        title="Rasm o'chirilsinmi?"
        description={`${toRemove?.filename ?? "Rasm"} serverdan butunlay o'chadi — anketa rasmlari tarix uchun saqlanmaydi.`}
        confirmText="O'chirish"
        destructive
        loading={remove.isPending}
        onConfirm={() => toRemove && remove.mutate(toRemove.id)}
      />
    </div>
  )
}

/** Texnolog ko'rinishi: tartib qog'ozning teskarisi — avval modullar va o'lchamlar,
 *  keyin material. Texnolog aynan shu tartibda GibLab'da dizayn yasaydi. */
function RoomSummary({
  room,
  survey,
  orderId,
  photos,
}: {
  room: SurveyRoom
  survey: OrderSurvey
  orderId: number
  photos: OrderFileRead[]
}) {
  const dims = [room.room_length, room.room_width, room.room_height]
  const walls = (room.walls ?? []).filter((w) => w.length || w.height)
  const modules = room.modules ?? []

  return (
    <div className="space-y-5">
      {/* Qaysi xona ekani — texnolog buni bilmasa noto'g'ri o'lchamda modul yasaydi */}
      <h2 className="text-base font-semibold">{room.name || "Xona"}</h2>

      <Section title={`Modullar (${modules.length} ta)`}>
        {modules.length ? (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[700px] border-collapse text-sm">
              <thead>
                <tr className="border-b text-left text-muted-foreground text-xs font-semibold uppercase tracking-wider">
                  <th className="w-8 py-2">№</th>
                  <th className="py-2">Nomi</th>
                  <th className="w-16 py-2">Devor</th>
                  <th className="w-20 py-2 text-right">Eni, mm</th>
                  <th className="w-20 py-2 text-right">Chuq., mm</th>
                  <th className="w-20 py-2 text-right">Bal., mm</th>
                  <th className="w-16 py-2 text-right">Soni</th>
                  <th className="py-2">Izoh</th>
                </tr>
              </thead>
              <tbody>
                {modules.map((m, i) => (
                  <tr key={`${m.name}-${i}`} className="border-b">
                    <td className="py-2 text-muted-foreground">{i + 1}</td>
                    <td className="py-2 font-medium">{m.name || "—"}</td>
                    <td className="py-2">{m.wall || "—"}</td>
                    <td className="py-2 text-right num">{m.width ?? "—"}</td>
                    <td className="py-2 text-right num">{m.depth ?? "—"}</td>
                    <td className="py-2 text-right num">{m.height ?? "—"}</td>
                    <td className="py-2 text-right num">{m.count ?? "—"}</td>
                    <td className="py-2 text-muted-foreground">
                      {m.note || ""}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-muted-foreground text-sm">
            Modullar kiritilmagan — o'lchov varag'i hali to'ldirilmagan.
          </p>
        )}
        {(room.total_running_meters != null || room.total_height != null) && (
          <p className="mt-2 text-muted-foreground text-sm">
            Umumiy: {room.total_running_meters ?? "—"} pm ·{" "}
            {room.total_height ?? "—"} mm balandlik
          </p>
        )}
      </Section>

      <RoomPhotos
        orderId={orderId}
        roomId={room.id}
        photos={photos}
        canEdit={false}
      />

      <Section title="Xona o'lchamlari">
        <Facts
          items={[
            [
              "Xona (uz × ken × bal)",
              dims.every((d) => d == null)
                ? ""
                : `${dims.map((d) => d ?? "?").join(" × ")} mm`,
            ],
            [
              "Mebel devori",
              room.furniture_wall_length
                ? `${room.furniture_wall_length} mm`
                : "",
            ],
            ["Shakl", room.shape ? labelOf(LAYOUT_SHAPES, room.shape) : ""],
            [
              "Devorlar (uzunlik / balandlik)",
              walls
                .map((w) => `${w.letter} ${w.length ?? "?"}/${w.height ?? "?"}`)
                .join(" · "),
            ],
            [
              "O'lchov",
              survey.measured_at
                ? `${survey.measured_at}${survey.measured_by ? ` — ${survey.measured_by}` : ""}`
                : "",
            ],
            ["Upakovka", survey.packaging ? "Kerak" : ""],
          ]}
        />
      </Section>

      <Section title="Material">
        <Facts
          items={[
            ["Korpus", labelsOf(CORPUS_MATERIALS, room.corpus_materials)],
            ["Korpus rangi", room.corpus_color ?? ""],
            [
              "Qalinligi",
              room.corpus_thickness
                ? labelOf(CORPUS_THICKNESS, room.corpus_thickness)
                : "",
            ],
            ["Korpus izohi", room.corpus_note ?? ""],
            ["Fasad", labelsOf(FACADE_MATERIALS, room.facade_materials)],
            ["Fasad rangi", room.facade_color ?? ""],
            [
              "Stol usti",
              room.countertop ? labelOf(COUNTERTOPS, room.countertop) : "",
            ],
            ["Fasad izohi", room.facade_note ?? ""],
            [
              "Furnitura",
              room.hardware_level
                ? labelOf(HARDWARE_LEVELS, room.hardware_level)
                : "",
            ],
          ]}
        />
      </Section>

      <Section title="Mebel turi va xizmatlar">
        <Facts
          items={[
            [
              "Mebel turi",
              [
                labelsOf(FURNITURE_TYPES, room.furniture_types),
                room.furniture_other,
              ]
                .filter(Boolean)
                .join(", "),
            ],
            [
              "Qo'shimcha xizmat",
              labelsOf(EXTRA_SERVICES, room.extra_services),
            ],
            ["Mijoz izohi", room.note ?? ""],
          ]}
        />
      </Section>
    </div>
  )
}

/** Bo'sh qiymatlar tashlab yuboriladi — texnolog faqat kiritilganini ko'radi */
function Facts({ items }: { items: [string, string][] }) {
  const filled = items.filter(([, v]) => v?.trim())
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
function NumInput({
  value,
  disabled,
  onChange,
  placeholder,
  integer = false,
  "aria-label": ariaLabel,
}: {
  value: number | null | undefined
  disabled?: boolean
  onChange: (v: number | null) => void
  placeholder?: string
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
      placeholder={placeholder}
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

function Section({
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

function Field({
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

function Num({
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

/** Ko'p tanlovli katakchalar — sensorli ekranda butun katak bosiladi */
function CheckGrid({
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
          // biome-ignore lint/a11y/noLabelWithoutControl: Checkbox (Radix) ichida — butun katak bosiladi
          <label
            key={o.value}
            className={`flex cursor-pointer items-center gap-2 rounded-lg border px-3 py-2 text-sm transition-colors ${
              checked
                ? "border-primary bg-primary/5"
                : "hover:border-primary/40"
            } ${disabled ? "cursor-default opacity-70" : ""}`}
          >
            <Checkbox
              checked={checked}
              disabled={disabled}
              onCheckedChange={() =>
                onChange(
                  checked
                    ? values.filter((v) => v !== o.value)
                    : [...values, o.value],
                )
              }
            />
            {o.label}
          </label>
        )
      })}
    </div>
  )
}

/** Planirovka silueti — qog'oz anketadagi chizmalar (uploads/forma/...html:90-103).
 *  Bu sahifadagi yagona savol javobi matn emas, SHAKL: mijoz siluetni tanidi-yu,
 *  "П-shakl (U)" jargonini o'qimaydi. Xato bu yerda eng qimmat — texnolog
 *  butun planirovkani shunga qarab yasaydi. */
function ShapeChoice({
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
function Choice({
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
