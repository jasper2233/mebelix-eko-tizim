// Texnolog matritsasi: rows = parts, columns = 6 posts.
// Read mode: progress cells. Edit mode (texnolog, pre-production): stage toggles + notes.

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Pencil, X } from "lucide-react"
import { useMemo, useState } from "react"
import { createPortal } from "react-dom"

import { type MatrixPart, OrdersService, type PostRead } from "@/client"
import { QueryError } from "@/components/Common/QueryError"
import { PartMapButton } from "@/components/Orders/PartMapDialog"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
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
import {
  chipColors,
  formatSize,
  POST_COLORS,
  routeStepNames,
  STANDARD_MATRIX_POSTS,
} from "@/lib/mes"
import {
  crudCallbacks,
  getOrderMatrixQueryOptions,
  getPostsQueryOptions,
} from "@/queries/mes"

type StageEdits = Record<number, Record<number, boolean>> // part_id -> post_id -> enabled
type NoteEdits = Record<number, string>
type CustomEdits = Record<number, boolean> // part_id -> nostandart

export function OrderMatrix({
  orderId,
  editable,
  toolbarContainer,
}: {
  orderId: number
  editable: boolean
  /** Boshqaruv qatori (qidiruv + hisob + tahrir tugmalari) shu elementga portal
   *  qilinadi — buyurtma sahifasida tab'lar qatorining o'ng tomoni, alohida
   *  qator o'rniga. Berilmasa jadval ustida o'z qatorida. */
  toolbarContainer?: HTMLElement | null
}) {
  const {
    data: matrix,
    isLoading,
    isError,
    refetch,
  } = useQuery(getOrderMatrixQueryOptions(orderId))
  const { data: posts } = useQuery(getPostsQueryOptions())
  const [editMode, setEditMode] = useState(false)
  const [query, setQuery] = useState("")
  const [stageEdits, setStageEdits] = useState<StageEdits>({})
  const [noteEdits, setNoteEdits] = useState<NoteEdits>({})
  const [customEdits, setCustomEdits] = useState<CustomEdits>({})
  const exitEdit = () => {
    setEditMode(false)
    setStageEdits({})
    setNoteEdits({})
    setCustomEdits({})
  }
  const queryClient = useQueryClient()
  const cb = crudCallbacks(
    queryClient,
    ["orders", orderId, "matrix"],
    "Matritsa saqlandi",
  )

  // Faqat standart detalning postlari. Qolganlari nostandart tabda chiziladi —
  // matritsada ular hech qachon to'lmaydigan bo'sh ustun bo'lib turardi.
  const sortedPosts = useMemo(
    () =>
      (posts ?? [])
        .filter((p) => STANDARD_MATRIX_POSTS.includes(p.code))
        .sort((a, b) => a.order_index - b.order_index),
    [posts],
  )

  const mutation = useMutation({
    mutationFn: () => {
      const partIds = new Set(
        [
          ...Object.keys(stageEdits),
          ...Object.keys(noteEdits),
          ...Object.keys(customEdits),
        ].map(Number),
      )
      return OrdersService.editOrderMatrix({
        path: { order_id: orderId },
        body: {
          edits: [...partIds].map((partId) => ({
            part_id: partId,
            note: noteEdits[partId] ?? null,
            stages: stageEdits[partId] ?? {},
            is_custom: customEdits[partId] ?? null,
          })),
        },
      })
    },
    ...cb,
    onSuccess: () => {
      cb.onSuccess()
      exitEdit()
    },
  })

  if (isLoading) return <Skeleton className="h-48 w-full" />
  // Xatoni bo'sh holatdan oldin tekshiramiz: 500 da "detal yo'q" deyish
  // texnologni yo'q faylni qayta yuklashga majburlardi.
  if (isError) return <QueryError onRetry={() => refetch()} />
  if (!matrix?.parts.length) {
    return (
      <p className="rounded-xl border border-dashed p-6 text-center text-sm text-muted-foreground">
        Detallar yo'q — avval .project fayl yuklanishi kerak.
      </p>
    )
  }

  const hasEdits =
    Object.keys(stageEdits).length > 0 ||
    Object.keys(noteEdits).length > 0 ||
    Object.keys(customEdits).length > 0

  const q = query.trim().toLowerCase()
  const visibleParts = q
    ? matrix.parts.filter((p) =>
        `${p.product_code}_${p.code} ${p.name}`.toLowerCase().includes(q),
      )
    : matrix.parts

  // Bitta boshqaruv qatori: qidiruv + hisob + marshrut tugmalari. Portal berilsa
  // tab'lar qatoriga (o'ngga) chiqadi — jadval ustida alohida qator qolmaydi.
  const toolbar = (
    <div
      className={
        toolbarContainer
          ? "flex flex-wrap items-center justify-end gap-2"
          : "mb-3 flex flex-wrap items-center justify-between gap-2"
      }
    >
      <div className="flex items-center gap-2">
        <Input
          className="h-8 w-56 text-sm"
          placeholder="Qidirish: kod yoki nom..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <span className="whitespace-nowrap text-xs text-muted-foreground">
          {q
            ? `${visibleParts.length} / ${matrix.parts.length} detal`
            : `${matrix.parts.length} detal`}
        </span>
      </div>
      {editable &&
        (editMode ? (
          <div className="flex items-center gap-2">
            <Button variant="ghost" size="sm" onClick={exitEdit}>
              <X /> Bekor qilish
            </Button>
            <LoadingButton
              size="sm"
              loading={mutation.isPending}
              disabled={!hasEdits}
              onClick={() => mutation.mutate()}
            >
              Saqlash
            </LoadingButton>
          </div>
        ) : (
          <Button variant="outline" size="sm" onClick={() => setEditMode(true)}>
            <Pencil /> Marshrutni tahrirlash
          </Button>
        ))}
    </div>
  )

  return (
    <div>
      {toolbarContainer ? createPortal(toolbar, toolbarContainer) : toolbar}
      {/* Balandlik chegaralangan: uzun buyurtmada butun sahifa emas, jadval o'zi
          aylanadi, sarlavha esa yopishqoq — prisadkachi qaysi ustun ekanini yo'qotmaydi.
          Scroll konteyner — Table'ning o'z o'rami (data-slot), aks holda sticky ishlamaydi */}
      <div className="[&_[data-slot=table-container]]:max-h-[70vh] [&_[data-slot=table-container]]:overflow-y-auto">
        <Table>
          <TableHeader className="sticky top-0 z-10 bg-background shadow-[0_1px_0_var(--border)]">
            <TableRow>
              <TableHead className="min-w-[180px]">Detal</TableHead>
              <TableHead>O'lchami</TableHead>
              <TableHead className="text-center">Soni</TableHead>
              {sortedPosts.map((p) => (
                <TableHead
                  key={p.id}
                  className="text-center"
                  style={{ color: POST_COLORS[p.code] }}
                >
                  {p.code}
                </TableHead>
              ))}
              <TableHead className="text-center">Nostandart</TableHead>
              <TableHead>Izoh</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {visibleParts.map((part) => (
              <TableRow key={part.id}>
                <TableCell>
                  <span className="flex items-center gap-1.5">
                    <span className="font-medium">
                      {part.product_code}_{part.code}
                    </span>
                    {/* Xaritani shu yerda ko'rish (dialog) — sahifadan chiqilmaydi */}
                    <PartMapButton
                      orderId={orderId}
                      partKey={`${part.product_code}_${part.code}`}
                    />
                  </span>
                  <span className="block max-w-[220px] truncate text-xs text-muted-foreground">
                    {part.name}
                  </span>
                </TableCell>
                <TableCell className="num whitespace-nowrap text-xs">
                  {formatSize(part.length, part.width, part.thickness)}
                </TableCell>
                <TableCell
                  className={`num text-center ${part.count === 0 ? "text-muted-foreground/60" : "font-semibold"}`}
                  title={
                    part.count === 0
                      ? "Faylda soni 0 — ishlab chiqarilmaydi"
                      : undefined
                  }
                >
                  {part.count}
                </TableCell>
                {sortedPosts.map((post) => (
                  <MatrixCell
                    key={post.id}
                    part={part}
                    post={post}
                    editMode={editMode}
                    isCustom={customEdits[part.id] ?? part.is_custom}
                    stageEdits={stageEdits}
                    setStageEdits={setStageEdits}
                  />
                ))}
                <TableCell className="text-center">
                  {editMode ? (
                    <Checkbox
                      checked={customEdits[part.id] ?? part.is_custom}
                      onCheckedChange={(v) => {
                        setCustomEdits((prev) => ({
                          ...prev,
                          [part.id]: v === true,
                        }))
                        // Bayroq almashgach shu detalning kutayotgan bosqich
                        // tanlovlari kuchini yo'qotadi: bitta saqlashda ular
                        // backend qayta qurgan marshrutga tegib ketardi.
                        setStageEdits((prev) => {
                          const { [part.id]: _dropped, ...rest } = prev
                          return rest
                        })
                      }}
                      aria-label={`${part.code} nostandart`}
                    />
                  ) : part.is_custom ? (
                    // «✓» hech narsa demasdi — endi marshrutning o'zi, BITTA
                    // satr («Raspil → Kromka → G petlya o'ngdan»): chiplar tor
                    // ustunda har biri alohida qatorga tushib, qatorni cho'zardi.
                    // Nom ostidagi «Nostandart» belgisi olib tashlandi — ustunning
                    // o'zi aytadi: marshrut bor (matn) yoki «marshrut yo'q» (amber).
                    routeStepNames(part.routes).length ? (
                      <span
                        className="block max-w-[260px] truncate text-xs"
                        title={routeStepNames(part.routes).join(" → ")}
                      >
                        {routeStepNames(part.routes).join(" → ")}
                      </span>
                    ) : (
                      <span
                        className="text-xs font-medium text-amber-700"
                        title="Marshrutini texnolog Nostandart detallar tabida chizadi"
                      >
                        marshrut yo'q
                      </span>
                    )
                  ) : (
                    <span className="text-muted-foreground/40">—</span>
                  )}
                </TableCell>
                <TableCell>
                  {editMode ? (
                    <Input
                      className="h-8 min-w-[120px] text-xs"
                      value={noteEdits[part.id] ?? part.note ?? ""}
                      placeholder="Izoh..."
                      onChange={(e) =>
                        setNoteEdits((prev) => ({
                          ...prev,
                          [part.id]: e.target.value,
                        }))
                      }
                    />
                  ) : (
                    <span className="text-xs text-muted-foreground">
                      {part.note ?? ""}
                    </span>
                  )}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  )
}

function MatrixCell({
  part,
  post,
  editMode,
  isCustom,
  stageEdits,
  setStageEdits,
}: {
  part: MatrixPart
  post: PostRead
  editMode: boolean
  /** Tahrirdagi holat (serverdagi emas): checkbox belgilangan zahoti katakchalar
   *  qulflansin — aks holda bitta saqlashda is_custom va stages birga ketib,
   *  backend qo'lda chizilgan marshrutga tegib qo'yardi. Qulf faqat KEYINGI
   *  bosishlarni to'xtatadi; allaqachon belgilangan bosqichlarni checkbox'ning
   *  o'zi `stageEdits` dan olib tashlaydi. */
  isCustom: boolean
  stageEdits: StageEdits
  setStageEdits: React.Dispatch<React.SetStateAction<StageEdits>>
}) {
  // Post marshrutda takrorlanishi mumkin (kromka -> prisadka -> kromka) —
  // katakcha shu postdagi BARCHA qadamlarni birga ko'rsatadi.
  const steps = part.routes.filter((r) => r.post_id === post.id && r.is_enabled)
  const color = POST_COLORS[post.code] ?? "var(--status-draft)"
  const edited = stageEdits[part.id]?.[post.id]
  const enabled = edited ?? steps.length > 0

  if (editMode) {
    // Nostandart detalning marshruti alohida tabda chiziladi — bu yerda tegilmaydi.
    // ARRA standart detal uchun majburiy.
    const locked = isCustom || post.code === "ARRA"
    return (
      <TableCell className="text-center">
        <Checkbox
          checked={enabled}
          disabled={locked}
          onCheckedChange={(v) =>
            setStageEdits((prev) => ({
              ...prev,
              [part.id]: { ...prev[part.id], [post.id]: v === true },
            }))
          }
          aria-label={`${part.code} ${post.code}`}
        />
      </TableCell>
    )
  }

  // Soni 0 detal (faylda shunday keladi): 0/0 "✓" bo'lib "tayyor" degan
  // yolg'on taassurot berardi — ishlab chiqarilmaydi, katak bo'sh.
  if (!steps.length || part.count === 0) {
    return (
      <TableCell className="text-center text-muted-foreground/40">—</TableCell>
    )
  }
  const route = steps.reduce(
    (acc, s) => ({
      total_done: acc.total_done + s.total_done,
      total_required: acc.total_required + s.total_required,
    }),
    { total_done: 0, total_required: 0 },
  )
  const complete = route.total_done >= route.total_required
  return (
    <TableCell className="text-center">
      <span
        className="num inline-flex min-w-11 justify-center rounded-sm px-1.5 py-0.5 text-xs font-bold"
        // Tugallangan katak to'qroq fonda ajralib tursin (22% vs 10%).
        style={chipColors(color, complete ? 22 : 10)}
      >
        {complete ? "✓" : `${route.total_done}/${route.total_required}`}
      </span>
    </TableCell>
  )
}
