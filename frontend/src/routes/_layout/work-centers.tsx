import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { Pencil, Plus, Trash2 } from "lucide-react"
import { useState } from "react"

import { type MachineRead, MachinesService, type PostRead } from "@/client"
import { ConfirmDialog } from "@/components/Common/ConfirmDialog"
import { EmptyRow } from "@/components/Common/EmptyRow"
import { Field } from "@/components/Common/Field"
import { PageHeader } from "@/components/Common/PageHeader"
import { PostBadge } from "@/components/Common/PostBadge"
import { QueryError } from "@/components/Common/QueryError"
import { RowAction } from "@/components/Common/RowAction"
import { SelectField } from "@/components/Common/SelectField"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
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
import { useCurrentUser } from "@/hooks/useCurrentUser"
import { requireAccess } from "@/lib/guards"
import {
  CAPACITY_UNIT_LABELS,
  IDEAL_RATE_HINTS,
  isAdmin,
  isProductionStaff,
  MACHINE_STATUS_LABELS,
} from "@/lib/mes"
import {
  crudCallbacks,
  getMachinesQueryOptions,
  getPostsQueryOptions,
} from "@/queries/mes"

export const Route = createFileRoute("/_layout/work-centers")({
  component: WorkCentersPage,
  // Sidebar ko'rinishi bilan bir xil rollar to'plami (lib/mes)
  beforeLoad: requireAccess(isProductionStaff),
  head: () => ({ meta: [{ title: "Ish markazlari | MebeliX" }] }),
})

/** Holat rangi: TA'MIRDA amber (vaqtinchalik, ish davom etadi), NOAKTIV kulrang
 * (ishdan chiqarilgan — avtomatik tanlanmaydi). */
const STATUS_STYLE: Record<string, string> = {
  repair: "border-amber-300 bg-amber-100 text-amber-900",
  inactive: "border-transparent bg-muted text-muted-foreground",
}

function WorkCentersPage() {
  const {
    data: machines,
    isLoading,
    isError,
    refetch,
  } = useQuery(getMachinesQueryOptions())
  const { data: posts } = useQuery(getPostsQueryOptions())
  const { currentUser } = useCurrentUser()
  const admin = isAdmin(currentUser)
  const [adding, setAdding] = useState(false)
  const [editFor, setEditFor] = useState<MachineRead | null>(null)
  const [deleteFor, setDeleteFor] = useState<MachineRead | null>(null)
  const postById = new Map((posts ?? []).map((p) => [p.id, p]))
  // Marshrut tartibida: ARRA, KROMKA, OVAL... Ilgari id tartibida chiqardi,
  // ya'ni yangi qo'shilgan arra ro'yxat oxirida, o'z posti yonida emas edi
  const sorted = [...(machines ?? [])].sort(
    (a, b) =>
      (postById.get(a.post_id)?.order_index ?? 0) -
        (postById.get(b.post_id)?.order_index ?? 0) ||
      a.name.localeCompare(b.name),
  )

  return (
    <div>
      <PageHeader
        title="Ish markazlari"
        description="Har postdagi ish markazi — smena shu joyda ochiladi"
        actions={
          admin ? (
            <Button onClick={() => setAdding(true)} disabled={!posts}>
              <Plus /> Ish markazi qo'shish
            </Button>
          ) : undefined
        }
      />
      {isLoading ? (
        <Skeleton className="h-64 w-full" />
      ) : isError ? (
        <QueryError onRetry={() => refetch()} />
      ) : (
        <div className="overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Ish markazi</TableHead>
                <TableHead>Post</TableHead>
                <TableHead className="text-right">Quvvat</TableHead>
                <TableHead>Holat</TableHead>
                {admin && <TableHead className="w-20" />}
              </TableRow>
            </TableHeader>
            <TableBody>
              {sorted.length ? (
                sorted.map((m) => {
                  const post = postById.get(m.post_id)
                  return (
                    <TableRow key={m.id}>
                      <TableCell className="font-medium">{m.name}</TableCell>
                      <TableCell>
                        {post && <PostBadge code={post.code} />}
                      </TableCell>
                      <TableCell className="text-right tabular-nums">
                        {m.capacity != null
                          ? `${m.capacity} ${CAPACITY_UNIT_LABELS[m.capacity_unit ?? "units_per_hour"]}`
                          : "—"}
                      </TableCell>
                      <TableCell>
                        <Badge
                          variant={
                            m.status === "active" ? "default" : "outline"
                          }
                          className={STATUS_STYLE[m.status]}
                        >
                          {MACHINE_STATUS_LABELS[m.status]}
                        </Badge>
                      </TableCell>
                      {admin && (
                        <TableCell>
                          <div className="flex justify-end gap-1">
                            <RowAction
                              icon={Pencil}
                              title="Tahrirlash"
                              onClick={() => setEditFor(m)}
                            />
                            <RowAction
                              icon={Trash2}
                              title="O'chirish"
                              danger
                              onClick={() => setDeleteFor(m)}
                            />
                          </div>
                        </TableCell>
                      )}
                    </TableRow>
                  )
                })
              ) : (
                <EmptyRow colSpan={admin ? 5 : 4}>
                  Ish markazlari yo'q.
                </EmptyRow>
              )}
            </TableBody>
          </Table>
        </div>
      )}
      {(adding || editFor) && (
        <MachineDialog
          machine={editFor}
          posts={posts ?? []}
          machines={machines ?? []}
          onClose={() => {
            setAdding(false)
            setEditFor(null)
          }}
        />
      )}
      <DeleteMachine machine={deleteFor} onClose={() => setDeleteFor(null)} />
    </div>
  )
}

