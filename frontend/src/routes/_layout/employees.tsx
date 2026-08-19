// Odamlar — hodimlar va kirish hisoblari BITTA ro'yxatda. Har odam bitta qator:
// tsex ishchisi (beyjik), ofis xodimi (parol), ikkalasi, yoki hisobsiz xodim.
//
// Nega bitta ro'yxat: ilgari bir odam ikki sahifada ikki yozuv edi (Hodimlar va
// Foydalanuvchilar) va ular o'rtasida hech qanday ko'rinadigan bog'lam yo'q edi —
// texnolog ham hodim, ham hisob sifatida ikki marta yaratilardi.
//
// Qurilma va post hisoblari (TERMINAL, TABLO va 9 operator roli) ODAM EMAS:
// TERMINAL — monoblokning o'zi, post rollari esa beyjik bilan ochilgan smena
// qaysi hisob nomidan yozilishini hal qiladi. Ular pastdagi alohida bo'limda.
//
// Hodimni qurilma/post hisobiga bog'lashni server rad etadi
// (`employees._validate_user_link`), ya'ni bu ro'yxatga "odam emas" qator tusholmaydi.

import {
  keepPreviousData,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import {
  IdCard,
  KeyRound,
  Pencil,
  Plus,
  Printer,
  Trash2,
  UserCheck,
  UserMinus,
} from "lucide-react"
import { useMemo, useState } from "react"
import { toast } from "sonner"

import {
  type EmployeeRead,
  EmployeesService,
  type UserRead,
  UsersService,
} from "@/client"
import { ConfirmDialog } from "@/components/Common/ConfirmDialog"
import { EmptyRow } from "@/components/Common/EmptyRow"
import { PageHeader } from "@/components/Common/PageHeader"
import { PostBadge } from "@/components/Common/PostBadge"
import { QueryError } from "@/components/Common/QueryError"
import { RowAction } from "@/components/Common/RowAction"
import { SearchInput } from "@/components/Common/SearchInput"
import {
  type Access,
  type Person,
  PersonDialog,
} from "@/components/People/PersonDialog"
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
import { useDebounced } from "@/hooks/useDebounced"
import { requireAccess } from "@/lib/guards"
import {
  EMPLOYEE_STATUS_LABELS,
  isAdmin,
  isManagement,
  isSuperuser,
  MACHINE_BOUND_ROLES,
  OPERATOR_ROLES,
  ROLE_LABELS,
} from "@/lib/mes"
import { cn } from "@/lib/utils"
import {
  crudCallbacks,
  getEmployeesQueryOptions,
  getPostsQueryOptions,
} from "@/queries/mes"
import { getUsersQueryOptions } from "@/queries/users"
import { detailMessage } from "@/utils"

export const Route = createFileRoute("/_layout/employees")({
  component: PeoplePage,
  beforeLoad: requireAccess(isManagement),
  head: () => ({ meta: [{ title: "Hodimlar | MebeliX" }] }),
})

const DEVICE_ROLES: string[] = [...MACHINE_BOUND_ROLES, ...OPERATOR_ROLES]
const isDeviceAccount = (u: UserRead) => DEVICE_ROLES.includes(u.role)

const ACCESS_LABEL: Record<Access, string> = {
  badge: "Beyjik",
  password: "Parol",
  none: "Yo'q",
}

/** Odamda IKKI eshik bo'lishi mumkin: beyjik (tsex monoblokи) va parol (ofis
 * kompyuteri). Ular bir-biriga bog'liq emas, shuning uchun ustun ham ikki katak:
 * to'ldirilgan — eshik ochiq, uzuq chiziqli — yopiq. Ro'yxatni pastga qarab
 * o'qiganda kim qayerda ishlashi legendasiz ko'rinadi. Rang brend tizimidan:
 * tsex — asosiy navy, ofis — oltin (kamroq odamda bor, kuchliroq huquq). */
function AccessDoors({ access }: { access: Access }) {
  const hasBadge = access === "badge"
  const hasPassword = access === "password"
  const slot = "grid size-6 place-items-center rounded-[4px] border"
  return (
    <span className="flex items-center gap-2">
      <span aria-hidden className="flex gap-1">
        <span
          className={cn(
            slot,
            hasBadge
              ? "border-primary bg-primary text-primary-foreground"
              : "border-dashed border-border text-muted-foreground/40",
          )}
        >
          <IdCard className="size-3.5" />
        </span>
        <span
          className={cn(
            slot,
            hasPassword
              ? "border-sidebar-primary bg-sidebar-primary text-sidebar-primary-foreground"
              : "border-dashed border-border text-muted-foreground/40",
          )}
        >
          <KeyRound className="size-3.5" />
        </span>
      </span>
      <span className="text-sm">{ACCESS_LABEL[access]}</span>
    </span>
  )
}

function PeoplePage() {
  const [search, setSearch] = useState("")
  const [badgeFor, setBadgeFor] = useState<EmployeeRead | null>(null)
  const [editFor, setEditFor] = useState<Person | null>(null)
  const [adding, setAdding] = useState(false)
  const [deleteFor, setDeleteFor] = useState<Person | null>(null)
  const [toggleFor, setToggleFor] = useState<Person | null>(null)
  const debounced = useDebounced(search.trim())

  const employees = useQuery({
    ...getEmployeesQueryOptions(debounced),
    placeholderData: keepPreviousData,
  })
  const users = useQuery(getUsersQueryOptions())
  const { data: posts } = useQuery(getPostsQueryOptions())
  const { currentUser } = useCurrentUser()
  // Backend: hodim yozish `AdminUser`, hisob yozish superuser. Tugmalar AYNAN
  // shu chegaraga qarab chiziladi — ilgari manager hammasini ko'rib, bosganda
  // 403 olardi va ish shu yerda to'xtardi.
  const canEdit = isAdmin(currentUser)
  const canManageAccounts = isSuperuser(currentUser)
  const postById = new Map((posts ?? []).map((p) => [p.id, p]))

  const people = useMemo(() => {
    const userRows = users.data?.data ?? []
    const byId = new Map(userRows.map((u) => [Number(u.id), u]))
    const linked = new Set<number>()
    const result: Person[] = []

    for (const e of employees.data?.data ?? []) {
      const user = e.user_id != null ? (byId.get(e.user_id) ?? null) : null
      if (user) linked.add(Number(user.id))
      const hasPosts = e.assigned_post_ids.length > 0
      result.push({
        employee: e,
        user,
        name: e.full_name,
        position: e.position,
        phone: e.phone,
        posts: e.assigned_post_ids,
        access: user ? "password" : hasPosts ? "badge" : "none",
      })
    }

    // Hodim yozuvi yo'q hisoblar — ofis xodimlari
    const q = debounced.toLowerCase()
    for (const u of userRows) {
      if (isDeviceAccount(u) || linked.has(Number(u.id))) continue
      if (q && !(u.name ?? u.username).toLowerCase().includes(q)) continue
      result.push({
        employee: null,
        user: u,
        name: u.name ?? u.username,
        position: ROLE_LABELS[u.role],
        phone: u.phone,
        posts: [],
        access: "password",
      })
    }

    return result.sort((a, b) => a.name.localeCompare(b.name))
  }, [employees.data, users.data, debounced])

  const isLoading = employees.isLoading || users.isLoading
  const isError = employees.isError || users.isError

  return (
    <div>
      <PageHeader
        title="Hodimlar"
        description="Tsex ishchilari va ofis xodimlari — kirish usuli bilan"
        actions={
          canEdit ? (
            <Button onClick={() => setAdding(true)}>
              <Plus /> Hodim qo'shish
            </Button>
          ) : undefined
        }
      />
      <div className="mb-4 flex">
        <SearchInput
          className="ml-auto w-full max-w-xs"
          placeholder="F.I.Sh bo'yicha"
          value={search}
          onChange={setSearch}
        />
      </div>

      {isLoading ? (
        <Skeleton className="h-64 w-full" />
      ) : isError ? (
        <QueryError
          onRetry={() => {
            employees.refetch()
            users.refetch()
          }}
        />
      ) : (
        <div className="overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>F.I.Sh</TableHead>
                <TableHead>Lavozim</TableHead>
                <TableHead>Kirish</TableHead>
                <TableHead>Postlar</TableHead>
                <TableHead>Holat</TableHead>
                <TableHead className="w-32">Amallar</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {people.length ? (
                people.map((p) => {
                  const active = p.employee
                    ? p.employee.status === "active"
                    : (p.user?.is_active ?? true)
                  return (
                    <TableRow
                      key={p.employee ? `e${p.employee.id}` : `u${p.user?.id}`}
                    >
                      <TableCell className="font-medium">{p.name}</TableCell>
                      <TableCell>{p.position ?? "—"}</TableCell>
                      <TableCell>
                        <AccessDoors access={p.access} />
                      </TableCell>
                      <TableCell>
                        <div className="flex flex-wrap gap-1">
                          {p.posts.map((pid) => {
                            const post = postById.get(pid)
                            return post ? (
                              <PostBadge key={pid} code={post.code} />
                            ) : null
                          })}
                        </div>
                      </TableCell>
                      <TableCell>
                        <Badge variant={active ? "default" : "secondary"}>
                          {active
                            ? EMPLOYEE_STATUS_LABELS.active
                            : EMPLOYEE_STATUS_LABELS.inactive}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center gap-1.5">
                          {p.employee && p.access !== "none" && (
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => setBadgeFor(p.employee)}
                            >
                              <IdCard /> Beyjik
                            </Button>
                          )}
                          {(p.user ? canManageAccounts : canEdit) && (
                            <>
                              <RowAction
                                icon={active ? UserMinus : UserCheck}
                                title={
                                  active ? "Nofaol qilish" : "Faollashtirish"
                                }
                                onClick={() => setToggleFor(p)}
                              />
                              <RowAction
                                icon={Pencil}
                                title="Tahrirlash"
                                onClick={() => setEditFor(p)}
                              />
                              <RowAction
                                icon={Trash2}
                                title="O'chirish"
                                danger
                                onClick={() => setDeleteFor(p)}
                              />
                            </>
                          )}
                        </div>
                      </TableCell>
                    </TableRow>
                  )
                })
              ) : (
                <EmptyRow colSpan={6}>
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
          bilan yashaydi. Kalitsiz u bir hodimga beyjik qayta berilgach, KEYINGI
          hodimning dialogida ham o'sha eski javobni ko'rsatardi. */}
      {badgeFor && (
        <BadgeDialog
          key={badgeFor.id}
          employee={badgeFor}
          onClose={() => setBadgeFor(null)}
          isAdmin={canManageAccounts}
        />
      )}
      {(adding || editFor) && (
        <PersonDialog
          person={editFor}
          posts={posts ?? []}
          canManageAccounts={canManageAccounts}
          onClose={() => {
            setAdding(false)
            setEditFor(null)
          }}
        />
      )}
      <TogglePerson person={toggleFor} onClose={() => setToggleFor(null)} />
      <DeletePerson
        person={deleteFor}
        canManageAccounts={canManageAccounts}
        onClose={() => setDeleteFor(null)}
      />
    </div>
  )
}

/** Nofaol qilish — ishdan bo'shash yoki ta'til uchun. O'chirish emas: skan tarixi,
 * ish haqi va hisobot qatorlari joyida qolishi kerak. Hodimda `status`, hisobda
 * `is_active` — ikkalasi bir tugmadan boshqariladi. */
function TogglePerson({
  person,
  onClose,
}: {
  person: Person | null
  onClose: () => void
}) {
  const queryClient = useQueryClient()
  const active = person?.employee
    ? person.employee.status === "active"
    : (person?.user?.is_active ?? true)
  const mutation = useMutation({
    mutationFn: async (p: Person) => {
      if (p.employee) {
        await EmployeesService.updateEmployee({
          path: { employee_id: p.employee.id },
          body: { status: active ? "inactive" : "active" },
        })
      } else if (p.user) {
        await UsersService.updateUser({
          path: { user_id: Number(p.user.id) },
          body: { is_active: !active },
        })
      }
    },
    onSuccess: () => {
      toast.success(active ? "Nofaol qilindi" : "Faollashtirildi")
      onClose()
    },
    onError: (e) => toast.error(detailMessage(e)),
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["employees"] })
      queryClient.invalidateQueries({ queryKey: ["users"] })
    },
  })
  return (
    <ConfirmDialog
      open={!!person}
      onOpenChange={(v) => !v && onClose()}
      title={active ? "Nofaol qilinsinmi?" : "Faollashtirilsinmi?"}
      description={
        person
          ? active
            ? `${person.name} ro'yxatda qoladi, lekin beyjigi va kirishi ishlamaydi. Ochiq smenasi yopiladi. Skan tarixi va ish haqi saqlanadi.`
            : `${person.name} yana ishlay boshlaydi.`
          : ""
      }
      confirmText={active ? "Nofaol qilish" : "Faollashtirish"}
      destructive={active}
      loading={mutation.isPending}
      onConfirm={() => person && mutation.mutate(person)}
    />
  )
}

