// Brak — menejer ko'rib chiqadigan ro'yxat.
//
// Operator brakni belgilaydi, lekin detal ishlab chiqarishga O'ZIDAN O'ZI
// qaytmaydi: menejer ikki qarorni qabul qiladi va ular boshqa-boshqa savol.
//
//   AYBDOR post   Quality kimga yozilishini hal qiladi. Kromkachi arradan
//                 kelgan yaroqsiz detalni topsa, bu kromkaning ko'rsatkichini
//                 tushirmasligi kerak. Skan tarixidan taklif beriladi, lekin
//                 qarorni odam qabul qiladi.
//   QAYTA BOSHLASH  detal qaysi postdan qayta ishlanadi. Arra yoki roverdan
//                 boshlansa YANGI nusxa yaratiladi (chek o'sha ikki postda
//                 chiqadi), boshqasidan boshlansa bori to'g'rilanadi.

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { Check, X } from "lucide-react"
import { useState } from "react"
import { toast } from "sonner"

import {
  type DefectRead,
  DefectsService,
  type EmployeeRead,
  EmployeesService,
  type PostRead,
} from "@/client"
import { PageHeader } from "@/components/Common/PageHeader"
import { QueryError } from "@/components/Common/QueryError"
import { SelectField } from "@/components/Common/SelectField"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { LoadingButton } from "@/components/ui/loading-button"
import { Skeleton } from "@/components/ui/skeleton"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { requireAccess } from "@/lib/guards"
import { isManagement } from "@/lib/mes"
import { getPostsQueryOptions } from "@/queries/mes"
import { detailMessage } from "@/utils"

export const Route = createFileRoute("/_layout/defects")({
  component: DefectsPage,
  beforeLoad: requireAccess(isManagement),
  head: () => ({ meta: [{ title: "Brak | MebeliX" }] }),
})

const STATUS_LABEL: Record<string, string> = {
  pending: "KUTILMOQDA",
  approved: "TASDIQLANGAN",
  rejected: "RAD ETILGAN",
}

//: Yangi nusxa faqat shu postlardan qayta boshlanganda yaratiladi — chek aynan
//: shu ikki postda chiqadi (backend `defects.NEW_INSTANCE_POSTS`)
const NEW_INSTANCE_POSTS = ["ARRA", "ROVER"]

function DefectsPage() {
  const [status, setStatus] = useState<"pending" | "approved" | "rejected">(
    "pending",
  )
  const defects = useQuery({
    queryKey: ["defects", status],
    queryFn: async () =>
      (await DefectsService.readDefects({ query: { status } })).data,
  })
  const posts = useQuery(getPostsQueryOptions())
  const employees = useQuery({
    queryKey: ["employees", "all"],
    queryFn: async () =>
      (await EmployeesService.readEmployees({ query: { limit: 200 } })).data,
  })

  return (
    <div>
      <PageHeader
        title="Brak"
        description="Operator belgilagan yaroqsiz detallar — tasdiqlansa qayta ishlab chiqarishga ketadi"
      />
      <Tabs
        value={status}
        onValueChange={(v) => setStatus(v as typeof status)}
        className="mb-4"
      >
        <TabsList className="h-9">
          <TabsTrigger value="pending">Kutilmoqda</TabsTrigger>
          <TabsTrigger value="approved">Tasdiqlangan</TabsTrigger>
          <TabsTrigger value="rejected">Rad etilgan</TabsTrigger>
        </TabsList>
      </Tabs>

      {defects.isLoading ? (
        <Skeleton className="h-64 w-full" />
      ) : defects.isError ? (
        <QueryError onRetry={() => defects.refetch()} />
      ) : defects.data?.data.length ? (
        <div className="grid gap-3">
          {defects.data.data.map((d) => (
            <DefectCard
              key={d.id}
              defect={d}
              posts={posts.data ?? []}
              employees={employees.data?.data ?? []}
            />
          ))}
        </div>
      ) : (
        <p className="text-sm text-muted-foreground">
          {status === "pending"
            ? "Ko'rib chiqilmagan brak yo'q."
            : "Bu ro'yxat bo'sh."}
        </p>
      )}
    </div>
  )
}