type FormState = {
  name: string
  post_id: string
  status: string
  capacity: string
  capacity_unit: string
  planned_minutes_per_day: string
  ideal_rate: string
}

function MachineDialog({
  machine,
  posts,
  machines,
  onClose,
}: {
  machine: MachineRead | null
  posts: PostRead[]
  machines: MachineRead[]
  onClose: () => void
}) {
  const editing = machine !== null
  const [form, setForm] = useState<FormState>({
    name: machine?.name ?? "",
    post_id: machine ? String(machine.post_id) : "",
    status: machine?.status ?? "active",
    capacity: machine?.capacity != null ? String(machine.capacity) : "",
    capacity_unit: machine?.capacity_unit ?? "",
    planned_minutes_per_day: String(machine?.planned_minutes_per_day ?? 480),
    ideal_rate: machine?.ideal_rate != null ? String(machine.ideal_rate) : "",
  })
  const set = (key: keyof FormState, value: string) =>
    setForm((f) => ({ ...f, [key]: value }))

  const capacityNumber = form.capacity
    ? Number(form.capacity.replace(",", "."))
    : null
  const capacityBad = capacityNumber !== null && Number.isNaN(capacityNumber)
  const idealNumber = form.ideal_rate
    ? Number(form.ideal_rate.replace(",", "."))
    : null
  const idealBad = idealNumber !== null && Number.isNaN(idealNumber)
  const plannedNumber = Number(form.planned_minutes_per_day)
  const plannedBad =
    Number.isNaN(plannedNumber) || plannedNumber < 1 || plannedNumber > 1440
  // Ideal tezlikning MA'NOSI postdan keladi — har post bitta birlikda ishlaydi
  const ideal =
    IDEAL_RATE_HINTS[
      posts.find((p) => String(p.id) === form.post_id)?.code ?? ""
    ]

  /** Post tanlanganda nom TAKLIF qilinadi: "Arra-1", "Arra-2"... Nom qo'lda
   * yoziladi — u monoblokda operatorga YOLG'IZ ko'rinadi, ya'ni stanokning
   * ustidagi haqiqiy yozuvga mos kelishi kerak ("Altendorf F45" ham bo'lishi
   * mumkin). Taklif faqat bo'sh maydonga qo'yiladi, yozilganini bosmaydi. */
  const pickPost = (postId: string) => {
    const post = posts.find((p) => String(p.id) === postId)
    setForm((f) => {
      if (!post || f.name.trim()) return { ...f, post_id: postId }
      const used = machines.filter((m) => m.post_id === post.id).length
      return { ...f, post_id: postId, name: `${post.name}-${used + 1}` }
    })
  }

  const queryClient = useQueryClient()
  const cb = crudCallbacks(
    queryClient,
    ["machines"],
    editing ? "Ish markazi saqlandi" : "Ish markazi qo'shildi",
  )
  const mutation = useMutation({
    mutationFn: () => {
      const body = {
        name: form.name.trim(),
        post_id: Number(form.post_id),
        status: form.status as MachineRead["status"],
        // O'zbek klaviaturasida o'nlik kasr VERGUL bilan yoziladi: Number("18,5")
        // NaN beradi, JSON uni null qiladi va tizim "saqlandi" deb yolg'on aytardi
        capacity: capacityNumber,
        // Quvvat berilib birlik tanlanmasa hisobot birligi noma'lum qolardi
        capacity_unit: form.capacity
          ? ((form.capacity_unit || "units_per_hour") as NonNullable<
              MachineRead["capacity_unit"]
            >)
          : null,
        planned_minutes_per_day: plannedNumber,
        ideal_rate: idealNumber,
      }
      return editing
        ? MachinesService.updateMachine({
            path: { machine_id: machine.id },
            body,
          })
        : MachinesService.createMachine({ body })
    },
    ...cb,
    onSuccess: () => {
      cb.onSuccess()
      onClose()
    },
  })

  const valid =
    form.name.trim().length > 1 &&
    form.post_id !== "" &&
    !capacityBad &&
    !idealBad &&
    !plannedBad

  return (
    <Dialog open onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>
            {editing ? machine.name : "Yangi ish markazi"}
          </DialogTitle>
          <DialogDescription>
            Quvvat boshqaruv panelidagi "Tugash" prognozini hisoblaydi:
            navbatdagi yuk ÷ quvvat
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-3">
          <Field label="Nomi">
            <Input
              value={form.name}
              onChange={(e) => set("name", e.target.value)}
              placeholder="01 ARRA"
              maxLength={100}
              autoFocus
            />
          </Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Post">
              <SelectField
                value={form.post_id}
                onChange={pickPost}
                placeholder="Postni tanlang"
                options={[...posts]
                  .sort((a, b) => a.order_index - b.order_index)
                  .map((p) => ({
                    value: String(p.id),
                    label: p.name,
                    hint: p.code,
                  }))}
              />
            </Field>
            <Field label="Holat">
              <SelectField
                value={form.status}
                onChange={(v) => set("status", v)}
                options={[
                  { value: "active", label: "AKTIV", hint: "ishlayapti" },
                  {
                    value: "repair",
                    label: "TA'MIRDA",
                    hint: "navbatda oxirgi turadi",
                  },
                  {
                    value: "inactive",
                    label: "NOAKTIV",
                    hint: "ish yo'naltirilmaydi",
                  },
                ]}
              />
            </Field>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Quvvat (soatiga)">
              <Input
                value={form.capacity}
                onChange={(e) =>
                  set("capacity", e.target.value.replace(/[^\d.,]/g, ""))
                }
                placeholder="18"
                inputMode="decimal"
                aria-invalid={capacityBad}
              />
              {capacityBad && (
                <span className="text-xs text-destructive">
                  Sonni kiriting, masalan 18.5
                </span>
              )}
            </Field>
            <Field label="Birlik">
              <SelectField
                value={form.capacity_unit}
                onChange={(v) => set("capacity_unit", v)}
                emptyLabel="dona/soat"
                options={Object.entries(CAPACITY_UNIT_LABELS).map(
                  ([value, label]) => ({ value, label }),
                )}
              />
            </Field>
          </div>

          {/* OEE — ikkalasi ham SHU ish markaziniki: bir postdagi ikki stanokning
              konfiguratsiyasi bir xil bo'lmaydi (turli model, turli tezlik) */}
          <div className="grid grid-cols-2 gap-3 rounded-md border border-dashed p-3">
            <Field label="Kunlik reja (daqiqa)">
              <Input
                value={form.planned_minutes_per_day}
                onChange={(e) =>
                  set(
                    "planned_minutes_per_day",
                    e.target.value.replace(/\D/g, ""),
                  )
                }
                placeholder="480"
                inputMode="numeric"
                aria-invalid={plannedBad}
              />
              <span className="text-2xs text-muted-foreground">
                {plannedBad
                  ? "1 dan 1440 gacha"
                  : `${(plannedNumber / 60).toFixed(1)} soat. Tushlik va tanaffus shundan ayriladi`}
              </span>
            </Field>
            <Field
              label={ideal ? `Ideal tezlik (${ideal.unit})` : "Ideal tezlik"}
            >
              <Input
                value={form.ideal_rate}
                onChange={(e) =>
                  set("ideal_rate", e.target.value.replace(/[^\d.,]/g, ""))
                }
                placeholder={ideal?.placeholder ?? "—"}
                inputMode="decimal"
                disabled={!ideal}
                aria-invalid={idealBad}
              />
              <span className="text-2xs text-muted-foreground">
                {idealBad
                  ? "Sonni kiriting, masalan 2.5"
                  : (ideal?.hint ??
                    "OEE faqat Arra, Kromka va Prisadka uchun hisoblanadi")}
              </span>
            </Field>
          </div>
        </div>

        <DialogFooter>
          <LoadingButton
            disabled={!valid}
            loading={mutation.isPending}
            onClick={() => mutation.mutate()}
          >
            Saqlash
          </LoadingButton>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function DeleteMachine({
  machine,
  onClose,
}: {
  machine: MachineRead | null
  onClose: () => void
}) {
  const queryClient = useQueryClient()
  const cb = crudCallbacks(queryClient, ["machines"], "Ish markazi o'chirildi")
  const mutation = useMutation({
    mutationFn: (id: number) =>
      MachinesService.deleteMachine({ path: { machine_id: id } }),
    ...cb,
    onSuccess: () => {
      cb.onSuccess()
      onClose()
    },
  })
  return (
    <ConfirmDialog
      open={!!machine}
      onOpenChange={(v) => !v && onClose()}
      title="Ish markazini o'chirish"
      // Server bog'lamni tekshiradi (hisob, agent, ochiq smena, tugallanmagan
      // marshrut) va sababni aytib rad etadi — bu yerda takrorlanmaydi
      description={
        machine
          ? `${machine.name} ro'yxatdan chiqadi. Skan tarixi joyida qoladi. Vaqtincha to'xtatish uchun o'chirish emas, "NOAKTIV" holati kerak.`
          : ""
      }
      confirmText="O'chirish"
      destructive
      loading={mutation.isPending}
      onConfirm={() => machine && mutation.mutate(machine.id)}
    />
  )
}