function DeletePerson({
  person,
  canManageAccounts,
  onClose,
}: {
  person: Person | null
  canManageAccounts: boolean
  onClose: () => void
}) {
  const queryClient = useQueryClient()
  const mutation = useMutation({
    mutationFn: async (p: Person) => {
      if (p.employee) {
        await EmployeesService.deleteEmployee({
          path: { employee_id: p.employee.id },
        })
      }
      // Hisobni faqat superuser o'chira oladi — boshqasida tsex yozuvi ketadi,
      // hisob esa qoladi va buni xabar ham aytadi
      if (p.user && canManageAccounts) {
        await UsersService.deleteUser({ path: { user_id: Number(p.user.id) } })
      }
    },
    onSuccess: () => {
      toast.success("O'chirildi")
      onClose()
    },
    onError: (e) => toast.error(detailMessage(e)),
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["employees"] })
      queryClient.invalidateQueries({ queryKey: ["users"] })
    },
  })

  const what = person?.user
    ? canManageAccounts
      ? "tsex yozuvi ham, kirish hisobi ham o'chiriladi"
      : "faqat tsex yozuvi o'chiriladi — kirish hisobini superuser o'chiradi"
    : "ro'yxatdan o'chiriladi, beyjigi ishlamay qoladi"

  return (
    <ConfirmDialog
      open={!!person}
      onOpenChange={(v) => !v && onClose()}
      title="Hodimni o'chirish"
      description={
        person ? `${person.name}: ${what}. Skan tarixi saqlanadi.` : ""
      }
      confirmText="O'chirish"
      destructive
      loading={mutation.isPending}
      onConfirm={() => person && mutation.mutate(person)}
    />
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
  const [confirmRegen, setConfirmRegen] = useState(false)
  const queryClient = useQueryClient()
  const print = useMutation({
    mutationFn: (id: number) =>
      EmployeesService.printEmployeeBadge({ path: { employee_id: id } }),
    onSuccess: () => toast.success("Beyjik chop etishga yuborildi"),
    onError: (e) => toast.error(detailMessage(e)),
  })
  const regenCb = crudCallbacks(
    queryClient,
    ["employees"],
    "Yangi beyjik berildi",
  )
  const regen = useMutation({
    mutationFn: (id: number) =>
      EmployeesService.regenerateBadge({ path: { employee_id: id } }),
    ...regenCb,
    onSuccess: () => {
      regenCb.onSuccess()
      setConfirmRegen(false)
    },
  })

  if (!employee) return null
  return (
    <Dialog open onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="max-w-xs text-center">
        <DialogHeader>
          {employee.position && (
            <div className="text-2xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">
              {employee.position}
            </div>
          )}
          <DialogTitle>{employee.full_name}</DialogTitle>
          <DialogDescription>
            Beyjikni chop etib hodimga bering
          </DialogDescription>
        </DialogHeader>
        {/* QR EKRANDA CHIZILMAYDI: beyjik — tsexdagi yagona kirish kaliti, ekrandagi
            QR ni suratga olgan odam boshqa hodim nomidan smena ocha olardi. Server
            yorliqni to'g'ridan-to'g'ri printerga yuboradi, shuning uchun `badge_id`
            javobda ham qaytarilmaydi. */}
        <div className="mx-auto rounded-xl border border-dashed p-6 text-sm text-muted-foreground">
          Beyjik raqami ekranda ko'rsatilmaydi.
          <br />
          Yorliq to'g'ridan-to'g'ri printerga yuboriladi.
        </div>
        <DialogFooter className="flex-col gap-2 sm:flex-col">
          <LoadingButton
            variant="outline"
            loading={print.isPending}
            onClick={() => print.mutate(employee.id)}
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
