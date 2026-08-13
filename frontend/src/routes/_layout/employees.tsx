import { zodResolver } from "@hookform/resolvers/zod"
import {
  keepPreviousData,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { IdCard, Pencil, Plus, Printer, Trash2 } from "lucide-react"
import { QRCodeSVG } from "qrcode.react"
import { useState } from "react"
import { type Control, useForm } from "react-hook-form"
import { toast } from "sonner"
import { z } from "zod"

import { type EmployeeRead, EmployeesService } from "@/client"
import { ConfirmDialog } from "@/components/Common/ConfirmDialog"
import { EmptyRow } from "@/components/Common/EmptyRow"
import { PageHeader } from "@/components/Common/PageHeader"
import { PostBadge } from "@/components/Common/PostBadge"
import { QueryError } from "@/components/Common/QueryError"
import { SearchInput } from "@/components/Common/SearchInput"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form"
import { Input } from "@/components/ui/input"
import { LoadingButton } from "@/components/ui/loading-button"
import { Skeleton } from "@/components/ui/skeleton"
import { Switch } from "@/components/ui/switch"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { useCurrentUser } from "@/hooks/useCurrentUser"
import { useDebounced } from "@/hooks/useDebounced"
import { requireAccess } from "@/lib/guards"
import {
  EMPLOYEE_STATUS_LABELS,
  isAdmin,
  isManagement,
  POST_COLORS,
} from "@/lib/mes"
import { formatUzPhone, optionalFormattedPhoneSchema } from "@/lib/validation"
import {
  crudCallbacks,
  getEmployeesQueryOptions,
  getPostsQueryOptions,
} from "@/queries/mes"
import { detailMessage } from "@/utils"

export const Route = createFileRoute("/_layout/employees")({
  component: EmployeesPage,
  // Sidebar ko'rinishi bilan bir xil rollar to'plami (lib/mes)
  beforeLoad: requireAccess(isManagement),
  head: () => ({ meta: [{ title: "Hodimlar | MebeliX" }] }),
})

const formSchema = z.object({
  full_name: z.string().trim().min(2, "Kamida 2 belgi").max(100),
  phone: optionalFormattedPhoneSchema,
  position: z.string().max(50).optional(),
  assigned_post_ids: z.array(z.number()).min(1, "Kamida bitta post tanlang"),
})

/** Qo'shish va tahrirlash dialoglaridagi bir xil maydonlar. Ikkalasi ham bitta
 * formSchema'ga tayanadi: maydon qo'shilsa u avtomat ikkala dialogda chiqadi. */
function EmployeeFields({
  control,
}: {
  control: Control<z.infer<typeof formSchema>>
}) {
  // TanStack bir xil kalit bo'yicha dedupe qiladi — dialog o'zi so'rasa ham qo'shimcha so'rov ketmaydi
  const { data: posts } = useQuery(getPostsQueryOptions())

  return (
    <>
      <FormField
        control={control}
        name="full_name"
        render={({ field }) => (
          <FormItem>
            <FormLabel>F.I.Sh</FormLabel>
            <FormControl>
              <Input {...field} autoFocus />
            </FormControl>
            <FormMessage />
          </FormItem>
        )}
      />
      <div className="grid grid-cols-2 gap-3">
        <FormField
          control={control}
          name="phone"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Telefon</FormLabel>
              <FormControl>
                <Input
                  {...field}
                  type="tel"
                  inputMode="numeric"
                  placeholder="+998 90 123-45-67"
                  onChange={(e) =>
                    field.onChange(formatUzPhone(e.target.value, field.value))
                  }
                />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
        <FormField
          control={control}
          name="position"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Lavozim</FormLabel>
              <FormControl>
                <Input {...field} placeholder="ISHCHI XODIM" />
              </FormControl>
            </FormItem>
          )}
        />
      </div>
      <FormField
        control={control}
        name="assigned_post_ids"
        render={({ field }) => (
          <FormItem>
            <FormLabel>Qaysi postlarda ishlaydi</FormLabel>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
              {(posts ?? []).map((p) => (
                <div
                  key={p.id}
                  className="flex items-center gap-2 rounded-lg border p-2 text-sm"
                >
                  <Checkbox
                    checked={field.value.includes(p.id)}
                    aria-label={p.code}
                    onCheckedChange={(v) =>
                      field.onChange(
                        v === true
                          ? [...field.value, p.id]
                          : field.value.filter((x) => x !== p.id),
                      )
                    }
                  />
                  <span
                    style={{ color: POST_COLORS[p.code] }}
                    className="font-semibold"
                  >
                    {p.code}
                  </span>
                </div>
              ))}
            </div>
            <FormMessage />
          </FormItem>
        )}
      />
    </>
  )
}

