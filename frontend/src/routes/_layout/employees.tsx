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
import { IdCard, KeyRound, Pencil, Plus, Printer, Trash2 } from "lucide-react"
import { useMemo, useState } from "react"
import { toast } from "sonner"

import {
  type EmployeeRead,
  EmployeesService,
  type UserRead,
  UsersService,
} from "@/client"
import { AddUser } from "@/components/Admin/AddUser"
import { UserActionsMenu } from "@/components/Admin/UserActionsMenu"
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
  both: "Ikkalasi",
  none: "Yo'q",
}

const ACCESS_FILTERS: { key: Access | "all"; label: string }[] = [
  { key: "all", label: "Hammasi" },
  { key: "badge", label: "Tsex" },
  { key: "password", label: "Ofis" },
  { key: "none", label: "Kirishsiz" },
]

/** Odamda IKKI eshik bo'lishi mumkin: beyjik (tsex monoblokи) va parol (ofis
 * kompyuteri). Ular bir-biriga bog'liq emas, shuning uchun ustun ham ikki katak:
 * to'ldirilgan — eshik ochiq, uzuq chiziqli — yopiq. Ro'yxatni pastga qarab
 * o'qiganda kim qayerda ishlashi legendasiz ko'rinadi. Rang brend tizimidan:
 * tsex — asosiy navy, ofis — oltin (kamroq odamda bor, kuchliroq huquq). */
function AccessDoors({ access }: { access: Access }) {
  const hasBadge = access === "badge" || access === "both"
  const hasPassword = access === "password" || access === "both"
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
  const [accessFilter, setAccessFilter] = useState<Access | "all">("all")
  const [badgeFor, setBadgeFor] = useState<EmployeeRead | null>(null)
  const [editFor, setEditFor] = useState<Person | null>(null)
  const [adding, setAdding] = useState(false)
  const [deleteFor, setDeleteFor] = useState<Person | null>(null)
  const debounced = useDebounced(search.trim())

  const employees = useQuery({
    ...getEmployeesQueryOptions(debounced),
    placeholderData: keepPreviousData,
  })
  const users = useQuery(getUsersQueryOptions())
  const { data: posts } = useQuery(getPostsQueryOptions())
  const { currentUser } = useCurrentUser()
  const canManageAccounts = isSuperuser(currentUser)
  const postById = new Map((posts ?? []).map((p) => [p.id, p]))

  const { people, devices } = useMemo(() => {
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
        access: user
          ? hasPosts
            ? "both"
            : "password"
          : hasPosts
            ? "badge"
            : "none",
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

    return {
      people: result.sort((a, b) => a.name.localeCompare(b.name)),
      devices: userRows.filter(isDeviceAccount),
    }
  }, [employees.data, users.data, debounced])

  // "Tsex" va "Ofis" — eshik bo'yicha filtr, ya'ni ikkala eshikli odam IKKALASIDA
  // ham chiqadi. Aks holda texnolog qidirilganda ikkala chipda ham topilmasdi.
  const shown =
    accessFilter === "all"
      ? people
      : people.filter((p) =>
          accessFilter === "badge"
            ? p.access === "badge" || p.access === "both"
            : accessFilter === "password"
              ? p.access === "password" || p.access === "both"
              : p.access === "none",
        )

  const isLoading = employees.isLoading || users.isLoading
  const isError = employees.isError || users.isError

  return (
    <div>
      <PageHeader
        title="Hodimlar"
        description="Tsex ishchilari va ofis xodimlari — kirish usuli bilan"
        actions={
          canManageAccounts || isManagement(currentUser) ? (
            <Button onClick={() => setAdding(true)}>
              <Plus /> Odam qo'shish
            </Button>
          ) : undefined
        }
      />
      <div className="mb-4 flex flex-wrap items-center gap-2">
        {ACCESS_FILTERS.map((f) => (
          <Button
            key={f.key}
            size="sm"
            variant={accessFilter === f.key ? "default" : "outline"}
            onClick={() => setAccessFilter(f.key)}
          >
            {f.label}
          </Button>
        ))}
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
              {shown.length ? (
                shown.map((p) => {
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
                        </div>
                      </TableCell>
                    </TableRow>
                  )
                })
              ) : (
                <EmptyRow colSpan={6}>
                  {debounced
                    ? `"${debounced}" bo'yicha odam topilmadi.`
                    : accessFilter !== "all"
                      ? "Bu kirish usulida hali hech kim yo'q."
                      : "Hali odam yo'q — \"Odam qo'shish\" bilan qo'shing."}
                </EmptyRow>
              )}
            </TableBody>
          </Table>
        </div>
      )}

      {canManageAccounts && devices.length > 0 && (
        <details className="mt-8 rounded-md border p-4">
          <summary className="cursor-pointer text-sm font-semibold">
            Qurilma va post hisoblari ({devices.length})
          </summary>
          <p className="mt-2 mb-3 text-sm text-muted-foreground">
            Bular ODAM EMAS: TERMINAL — monoblokning o'zi, post rollari esa
            beyjik bilan ochilgan smena qaysi hisob nomidan yozilishini hal
            qiladi. O'chirilsa o'sha postda beyjik bilan kirish ishlamay qoladi
            — server ham buni rad etadi.
          </p>
          <div className="mb-3">
            <AddUser />
          </div>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Hisob</TableHead>
                <TableHead>Rol</TableHead>
                <TableHead>Holat</TableHead>
                <TableHead className="w-16" />
              </TableRow>
            </TableHeader>
            <TableBody>
              {devices.map((u) => (
                <TableRow key={u.id}>
                  <TableCell className="font-medium">
                    {u.name ?? u.username}
                  </TableCell>
                  <TableCell>{ROLE_LABELS[u.role]}</TableCell>
                  <TableCell>
                    <Badge variant={u.is_active ? "default" : "secondary"}>
                      {u.is_active ? "FAOL" : "NOFAOL"}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <UserActionsMenu user={u} />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </details>
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
      <DeletePerson
        person={deleteFor}
        canManageAccounts={canManageAccounts}
        onClose={() => setDeleteFor(null)}
      />
    </div>
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
      title="Odamni o'chirish"
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
