import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute, Link } from "@tanstack/react-router"
import { ArrowLeft, Plus, Save, Trash2 } from "lucide-react"
import { useEffect, useState } from "react"

import {
  type OrderSurvey,
  OrdersService,
  type SurveyModule,
  type SurveyRoom,
} from "@/client"
import { PageHeader } from "@/components/Common/PageHeader"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { Input } from "@/components/ui/input"
import { LoadingButton } from "@/components/ui/loading-button"
import { Skeleton } from "@/components/ui/skeleton"
import { Textarea } from "@/components/ui/textarea"
import useCurrentUser from "@/hooks/useCurrentUser"
import useCustomToast from "@/hooks/useCustomToast"
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
import { getOrderQueryOptions } from "@/queries/mes"
import { handleError } from "@/utils"

export const Route = createFileRoute("/_layout/anketa/$orderId")({
  component: AnketaPage,
  head: () => ({ meta: [{ title: "Anketa | MebeliX" }] }),
})

const newRoom = (n: number): SurveyRoom => ({
  id: `r${Date.now()}${n}`,
  name: n === 1 ? "Xona 1" : `Xona ${n}`,
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
  const { data: order, isLoading } = useQuery(getOrderQueryOptions(id))
  const { currentUser } = useCurrentUser()
  const { showSuccessToast, showErrorToast } = useCustomToast()

  const role = currentUser?.role
  const canEdit =
    currentUser?.is_superuser || role === "admin" || role === "manager"

  const [survey, setSurvey] = useState<OrderSurvey>({ version: 1, rooms: [] })
  const [active, setActive] = useState(0)
  const [dirty, setDirty] = useState(false)

  // Serverdagi anketa kelgach bir marta yuklanadi; keyin tahrir lokal holatда
  useEffect(() => {
    if (!order) return
    const saved = order.survey as OrderSurvey | null
    setSurvey(
      saved?.rooms?.length
        ? saved
        : { version: 1, measured_by: "", rooms: [newRoom(1)] },
    )
  }, [order])

  const save = useMutation({
    mutationFn: () =>
      OrdersService.saveOrderSurvey({ orderId: id, requestBody: survey }),
    onSuccess: () => {
      showSuccessToast("Anketa saqlandi")
      setDirty(false)
      queryClient.invalidateQueries({ queryKey: ["orders", id] })
    },
    onError: handleError(showErrorToast),
  })

  if (isLoading || !order) return <Skeleton className="h-96 w-full" />

  const rooms = survey.rooms ?? []
  const room = rooms[active]

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
            className={`rounded-lg border px-4 py-2 text-sm font-medium transition-colors ${
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

      {/* Texnolog/direktor: forma emas, o'qish uchun jamlanma — matn nusxa olinadi */}
      {room && !canEdit && <RoomSummary room={room} survey={survey} />}

      {room && canEdit && (
        <div className="space-y-5">
          <Section title="Xona">
            <div className="grid gap-3 sm:grid-cols-2">
              <Field label="Xona nomi">
                <Input
                  value={room.name ?? ""}
                  disabled={!canEdit}
                  placeholder="Oshxona"
                  onChange={(e) => patch({ name: e.target.value })}
                />
              </Field>
              {canEdit && rooms.length > 1 && (
                <div className="flex items-end">
                  <Button
                    variant="ghost"
                    className="text-destructive"
                    onClick={() => removeRoom(active)}
                  >
                    <Trash2 /> Bu xonani o'chirish
                  </Button>
                </div>
              )}
            </div>
          </Section>

          <Section title="Qanday mebel kerak">
            <CheckGrid
              options={FURNITURE_TYPES}
              values={room.furniture_types ?? []}
              disabled={!canEdit}
              onChange={(v) => patch({ furniture_types: v })}
            />
            <Field label="Boshqa">
              <Input
                value={room.furniture_other ?? ""}
                disabled={!canEdit}
                onChange={(e) => patch({ furniture_other: e.target.value })}
              />
            </Field>
          </Section>

          <Section title="Xonadagi shakli va o'lchamlari">
            <Choice
              options={LAYOUT_SHAPES}
              value={room.shape ?? null}
              disabled={!canEdit}
              onChange={(v) => patch({ shape: v })}
            />
            <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <Num
                label="Xona uzunligi"
                value={room.room_length}
                disabled={!canEdit}
                onChange={(v) => patch({ room_length: v })}
              />
              <Num
                label="Xona kengligi"
                value={room.room_width}
                disabled={!canEdit}
                onChange={(v) => patch({ room_width: v })}
              />
              <Num
                label="Xona balandligi"
                value={room.room_height}
                disabled={!canEdit}
                onChange={(v) => patch({ room_height: v })}
              />
              <Num
                label="Mebel devori uzunligi"
                value={room.furniture_wall_length}
                disabled={!canEdit}
                onChange={(v) => patch({ furniture_wall_length: v })}
              />
            </div>
          </Section>

          <Section title="Korpus materiali" hint="mebelning ichki qismi">
            <CheckGrid
              options={CORPUS_MATERIALS}
              values={room.corpus_materials ?? []}
              disabled={!canEdit}
              onChange={(v) => patch({ corpus_materials: v })}
            />
            <div className="mt-3 grid gap-3 sm:grid-cols-2">
              <Field label="Rang / dekor">
                <Input
                  value={room.corpus_color ?? ""}
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
                disabled={!canEdit}
                onChange={(e) => patch({ corpus_note: e.target.value })}
              />
            </Field>
          </Section>

          <Section title="Fasad materiali" hint="old eshik va tortmalar">
            <CheckGrid
              options={FACADE_MATERIALS}
              values={room.facade_materials ?? []}
              disabled={!canEdit}
              onChange={(v) => patch({ facade_materials: v })}
            />
            <div className="mt-3 grid gap-3 sm:grid-cols-2">
              <Field label="Rang / tekstura">
                <Input
                  value={room.facade_color ?? ""}
                  disabled={!canEdit}
                  onChange={(e) => patch({ facade_color: e.target.value })}
                />
              </Field>
              <Field label="Stol usti (oshxona)">
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
                disabled={!canEdit}
                onChange={(e) => patch({ facade_note: e.target.value })}
              />
            </Field>
          </Section>

          <Section title="Furnitura va qo'shimcha xizmat">
            <Field label="Furnitura darajasi">
              <Choice
                options={HARDWARE_LEVELS}
                value={room.hardware_level ?? null}
                disabled={!canEdit}
                onChange={(v) => patch({ hardware_level: v })}
              />
            </Field>
            <div className="mt-3">
              <CheckGrid
                options={EXTRA_SERVICES}
                values={room.extra_services ?? []}
                disabled={!canEdit}
                onChange={(v) => patch({ extra_services: v })}
              />
            </div>
          </Section>

          <Section title="Qo'shimcha izoh">
            <Textarea
              rows={3}
              value={room.note ?? ""}
              disabled={!canEdit}
              placeholder="Mijozning qo'shimcha talab va izohlari"
              onChange={(e) => patch({ note: e.target.value })}
            />
          </Section>

          {/* O'lchov varag'i — zamerdan keyin to'ldiriladi, shuning uchun yopiq turadi */}
          <details className="rounded-xl border bg-card">
            <summary className="cursor-pointer px-4 py-3 font-semibold">
              O'lchov varag'i{" "}
              <span className="font-normal text-muted-foreground text-sm">
                (zamerdan keyin to'ldiriladi)
              </span>
            </summary>
            <div className="space-y-5 border-t p-4">
              <div className="grid gap-3 sm:grid-cols-2">
                <Field label="O'lchov sanasi">
                  <Input
                    type="date"
                    value={survey.measured_at ?? ""}
                    disabled={!canEdit}
                    onChange={(e) => {
                      setSurvey((s) => ({
                        ...s,
                        measured_at: e.target.value || null,
                      }))
                      setDirty(true)
                    }}
                  />
                </Field>
                <Field label="O'lchagan usta">
                  <Input
                    value={survey.measured_by ?? ""}
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
                        <Input
                          inputMode="numeric"
                          placeholder="uzunlik"
                          value={w.length ?? ""}
                          disabled={!canEdit}
                          onChange={(e) =>
                            setWall("length", numOrNull(e.target.value))
                          }
                        />
                        <Input
                          inputMode="numeric"
                          placeholder="balandlik"
                          value={w.height ?? ""}
                          disabled={!canEdit}
                          onChange={(e) =>
                            setWall("height", numOrNull(e.target.value))
                          }
                        />
                      </div>
                    )
                  })}
                </div>
              </div>

              <div>
                <div className="mb-2 font-medium text-sm">
                  Yasaladigan mebel razmerlari
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full min-w-[720px] border-collapse text-sm">
                    <thead>
                      <tr className="border-b text-left text-muted-foreground text-xs">
                        <th className="w-8 py-2">№</th>
                        <th className="py-2">Modul / bo'lim</th>
                        <th className="w-20 py-2">Devor</th>
                        <th className="w-24 py-2">Eni</th>
                        <th className="w-24 py-2">Chuqurlik</th>
                        <th className="w-24 py-2">Balandlik</th>
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
                                disabled={!canEdit}
                                onChange={(e) =>
                                  setMod({ name: e.target.value })
                                }
                              />
                            </td>
                            <td className="py-1 pr-1">
                              <Input
                                value={m.wall ?? ""}
                                disabled={!canEdit}
                                onChange={(e) =>
                                  setMod({ wall: e.target.value })
                                }
                              />
                            </td>
                            <td className="py-1 pr-1">
                              <Input
                                inputMode="numeric"
                                value={m.width ?? ""}
                                disabled={!canEdit}
                                onChange={(e) =>
                                  setMod({ width: numOrNull(e.target.value) })
                                }
                              />
                            </td>
                            <td className="py-1 pr-1">
                              <Input
                                inputMode="numeric"
                                value={m.depth ?? ""}
                                disabled={!canEdit}
                                onChange={(e) =>
                                  setMod({ depth: numOrNull(e.target.value) })
                                }
                              />
                            </td>
                            <td className="py-1 pr-1">
                              <Input
                                inputMode="numeric"
                                value={m.height ?? ""}
                                disabled={!canEdit}
                                onChange={(e) =>
                                  setMod({ height: numOrNull(e.target.value) })
                                }
                              />
                            </td>
                            <td className="py-1 pr-1">
                              <Input
                                inputMode="numeric"
                                value={m.count ?? ""}
                                disabled={!canEdit}
                                onChange={(e) =>
                                  setMod({ count: numOrNull(e.target.value) })
                                }
                              />
                            </td>
                            <td className="py-1 pr-1">
                              <Input
                                value={m.note ?? ""}
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
                <div className="mt-3 grid gap-3 sm:grid-cols-2">
                  <Num
                    label="Umumiy uzunlik (pogonometr, pm)"
                    value={room.total_running_meters}
                    disabled={!canEdit}
                    onChange={(v) => patch({ total_running_meters: v })}
                  />
                  <Num
                    label="Umumiy balandlik"
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

      {/* Saqlash paneli — sahifa uzun, tugma doim ko'rinib tursin.
          sticky (fixed emas): sidebar ustiga chiqmaydi, main padding'ini teskari margin bilan qoplaydi */}
      {canEdit && (
        <div className="-mx-6 md:-mx-8 -mb-6 md:-mb-8 sticky bottom-0 z-10 mt-5 border-t bg-background/95 px-6 py-3 backdrop-blur md:px-8">
          <div className="flex items-center justify-end gap-3">
            <span className="text-muted-foreground text-sm">
              {dirty ? "Saqlanmagan o'zgarishlar bor" : "Hammasi saqlangan"}
            </span>
            <LoadingButton
              loading={save.isPending}
              disabled={!dirty}
              onClick={() => save.mutate()}
            >
              <Save /> Saqlash
            </LoadingButton>
          </div>
        </div>
      )}
    </div>
  )
}

/** Texnolog ko'rinishi: tartib qog'ozning teskarisi — avval modullar va o'lchamlar,
 *  keyin material. Texnolog aynan shu tartibda GibLab'da dizayn yasaydi. */
function RoomSummary({
  room,
  survey,
}: {
  room: SurveyRoom
  survey: OrderSurvey
}) {
  const dims = [room.room_length, room.room_width, room.room_height]
  const walls = (room.walls ?? []).filter((w) => w.length || w.height)
  const modules = room.modules ?? []

  return (
    <div className="space-y-5">
      <Section title={`Modullar (${modules.length} ta)`}>
        {modules.length ? (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[640px] border-collapse text-sm">
              <thead>
                <tr className="border-b text-left text-muted-foreground text-xs">
                  <th className="w-8 py-2">№</th>
                  <th className="py-2">Nomi</th>
                  <th className="w-16 py-2">Devor</th>
                  <th className="w-40 py-2">Eni × Chuq × Bal</th>
                  <th className="w-16 py-2">Soni</th>
                  <th className="py-2">Izoh</th>
                </tr>
              </thead>
              <tbody>
                {modules.map((m, i) => (
                  <tr key={`${m.name}-${i}`} className="border-b">
                    <td className="py-2 text-muted-foreground">{i + 1}</td>
                    <td className="py-2 font-medium">{m.name || "—"}</td>
                    <td className="py-2">{m.wall || "—"}</td>
                    <td className="py-2 tabular-nums">
                      {[m.width, m.depth, m.height].every((v) => v == null)
                        ? "—"
                        : [m.width, m.depth, m.height]
                            .map((v) => v ?? "?")
                            .join(" × ")}
                    </td>
                    <td className="py-2 tabular-nums">{m.count ?? "—"}</td>
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
              "Devorlar",
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
  const n = Number(v)
  return v.trim() === "" || Number.isNaN(n) ? null : n
}

function Section({
  title,
  hint,
  children,
}: {
  title: string
  hint?: string
  children: React.ReactNode
}) {
  return (
    <section className="rounded-xl border bg-card p-4">
      <h3 className="mb-3 font-semibold">
        {title}
        {hint && (
          <span className="ml-2 font-normal text-muted-foreground text-sm">
            ({hint})
          </span>
        )}
      </h3>
      {children}
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
    // biome-ignore lint/a11y/noLabelWithoutControl: input children orqali keladi — bosilganda fokus oladi
    <label className="mt-3 block first:mt-0">
      <span className="mb-1 block text-muted-foreground text-sm">{label}</span>
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
    <Field label={`${label} (mm)`}>
      <Input
        inputMode="numeric"
        value={value ?? ""}
        disabled={disabled}
        onChange={(e) => onChange(numOrNull(e.target.value))}
      />
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
    <div className="flex flex-wrap gap-2">
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          disabled={disabled}
          onClick={() => onChange(value === o.value ? null : o.value)}
          className={`rounded-lg border px-3 py-2 text-sm transition-colors ${
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
