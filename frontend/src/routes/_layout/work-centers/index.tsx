// Ish markazlari: har postdagi stanok/joy — nom, post, holat + JONLI ustunlar
// (`/machines/overview`): stanok signal ustuni (andon), kim biriktirilgan, smenada
// nechta odam, bugungi skan, oxirgi skan, biriktirilgan tugallanmagan qadamlar.
// Admin uchun CRUD.

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute, Link } from "@tanstack/react-router"
import { Pencil, Plus, Trash2 } from "lucide-react"
import { useEffect, useState } from "react"

import {
  type MachineOverview,
  type MachineRead,
  MachinesService,
  type PostRead,
} from "@/client"
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
import { KromkaLive } from "@/components/WorkCenters/KromkaLive"
import { useCurrentUser } from "@/hooks/useCurrentUser"
import { useMesWs } from "@/hooks/useMesWs"
import { requireAccess } from "@/lib/guards"
import {
  ANDON_STATE_LABELS,
  ANDON_STYLE,
  formatAgo,
  formatDateTime,
  formatSince,
  isAdmin,
  isProductionStaff,
  MACHINE_STATUS_LABELS,
} from "@/lib/mes"
import { cn } from "@/lib/utils"
import {
  crudCallbacks,
  getMachinesQueryOptions,
  getPostsQueryOptions,
} from "@/queries/mes"