function EmployeesPage() {
  const [search, setSearch] = useState("")
  const [badgeFor, setBadgeFor] = useState<EmployeeRead | null>(null)
  const [editFor, setEditFor] = useState<EmployeeRead | null>(null)
  const [deleteFor, setDeleteFor] = useState<EmployeeRead | null>(null)
  const debounced = useDebounced(search.trim())
  const { data, isLoading, isError, refetch } = useQuery({
    ...getEmployeesQueryOptions(debounced),
    placeholderData: keepPreviousData,
  })
  const { data: posts } = useQuery(getPostsQueryOptions())
  const { currentUser } = useCurrentUser()
  const admin = isAdmin(currentUser)
  const postById = new Map((posts ?? []).map((p) => [p.id, p]))

  return (
    <div>
      <PageHeader
        title="Hodimlar"
        description="Sex ishchilari — beyjik QR orqali aniqlanadi"
        actions={admin ? <AddEmployee /> : undefined}
      />
      <div className="mb-4 flex">
        <SearchInput
          className="ml-auto w-full max-w-xs"
          placeholder="F.I.Sh yoki beyjik"
          value={search}
          onChange={setSearch}
        />
      </div>
      {isLoading ? (
        <Skeleton className="h-64 w-full" />
      ) : isError ? (
        <QueryError onRetry={() => refetch()} />
      ) : (
        <div className="overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>F.I.Sh</TableHead>
                <TableHead>Lavozim</TableHead>
                <TableHead>Postlar</TableHead>
                <TableHead>Holat</TableHead>
                <TableHead>Amallar</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data?.data.length ? (
                data.data.map((e) => (
                  <TableRow key={e.id}>
                    <TableCell className="font-medium">{e.full_name}</TableCell>
                    <TableCell>{e.position ?? "—"}</TableCell>
                    <TableCell>
                      <div className="flex flex-wrap gap-1">
                        {e.assigned_post_ids.map((pid) => {
                          const post = postById.get(pid)
                          if (!post) return null
                          return <PostBadge key={pid} code={post.code} />
                        })}
                      </div>
                    </TableCell>
                    <TableCell>
                      <Badge
                        variant={
                          e.status === "active" ? "default" : "secondary"
                        }
                      >
                        {EMPLOYEE_STATUS_LABELS[e.status]}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-1.5">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => setBadgeFor(e)}
                        >
                          <IdCard /> Beyjik
                        </Button>
                        {admin && (
                          <>
                            <Button
                              variant="ghost"
                              size="sm"
                              title="Tahrirlash"
                              onClick={() => setEditFor(e)}
                            >
                              <Pencil />
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              className="text-destructive"
                              title="O'chirish"
                              onClick={() => setDeleteFor(e)}
                            >
                              <Trash2 />
                            </Button>
                          </>
                        )}
                      </div>
                    </TableCell>
                  </TableRow>
                ))
              ) : (
                <EmptyRow colSpan={5}>
                  {debounced
                    ? `"${debounced}" bo'yicha hodim topilmadi.`
                    : "Hali hodim yo'q — \"Hodim qo'shish\" bilan qo'shing."}
                </EmptyRow>
              )}
            </TableBody>
          </Table>
        </div>
      )}
      {/* `key` SHART: dialog ichidagi "yangi beyjik" mutatsiyasi holati komponent
          bilan yashaydi. Kalitsiz u doim o'rnatilgan turardi va bir hodimga
          beyjik qayta berilgach, KEYINGI hodimning dialogida ham o'sha eski
          javob ko'rsatilardi (`regen.data ?? employee`) — ya'ni boshqa odamning
          ismi va QR'i chop etilardi. */}
      {badgeFor && (
        <BadgeDialog
          key={badgeFor.id}
          employee={badgeFor}
          onClose={() => setBadgeFor(null)}
          isAdmin={admin}
        />
      )}
      {editFor && (
        <EditEmployee employee={editFor} onClose={() => setEditFor(null)} />
      )}
      <DeleteEmployee employee={deleteFor} onClose={() => setDeleteFor(null)} />
    </div>
  )
}

