// Texnolog matritsasi (TZ 6.3.3): rows = parts, columns = 6 posts.
// Read mode: progress cells. Edit mode (texnolog, pre-production): stage toggles + notes.

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Link } from "@tanstack/react-router"
import { Map as MapIcon, Pencil, X } from "lucide-react"
import { useMemo, useState } from "react"

import { type MatrixPart, OrdersService, type PostRead } from "@/client"
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
}: {
  orderId: number
  editable: boolean
}) {
  const { data: matrix, isLoading } = useQuery(
    getOrderMatrixQueryOptions(orderId),
  )
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

  return (
    <div>
      {/* Bitta boshqaruv qatori: chapda qidiruv + hisob, o'ngda marshrut tugmalari —
          ikki alohida qator vertikal joyni isrof qilib, chetlarni notekis qilardi */}
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
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
            <Button
              variant="outline"
              size="sm"
              onClick={() => setEditMode(true)}
            >
              <Pencil /> Marshrutni tahrirlash
            </Button>
          ))}
      </div>
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
                    {/* Xaritada ko'rsat: detalning listi ochilib, katakchasi belgilanadi */}
                    <Link
                      to="/cutmap/$orderId"
                      params={{ orderId: String(orderId) }}
                      search={{ part: `${part.product_code}_${part.code}` }}
                      className="text-muted-foreground/50 hover:text-primary"
                      title="Kesish xaritasida ko'rsatish"
                    >
                      <MapIcon className="size-3.5" />
                    </Link>
                  </span>
                  <span className="block max-w-[220px] truncate text-xs text-muted-foreground">
                    {part.name}
                  </span>
                  {part.is_custom && (
                    <span
                      className="mt-0.5 inline-block rounded-sm bg-amber-100 px-1.5 py-0.5 text-2xs font-bold text-amber-900"
                      title="Marshrutini texnolog qo'lda chizadi — Nostandart detallar tabida."
                    >
                      {part.routes.length
                        ? `Nostandart · ${part.routes.length} qadam`
                        : "Nostandart · marshrut yo'q"}
                    </span>
                  )}
                </TableCell>
                <TableCell className="num whitespace-nowrap text-xs">
                  {formatSize(part.length, part.width, part.thickness)}
                </TableCell>
                <TableCell className="num text-center font-semibold">
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
                      onCheckedChange={(v) =>
                        setCustomEdits((prev) => ({
                          ...prev,
                          [part.id]: v === true,
                        }))
                      }
                      aria-label={`${part.code} nostandart`}
                    />
                  ) : part.is_custom ? (
                    <span className="font-bold text-amber-700">✓</span>
                  ) : (
                    <span className="text-muted-foreground/40">—</span>
                  )}
                </TableCell>
                <TableCell>
                  {editMode ? (
                    <Input
                      className="h-8 min-w-[120px] text-xs"
                      defaultValue={part.note ?? ""}
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
   *  backend qo'lda chizilgan marshrutga tegib qo'yardi. */
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
    // ARRA standart detal uchun majburiy (TZ 5.4.1).
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

  if (!steps.length) {
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
