// Texnolog matritsasi (TZ 6.3.3): rows = parts, columns = 6 posts.
// Read mode: progress cells. Edit mode (texnolog, pre-production): stage toggles + notes.

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Link } from "@tanstack/react-router"
import { Map as MapIcon, Pencil, X } from "lucide-react"
import { useMemo, useState } from "react"

import { OrdersService, type PostRead } from "@/client"
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
import useCustomToast from "@/hooks/useCustomToast"
import { formatSize, isCustomRoute, POST_COLORS } from "@/lib/mes"
import { getOrderMatrixQueryOptions, getPostsQueryOptions } from "@/queries/mes"
import { handleError } from "@/utils"

type StageEdits = Record<number, Record<number, boolean>> // part_id -> post_id -> enabled
type NoteEdits = Record<number, string>

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
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()

  const sortedPosts = useMemo(
    () => (posts ?? []).slice().sort((a, b) => a.order_index - b.order_index),
    [posts],
  )

  const mutation = useMutation({
    mutationFn: () => {
      const partIds = new Set(
        [...Object.keys(stageEdits), ...Object.keys(noteEdits)].map(Number),
      )
      return OrdersService.editOrderMatrix({
        orderId,
        requestBody: {
          edits: [...partIds].map((partId) => ({
            part_id: partId,
            note: noteEdits[partId] ?? null,
            stages: stageEdits[partId] ?? {},
          })),
        },
      })
    },
    onSuccess: () => {
      showSuccessToast("Matritsa saqlandi")
      setEditMode(false)
      setStageEdits({})
      setNoteEdits({})
    },
    onError: handleError(showErrorToast),
    onSettled: () =>
      queryClient.invalidateQueries({
        queryKey: ["orders", orderId, "matrix"],
      }),
  })

  if (isLoading) return <Skeleton className="h-48 w-full" />
  if (!matrix?.parts.length) {
    return (
      <p className="rounded-lg border border-dashed p-6 text-center text-sm text-muted-foreground">
        Detallar yo'q — avval .project fayl yuklanishi kerak.
      </p>
    )
  }

  const hasEdits =
    Object.keys(stageEdits).length > 0 || Object.keys(noteEdits).length > 0

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
              <Button
                variant="ghost"
                size="sm"
                onClick={() => {
                  setEditMode(false)
                  setStageEdits({})
                  setNoteEdits({})
                }}
              >
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
                  {/* Marshrut detal NOMIDAN olingan — qo'ldagi belgi keyingi
                      yuklashda yo'qoladi, chunki fayl marshrutni qayta quradi */}
                  {isCustomRoute(part.name) && (
                    <span
                      className="mt-0.5 inline-block rounded bg-amber-100 px-1.5 py-0.5 text-2xs font-bold text-amber-900"
                      title="Marshrut detal nomidagi kodlardan olingan. Bu yerda belgilagan o'zgarish faylni qayta yuklaganda yo'qoladi — marshrutni GibLab'da nomdan tuzating."
                    >
                      Marshrut nomdan
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
                    stageEdits={stageEdits}
                    setStageEdits={setStageEdits}
                  />
                ))}
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

type MatrixPartData = NonNullable<
  Awaited<ReturnType<typeof OrdersService.readOrderMatrix>>
>["parts"][number]

function MatrixCell({
  part,
  post,
  editMode,
  stageEdits,
  setStageEdits,
}: {
  part: MatrixPartData
  post: PostRead
  editMode: boolean
  stageEdits: StageEdits
  setStageEdits: React.Dispatch<React.SetStateAction<StageEdits>>
}) {
  const route = part.routes.find((r) => r.post_id === post.id)
  const color = POST_COLORS[post.code] ?? "var(--status-draft)"
  const edited = stageEdits[part.id]?.[post.id]
  const enabled = edited ?? (route ? route.is_enabled : false)

  if (editMode) {
    const locked = post.code === "ARRA" // majburiy bosqich (TZ 5.4.1)
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

  if (!route?.is_enabled) {
    return (
      <TableCell className="text-center text-muted-foreground/40">—</TableCell>
    )
  }
  const complete = route.total_done >= route.total_required
  return (
    <TableCell className="text-center">
      <span
        className="num inline-flex min-w-11 justify-center rounded-sm px-1.5 py-0.5 text-xs font-bold"
        style={{
          // Matn to'qroq variantda: sof post rangi o'z tinti ustida 3.65-5.11:1
          // berardi va aksariyat kombinatsiya AA dan o'tmasdi.
          color: `color-mix(in srgb, ${color} 78%, black)`,
          backgroundColor: `color-mix(in srgb, ${color} ${complete ? 22 : 10}%, white)`,
        }}
      >
        {complete ? "✓" : `${route.total_done}/${route.total_required}`}
      </span>
    </TableCell>
  )
}