export const Route = createFileRoute("/_layout/work-centers/")({
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

/** O'chirishga to'siqlar tugma bosilmasdan OLDIN (title) — server `_blockers` ning
 * taxminiy nusxasi. Ochiq smena `on_shift` dan olinadi, u faqat BUGUN ochilgan
 * smenalarni sanaydi: kechadan qolgan smenada tugma faol, server esa 409 beradi. */
function blockers(o: MachineOverview | undefined): string[] {
  if (!o) return []
  const out: string[] = []
  if (o.accounts.length)
    out.push(`biriktirilgan hisob: ${o.accounts.join(", ")}`)
  if (o.agents.length) out.push(`MES agenti: ${o.agents.join(", ")}`)
  if (o.on_shift) out.push(`ochiq smena: ${o.on_shift} ta`)
  if (o.unfinished_routes)
    out.push(`tugallanmagan marshrut: ${o.unfinished_routes} ta`)
  return out
}

function WorkCentersPage() {
  const machinesQ = useQuery(getMachinesQueryOptions())
  const postsQ = useQuery(getPostsQueryOptions())
  // Jonli ustunlar alohida so'rov: `MachineRead` ro'yxati har select'da
  // ishlatiladi, unga statistika yuklab bo'lmaydi
  const { data: overview } = useQuery({
    queryKey: ["machines", "overview"],
    queryFn: async () => (await MachinesService.readMachinesOverview()).data,
    refetchInterval: 60_000,
  })
  // Stanok holati o'zgarishi bilan jadval darhol yangilanadi — 60 s pollni kutmaydi
  const queryClient = useQueryClient()
  useMesWs((event) => {
    if (event.type === "andon.state")
      queryClient.invalidateQueries({ queryKey: ["machines", "overview"] })
  })
  // "12 daq" matni holat o'zgarmasa ham o'sib borsin (so'rov ma'lumoti o'zgarmasa
  // komponent qayta chizilmaydi)
  const [, setTick] = useState(0)
  useEffect(() => {
    const t = setInterval(() => setTick((n) => n + 1), 30_000)
    return () => clearInterval(t)
  }, [])
  const machines = machinesQ.data
  const posts = postsQ.data
  // Postlarsiz jadval buzuq chiqadi (bo'sh Post ustuni, noto'g'ri tartib),
  // shuning uchun ikkala so'rov ham yuklanish/xato holatini boshqaradi
  const isLoading = machinesQ.isLoading || postsQ.isLoading
  const isError = machinesQ.isError || postsQ.isError
  const { currentUser } = useCurrentUser()
  const admin = isAdmin(currentUser)
  const [adding, setAdding] = useState(false)
  const [editFor, setEditFor] = useState<MachineRead | null>(null)
  const [deleteFor, setDeleteFor] = useState<MachineRead | null>(null)
  const postById = new Map((posts ?? []).map((p) => [p.id, p]))
  const ovById = new Map((overview ?? []).map((o) => [o.machine_id, o]))
  // Marshrut tartibida: ARRA, KROMKA, OVAL... Ilgari id tartibida chiqardi,
  // ya'ni yangi qo'shilgan arra ro'yxat oxirida, o'z posti yonida emas edi
  const sorted = [...(machines ?? [])].sort(
    (a, b) =>
      (postById.get(a.post_id)?.order_index ?? 0) -
        (postById.get(b.post_id)?.order_index ?? 0) ||
      a.name.localeCompare(b.name),
  )
  const colSpan = admin ? 9 : 8

  return (
    <div>
      <PageHeader
        title="Ish markazlari"
        description="Har postdagi stanok yoki ish joyi — smena shu yerda ochiladi, skan shu nomdan yoziladi"
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
        <QueryError
          onRetry={() => {
            machinesQ.refetch()
            postsQ.refetch()
          }}
        />
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Ish markazi</TableHead>
              <TableHead>Post</TableHead>
              <TableHead>Holat</TableHead>
              <TableHead title="Stanok signal ustuni (andon) — chiroqlarni Pico o'qiydi, MES agenti yuboradi. Jonli: holat va qancha vaqtdan beri">
                Stanok
              </TableHead>
              <TableHead
                className="text-right"
                title="Bugun beyjik bilan ochilgan, hali yopilmagan smenalar"
              >
                Smenada
              </TableHead>
              <TableHead className="text-right" title="Bugungi skanlar">
                Bugun
              </TableHead>
              <TableHead>Oxirgi skan</TableHead>
              <TableHead
                className="text-right"
                title="Terminal navbati bilan bir xil: shu markazga biriktirilgan + postning biriktirilmagan ishi — qolgan skanlar"
              >
                Navbatda
              </TableHead>
              {admin && <TableHead className="w-20" />}
            </TableRow>
          </TableHeader>
          <TableBody>
            {sorted.length ? (
              sorted.map((m) => {
                const post = postById.get(m.post_id)
                const o = ovById.get(m.id)
                const locks = blockers(o)
                const quiet = !o?.today_scans && !o?.on_shift
                return (
                  <TableRow key={m.id}>
                    <TableCell>
                      {/* Nom — markazning O'Z sahifasiga havola: tsexda odam
                          «stanok hozir nima qilyapti» ni stanokdan izlaydi, va
                          sozlamalari ham o'sha sahifaning tabida (oyna emas). */}
                      <Link
                        to="/work-centers/$machineId"
                        params={{ machineId: String(m.id) }}
                        className="font-medium underline-offset-4 hover:underline"
                        title="Ish markazi sahifasi: joriy ish, oxirgi amallar, sozlamalar"
                      >
                        {m.name}
                      </Link>
                      {/* Bog'lamlar nom ostida: agent (onlayn nuqtasi bilan) va
                          qurilma hisobi — ular o'chirishga ham to'siq */}
                      {o && (o.agents.length > 0 || o.accounts.length > 0) && (
                        <div className="flex flex-wrap items-center gap-x-2 text-xs text-muted-foreground">
                          {o.agents.length > 0 && (
                            <span className="inline-flex items-center gap-1">
                              <span
                                className={cn(
                                  "inline-block size-1.5 rounded-full",
                                  o.agent_online
                                    ? "bg-emerald-500"
                                    : "bg-muted-foreground/40",
                                )}
                                title={
                                  o.agent_online
                                    ? "agent onlayn"
                                    : "agent oflayn"
                                }
                              />
                              agent: {o.agents.join(", ")}
                            </span>
                          )}
                          {o.accounts.length > 0 && (
                            <span>hisob: {o.accounts.join(", ")}</span>
                          )}
                        </div>
                      )}
                    </TableCell>
                    <TableCell>
                      {post && <PostBadge code={post.code} />}
                    </TableCell>
                    <TableCell>
                      <Badge
                        variant={m.status === "active" ? "default" : "outline"}
                        className={STATUS_STYLE[m.status]}
                      >
                        {MACHINE_STATUS_LABELS[m.status]}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      {o?.andon_state ? (
                        <div>
                          <Badge
                            variant="outline"
                            className={cn(
                              "gap-1.5",
                              ANDON_STYLE[o.andon_state] ??
                                "border-transparent bg-muted text-muted-foreground",
                            )}
                          >
                            <span
                              className={cn(
                                "inline-block size-1.5 rounded-full bg-current",
                                o.andon_state === "AWAIT_PART" &&
                                  "motion-safe:animate-pulse",
                              )}
                            />
                            {ANDON_STATE_LABELS[o.andon_state] ?? o.andon_state}
                          </Badge>
                          {o.andon_since && (
                            <div className="num text-xs text-muted-foreground">
                              {formatSince(o.andon_since)}
                            </div>
                          )}
                        </div>
                      ) : (
                        // Signal ustuni ulanmagan stanok ham, aloqasi uzilgani ham shu
                        // ko'rinishda: server 90 s xabar olmasa holatni o'zi o'chiradi
                        <span
                          className="text-muted-foreground"
                          title="Signal ustuni ulanmagan yoki MES agentidan 90 soniyadan beri xabar yo'q"
                        >
                          —
                        </span>
                      )}
                    </TableCell>
                    <TableCell className="num text-right">
                      {o?.on_shift ? (
                        <span className="font-semibold">
                          {o.on_shift}{" "}
                          <span className="font-normal text-muted-foreground">
                            hodim
                          </span>
                        </span>
                      ) : (
                        <span className="text-muted-foreground">—</span>
                      )}
                    </TableCell>
                    <TableCell className="num text-right">
                      {o?.today_scans ? (
                        <span className="font-semibold">{o.today_scans}</span>
                      ) : (
                        <span className="text-muted-foreground">0</span>
                      )}
                    </TableCell>
                    <TableCell
                      className={cn(
                        "num",
                        quiet ? "text-muted-foreground" : "",
                      )}
                    >
                      {o?.last_scan_at ? (
                        <>
                          <div>{formatDateTime(o.last_scan_at)}</div>
                          <div className="text-xs text-muted-foreground">
                            {formatAgo(o.last_scan_at)}
                          </div>
                        </>
                      ) : (
                        <span className="text-muted-foreground">
                          hali skan yo'q
                        </span>
                      )}
                    </TableCell>
                    <TableCell className="num text-right">
                      {/* Boshqaruv paneli «navbatda» bilan bir birlik (qolgan skan);
                          biriktirilgan qadamlar soni o'chirish to'sig'ida qoladi */}
                      {o?.queue_scans ? (
                        <span>
                          {o.queue_scans}{" "}
                          <span className="text-muted-foreground">skan</span>
                        </span>
                      ) : (
                        <span className="text-muted-foreground">—</span>
                      )}
                    </TableCell>
                    {admin && (
                      <TableCell>
                        <div className="flex justify-end gap-1">
                          <RowAction
                            icon={Pencil}
                            title="Tahrirlash"
                            onClick={() => setEditFor(m)}
                          />
                          {/* Server bog'lam bo'lsa 409 beradi; shu sabab tugma
                              bosilmasdan oldin ko'rinsin */}
                          <RowAction
                            icon={Trash2}
                            title={
                              locks.length
                                ? `O'chirib bo'lmaydi — ${locks.join("; ")}. Vaqtincha to'xtatish uchun NOAKTIV holati.`
                                : "O'chirish"
                            }
                            danger
                            disabled={locks.length > 0}
                            onClick={() => setDeleteFor(m)}
                          />
                        </div>
                      </TableCell>
                    )}
                  </TableRow>
                )
              })
            ) : (
              <EmptyRow colSpan={colSpan}>Ish markazlari yo'q.</EmptyRow>
            )}
          </TableBody>
        </Table>
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
      {/* Kromka stansiyasi o'lchovlari — jadval ostida, jonli. Stansiya yo'q bo'lsa
          butun blok chizilmaydi (komponentning o'zi qaror qiladi). */}
      <KromkaLive />
      <DeleteMachine machine={deleteFor} onClose={() => setDeleteFor(null)} />
    </div>
  )
}

type FormState = {
  name: string
  post_id: string
  status: string
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
  })
  const set = (key: keyof FormState, value: string) =>
    setForm((f) => ({ ...f, [key]: value }))

  /** Post tanlanganda nom TAKLIF qilinadi: "Arra-1", "Arra-2"... Nom qo'lda
   * yoziladi — u monoblokda operatorga YOLG'IZ ko'rinadi, ya'ni stanokning
   * ustidagi haqiqiy yozuvga mos kelishi kerak ("Altendorf F45" ham bo'lishi
   * mumkin). Taklif faqat bo'sh maydonga qo'yiladi, yozilganini bosmaydi. */
  const pickPost = (postId: string) => {
    const post = posts.find((p) => String(p.id) === postId)
    setForm((f) => {
      if (!post || f.name.trim()) return { ...f, post_id: postId }
      // Sanoq emas, birinchi BO'SH suffiks: o'chirishdan keyin sanoq mavjud
      // nomni taklif qilardi. Nom butun tsex bo'yicha unikal (backend
      // registrsiz solishtiradi), shuning uchun hamma stanok tekshiriladi.
      let n = 1
      const taken = new Set(machines.map((m) => m.name.toLowerCase()))
      while (taken.has(`${post.name}-${n}`.toLowerCase())) n++
      return { ...f, post_id: postId, name: `${post.name}-${n}` }
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

  const valid = form.name.trim().length > 1 && form.post_id !== ""

  return (
    <Dialog open onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>
            {editing ? machine.name : "Yangi ish markazi"}
          </DialogTitle>
        </DialogHeader>

        <div className="grid gap-3">
          {/* Avval POST: nom taklifi postdan keladi (ilgari nom birinchi turardi
              va taklif hech qachon ishlamasdi — nom allaqachon yozilgan bo'lardi) */}
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
          <div className="grid grid-cols-2 gap-3">
            <Field label="Nomi">
              <Input
                value={form.name}
                onChange={(e) => set("name", e.target.value)}
                placeholder="Arra-1"
                maxLength={100}
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
          <p className="text-xs text-muted-foreground">
            Nom monoblokda operatorga ko'rinadi — stanok ustidagi yozuvga mos
            bo'lsin. Skan tarixi bor markazning posti keyin o'zgartirilmaydi.
          </p>
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