function DefectCard({
  defect,
  posts,
  employees,
}: {
  defect: DefectRead
  posts: PostRead[]
  employees: EmployeeRead[]
}) {
  const queryClient = useQueryClient()
  const [blamedPost, setBlamedPost] = useState(
    defect.suggested_post_id ? String(defect.suggested_post_id) : "",
  )
  const [blamedEmployee, setBlamedEmployee] = useState(
    defect.suggested_employee_id ? String(defect.suggested_employee_id) : "",
  )
  const [restartPost, setRestartPost] = useState(
    defect.suggested_post_id ? String(defect.suggested_post_id) : "",
  )

  const done = () => {
    queryClient.invalidateQueries({ queryKey: ["defects"] })
    queryClient.invalidateQueries({ queryKey: ["orders"] })
  }
  const approve = useMutation({
    mutationFn: () =>
      DefectsService.approveDefect({
        path: { defect_id: defect.id },
        body: {
          blamed_post_id: Number(blamedPost),
          blamed_employee_id: blamedEmployee ? Number(blamedEmployee) : null,
          restart_post_id: Number(restartPost),
        },
      }),
    onSuccess: (r) => {
      toast.success(
        r.data.new_qr_text
          ? `Tasdiqlandi. Yangi nusxa: ${r.data.new_qr_text}`
          : "Tasdiqlandi. Detal qayta ishlashga qaytdi.",
      )
      done()
    },
    onError: (e) => toast.error(detailMessage(e)),
  })
  const reject = useMutation({
    mutationFn: () =>
      DefectsService.rejectDefect({ path: { defect_id: defect.id } }),
    onSuccess: () => {
      toast.success("Rad etildi")
      done()
    },
    onError: (e) => toast.error(detailMessage(e)),
  })

  const pending = defect.status === "pending"
  const restartCode = posts.find((p) => String(p.id) === restartPost)?.code
  const willClone = restartCode
    ? NEW_INSTANCE_POSTS.includes(restartCode)
    : false
  const postOptions = [...posts]
    .sort((a, b) => a.order_index - b.order_index)
    .map((p) => ({ value: String(p.id), label: p.name, hint: p.code }))

  return (
    <div className="rounded-lg border p-4">
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <span className="font-semibold">{defect.part_name}</span>
        <span className="num text-xs text-muted-foreground">
          {defect.qr_text}
        </span>
        <span className="text-xs text-muted-foreground">
          {defect.order_number}
        </span>
        <Badge variant={pending ? "default" : "secondary"} className="ml-auto">
          {STATUS_LABEL[defect.status]}
        </Badge>
      </div>

      <p className="mt-2 text-sm">{defect.reason}</p>
      <p className="mt-1 text-xs text-muted-foreground">
        {defect.found_post_name} postida topildi
        {defect.found_by_name && ` — ${defect.found_by_name}`}
        {(defect.route ?? []).length > 0 &&
          ` · marshrut: ${(defect.route ?? []).join(" → ")}`}
      </p>

      {/* "Kim chiqargan" savoliga javob SHU YERDA — taxmin emas, yozuv */}
      {(defect.history ?? []).length > 0 && (
        <div className="mt-3 rounded-md bg-muted/40 p-2.5">
          <div className="text-2xs font-bold uppercase tracking-wide text-muted-foreground">
            Skan tarixi
          </div>
          <div className="mt-1.5 grid gap-1">
            {(defect.history ?? []).map((h) => (
              <div
                key={`${h.post_name}-${h.at}`}
                className="flex flex-wrap items-baseline gap-x-2 text-xs"
              >
                <span className="font-medium">{h.post_name}</span>
                <span>{h.employee_name ?? "—"}</span>
                <span className="text-muted-foreground">{h.machine_name}</span>
                <span className="ml-auto num text-muted-foreground">
                  {new Date(h.at).toLocaleString("uz-UZ")}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {pending ? (
        <div className="mt-3 grid gap-3 border-t pt-3 sm:grid-cols-3">
          <label className="grid gap-1 text-sm">
            <span className="font-medium">Aybdor post</span>
            <SelectField
              value={blamedPost}
              onChange={setBlamedPost}
              placeholder="Tanlang"
              options={postOptions}
            />
          </label>
          <label className="grid gap-1 text-sm">
            <span className="font-medium">Aybdor hodim</span>
            <SelectField
              value={blamedEmployee}
              onChange={setBlamedEmployee}
              emptyLabel="ko'rsatilmaydi"
              options={employees.map((e) => ({
                value: String(e.id),
                label: e.full_name,
              }))}
            />
          </label>
          <label className="grid gap-1 text-sm">
            <span className="font-medium">Qaysi postdan qayta</span>
            <SelectField
              value={restartPost}
              onChange={setRestartPost}
              placeholder="Tanlang"
              options={postOptions}
            />
          </label>
          <div className="sm:col-span-3 flex flex-wrap items-center gap-2">
            {/* Oqibat OLDINDAN aytiladi: yangi nusxa yaratilishi buyurtma
                miqdorini oshiradi va buni bosishdan oldin bilish kerak */}
            <span className="text-xs text-muted-foreground">
              {restartPost
                ? willClone
                  ? "Yangi nusxa yaratiladi va yangi chek chiqadi"
                  : "Mavjud detal to'g'rilanadi, o'sha qadamdan keyingi scanlari bekor bo'ladi"
                : "Qayta boshlash postini tanlang"}
            </span>
            <div className="ml-auto flex gap-2">
              <Button
                variant="outline"
                disabled={reject.isPending}
                onClick={() => reject.mutate()}
              >
                <X /> Rad etish
              </Button>
              <LoadingButton
                disabled={!blamedPost || !restartPost}
                loading={approve.isPending}
                onClick={() => approve.mutate()}
              >
                <Check /> Tasdiqlash
              </LoadingButton>
            </div>
          </div>
        </div>
      ) : (
        <p className="mt-2 border-t pt-2 text-xs text-muted-foreground">
          {defect.blamed_post_name
            ? `Aybdor: ${defect.blamed_post_name}${defect.blamed_employee_name ? ` — ${defect.blamed_employee_name}` : ""}`
            : "Rad etilgan"}
          {defect.restart_post_name &&
            ` · ${defect.restart_post_name} dan qayta boshlandi`}
          {defect.new_qr_text && ` · yangi nusxa: ${defect.new_qr_text}`}
        </p>
      )}
    </div>
  )
}
