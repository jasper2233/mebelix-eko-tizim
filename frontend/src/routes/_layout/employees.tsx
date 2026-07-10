import { zodResolver } from "@hookform/resolvers/zod"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { IdCard, Plus, Search } from "lucide-react"
import { QRCodeSVG } from "qrcode.react"
import { useState } from "react"
import { useForm } from "react-hook-form"
import { z } from "zod"

import { type EmployeeRead, EmployeesService } from "@/client"
import { PageHeader } from "@/components/Common/PageHeader"
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
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import useCurrentUser from "@/hooks/useCurrentUser"
import useCustomToast from "@/hooks/useCustomToast"
import { EMPLOYEE_STATUS_LABELS, POST_COLORS } from "@/lib/mes"
import { PHONE_PATTERN } from "@/lib/validation"
import { getEmployeesQueryOptions, getPostsQueryOptions } from "@/queries/mes"
import { handleError } from "@/utils"

export const Route = createFileRoute("/_layout/employees")({
  component: EmployeesPage,
  head: () => ({ meta: [{ title: "Hodimlar | MebeliX" }] }),
})

const formSchema = z.object({
  full_name: z.string().trim().min(2, "Kamida 2 belgi").max(100),
  phone: z
    .string()
    .regex(PHONE_PATTERN, "+998XXXXXXXXX formatida")
    .or(z.literal("")),
  position: z.string().max(50).optional(),
  assigned_post_ids: z.array(z.number()).min(1, "Kamida bitta post tanlang"),
})

function EmployeesPage() {
  const [search, setSearch] = useState("")
  const [badgeFor, setBadgeFor] = useState<EmployeeRead | null>(null)
  const { data, isLoading } = useQuery(getEmployeesQueryOptions(search))
  const { data: posts } = useQuery(getPostsQueryOptions())
  const { currentUser } = useCurrentUser()
  const isAdmin = currentUser?.is_superuser || currentUser?.role === "admin"
  const postById = new Map((posts ?? []).map((p) => [p.id, p]))

  return (
    <div>
      <PageHeader
        title="Hodimlar"
        description="Sex ishchilari — beyjik QR orqali aniqlanadi"
        actions={isAdmin ? <AddEmployee /> : undefined}
      />
      <div className="mb-4 relative max-w-sm">
        <Search className="absolute left-2.5 top-2.5 size-4 text-muted-foreground" />
        <Input
          placeholder="F.I.Sh yoki beyjik"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="pl-8"
        />
      </div>
      {isLoading ? (
        <Skeleton className="h-64 w-full" />
      ) : (
        <div className="overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>F.I.Sh</TableHead>
                <TableHead>Lavozim</TableHead>
                <TableHead>Postlar</TableHead>
                <TableHead>Holat</TableHead>
                <TableHead>Beyjik</TableHead>
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
                          return (
                            <span
                              key={pid}
                              className="rounded px-1.5 py-0.5 text-[10px] font-bold"
                              style={{
                                color: POST_COLORS[post.code],
                                backgroundColor: `color-mix(in srgb, ${POST_COLORS[post.code]} 12%, white)`,
                              }}
                            >
                              {post.code}
                            </span>
                          )
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
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setBadgeFor(e)}
                      >
                        <IdCard /> Beyjik
                      </Button>
                    </TableCell>
                  </TableRow>
                ))
              ) : (
                <TableRow>
                  <TableCell
                    colSpan={5}
                    className="h-24 text-center text-muted-foreground"
                  >
                    Hodimlar topilmadi.
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </div>
      )}
      <BadgeDialog
        employee={badgeFor}
        onClose={() => setBadgeFor(null)}
        isAdmin={Boolean(isAdmin)}
      />
    </div>
  )
}

function AddEmployee() {
  const [open, setOpen] = useState(false)
  const { data: posts } = useQuery(getPostsQueryOptions())
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()

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
    onSuccess: () => {
      showSuccessToast("Hodim qo'shildi — beyjik QR tayyor")
      form.reset()
      setOpen(false)
    },
    onError: handleError(showErrorToast),
    onSettled: () => queryClient.invalidateQueries({ queryKey: ["employees"] }),
  })

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button>
          <Plus /> Hodim qo'shish
        </Button>
      </DialogTrigger>
      <DialogContent className="max-w-md">
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
            <FormField
              control={form.control}
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
                control={form.control}
                name="phone"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Telefon</FormLabel>
                    <FormControl>
                      <Input {...field} placeholder="+998..." />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
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
              control={form.control}
              name="assigned_post_ids"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Qaysi postlarda ishlaydi</FormLabel>
                  <div className="grid grid-cols-3 gap-2">
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
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const regen = useMutation({
    mutationFn: (id: number) =>
      EmployeesService.regenerateBadge({ employeeId: id }),
    onSuccess: () =>
      showSuccessToast("Yangi beyjik berildi — eskisi bloklandi"),
    onError: handleError(showErrorToast),
    onSettled: () => queryClient.invalidateQueries({ queryKey: ["employees"] }),
  })

  if (!employee) return null
  return (
    <Dialog open onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="max-w-xs text-center">
        <DialogHeader>
          <DialogTitle>{employee.full_name}</DialogTitle>
          <DialogDescription>
            Beyjik QR — chop etib hodimga bering
          </DialogDescription>
        </DialogHeader>
        <div className="mx-auto rounded-xl border p-4">
          <QRCodeSVG value={employee.badge_id} size={180} />
        </div>
        <div className="num text-xs text-muted-foreground">
          {employee.badge_id}
        </div>
        <DialogFooter className="flex-col gap-2 sm:flex-col">
          <Button variant="outline" onClick={() => window.print()}>
            Chop etish
          </Button>
          {isAdmin && (
            <LoadingButton
              variant="destructive"
              loading={regen.isPending}
              onClick={() => regen.mutate(employee.id)}
            >
              Yo'qolgan — yangi beyjik berish
            </LoadingButton>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