function EditEmployee({
  employee,
  onClose,
}: {
  employee: EmployeeRead
  onClose: () => void
}) {
  const queryClient = useQueryClient()
  const cb = crudCallbacks(queryClient, ["employees"], "Hodim yangilandi")

  const form = useForm<z.infer<typeof formSchema>>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      full_name: employee.full_name,
      phone: formatUzPhone(employee.phone ?? ""),
      position: employee.position ?? "",
      assigned_post_ids: employee.assigned_post_ids,
    },
  })
  const [active, setActive] = useState(employee.status === "active")

  const mutation = useMutation({
    mutationFn: (data: z.infer<typeof formSchema>) =>
      EmployeesService.updateEmployee({
        employeeId: employee.id,
        requestBody: {
          full_name: data.full_name,
          phone: data.phone || null,
          position: data.position || null,
          assigned_post_ids: data.assigned_post_ids,
          status: active ? "active" : "inactive",
        },
      }),
    ...cb,
    onSuccess: () => {
      cb.onSuccess()
      onClose()
    },
  })

  return (
    <Dialog open onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Hodimni tahrirlash</DialogTitle>
          <DialogDescription>{employee.full_name}</DialogDescription>
        </DialogHeader>
        <Form {...form}>
          <form
            onSubmit={form.handleSubmit((d) => mutation.mutate(d))}
            className="space-y-3"
          >
            <EmployeeFields control={form.control} />
            <div className="flex items-center justify-between rounded-lg border p-3">
              <span className="text-sm font-medium">
                {active ? "AKTIV" : "NOFAOL"} — beyjik{" "}
                {active ? "ishlaydi" : "bloklangan"}
              </span>
              <Switch checked={active} onCheckedChange={setActive} />
            </div>
            <DialogFooter className="pt-2">
              <LoadingButton type="submit" loading={mutation.isPending}>
                Saqlash
              </LoadingButton>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  )
}

function DeleteEmployee({
  employee,
  onClose,
}: {
  employee: EmployeeRead | null
  onClose: () => void
}) {
  const queryClient = useQueryClient()
  const cb = crudCallbacks(queryClient, ["employees"], "Hodim o'chirildi")
  const mutation = useMutation({
    mutationFn: (id: number) =>
      EmployeesService.deleteEmployee({ employeeId: id }),
    ...cb,
    onSuccess: () => {
      cb.onSuccess()
      onClose()
    },
  })
  return (
    <ConfirmDialog
      open={!!employee}
      onOpenChange={(v) => !v && onClose()}
      title="Hodimni o'chirish"
      description={
        employee
          ? `${employee.full_name} ro'yxatdan o'chiriladi, beyjigi ishlamay qoladi. Scan tarixi saqlanadi.`
          : ""
      }
      confirmText="O'chirish"
      destructive
      loading={mutation.isPending}
      onConfirm={() => employee && mutation.mutate(employee.id)}
    />
  )
}

function AddEmployee() {
  const [open, setOpen] = useState(false)
  const queryClient = useQueryClient()
  const cb = crudCallbacks(
    queryClient,
    ["employees"],
    "Hodim qo'shildi — beyjik QR tayyor",
  )

  const form = useForm<z.infer<typeof formSchema>>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      full_name: "",
      phone: "",
      position: "",
      assigned_post_ids: [],
    },
  })

  const mutation = useMutation({
    mutationFn: (data: z.infer<typeof formSchema>) =>
      EmployeesService.createEmployee({
        requestBody: {
          full_name: data.full_name,
          phone: data.phone || null,
          position: data.position || null,
          assigned_post_ids: data.assigned_post_ids,
        },
      }),
    ...cb,
    onSuccess: () => {
      cb.onSuccess()
      form.reset()
      setOpen(false)
    },
  })

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button>
          <Plus /> Hodim qo'shish
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Yangi hodim</DialogTitle>
          <DialogDescription>
            Beyjik ID tizim tomonidan beriladi (UUID)
          </DialogDescription>
        </DialogHeader>
        <Form {...form}>
          <form
            onSubmit={form.handleSubmit((d) => mutation.mutate(d))}
            className="space-y-3"
          >
            <EmployeeFields control={form.control} />
            <DialogFooter className="pt-2">
              <LoadingButton type="submit" loading={mutation.isPending}>
                Saqlash
              </LoadingButton>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  )
}

function BadgeDialog({
  employee,
  onClose,
  isAdmin,
}: {
  employee: EmployeeRead | null
  onClose: () => void
  isAdmin: boolean
}) {
  const queryClient = useQueryClient()
  const cb = crudCallbacks(
    queryClient,
    ["employees"],
    "Yangi beyjik tayyor — chop etib bering",
  )
  const [confirmRegen, setConfirmRegen] = useState(false)
  // Beyjik GoDEX'ga chiqadi — detal cheki bilan bir xil zanjir (server PNG
  // chizadi -> Redis navbati -> bridge-agent). Brauzerdan `window.print()`
  // TASHLANDI: u Windows drayveridagi saqlangan qog'oz o'lchamiga tayanardi va
  // u 80x60 bo'lmaganda beyjik yorliqqa mos tushmasdi.
  const print = useMutation({
    mutationFn: (id: number) =>
      EmployeesService.printEmployeeBadge({ employeeId: id }),
    onSuccess: (r) => toast.success(r.message),
    onError: (e) => toast.error(detailMessage(e)),
  })
  const regen = useMutation({
    mutationFn: (id: number) =>
      EmployeesService.regenerateBadge({ employeeId: id }),
    ...cb,
    onSuccess: () => {
      setConfirmRegen(false)
      cb.onSuccess()
    },
  })

  if (!employee) return null
  // Yangi beyjik yaratilgach dialog YANGI QR ko'rsatishi shart — prop'dagi
  // eski snapshot bekor qilingan beyjikni chop ettirib yuborardi
  const emp = regen.data ?? employee
  return (
    <Dialog open onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="max-w-xs text-center">
        <DialogHeader>
          {/* Lavozim ISMDAN OLDIN, kichik shriftda: beyjikda avval "kim
              lavozimda", keyin "kim" o'qiladi. Ikkalasi bitta blok — orasida
              bo'shliq yo'q, chunki ular bitta ma'noni beradi. */}
          {emp.position && (
            <div className="text-2xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">
              {emp.position}
            </div>
          )}
          <DialogTitle>{emp.full_name}</DialogTitle>
          {/* Bu ADMINGA ko'rsatma — beyjikning o'ziga bosilmaydi */}
          <DialogDescription>
            Beyjik QR — chop etib hodimga bering
          </DialogDescription>
        </DialogHeader>
        <div className="mx-auto rounded-xl border p-4">
          {/* `marginSize` — QR standartining "tinch zonasi" (4 modul). v4 da u
              sukut bo'yicha 0: qog'ozda beyjik kichraytirilganda QR chetiga
              yaqin narsa tushsa skaner o'qimay qolardi. */}
          <QRCodeSVG value={emp.badge_id} size={180} marginSize={4} />
        </div>
        {/* Beyjik ID qog'ozga BOSILMAYDI: hodim uchun u ma'nosiz raqam, QR
            o'qilmasa uni qo'lda kiritadigan joy ham yo'q. Ekranda qoladi —
            adminga hodimni aniqlash uchun kerak bo'ladi. */}
        <div className="num text-xs text-muted-foreground">{emp.badge_id}</div>
        <DialogFooter className="flex-col gap-2 sm:flex-col">
          <LoadingButton
            variant="outline"
            loading={print.isPending}
            onClick={() => print.mutate(emp.id)}
          >
            <Printer /> Chop etish
          </LoadingButton>
          {isAdmin && (
            <LoadingButton
              variant="destructive"
              loading={regen.isPending}
              onClick={() => setConfirmRegen(true)}
            >
              Yo'qolgan — yangi beyjik berish
            </LoadingButton>
          )}
        </DialogFooter>
        <ConfirmDialog
          open={confirmRegen}
          onOpenChange={setConfirmRegen}
          title="Yangi beyjik berilsinmi?"
          description={`${employee.full_name} ning eski beyjigi darhol ishlamay qoladi. Yangi QR ni chop etib bermaguningizcha u terminalga kira olmaydi.`}
          confirmText="Yangi beyjik berish"
          destructive
          loading={regen.isPending}
          onConfirm={() => regen.mutate(employee.id)}
        />
      </DialogContent>
    </Dialog>
  )
}
