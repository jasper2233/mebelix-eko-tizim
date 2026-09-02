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
// Hodimni QURILMA (TERMINAL/TABLO) va texnik hisobga bog'lashni server rad etadi
// (`employees._validate_user_link`); post rolidagi SHAXSIY hisobga esa ruxsat —
// skanersiz postda xodim aynan shu hisob bilan kiradi.

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
import { Field } from "@/components/Common/Field"
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
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
import {
  crudCallbacks,
  getBridgeAgentsQueryOptions,
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

// "none" yo'q: AccessCell u holatda tirecha bilan qaytadi va bu yerga yetmaydi
const ACCESS_LABEL: Record<Exclude<Access, "none">, string> = {
  badge: "Beyjik",
  password: "Parol",
  both: "Beyjik + parol",
}

/** Kirish usuli — odam tizimga QANDAY kiradi.
 * Uchtasi ham haqiqiy holat: beyjik (skanerli post), parol (ofis yoki skaneri
 * yo'q post), ikkalasi (postda ishlaydi va shaxsiy hisobi bor). Ustun aynan
 * shuni aytadi, chunki hisob yopilganda odam qaysi yo'ldan qolishini admin
 * shu yerdan ko'radi. */
function AccessCell({ access }: { access: Access }) {
  if (access === "none") {
    return <span className="text-sm text-muted-foreground">—</span>
  }
  return (
    <span className="flex items-center gap-1.5 text-sm">
      {access !== "password" && (
        <IdCard className="size-4 text-muted-foreground" />
      )}
      {access !== "badge" && (
        <KeyRound className="size-4 text-muted-foreground" />
      )}
      {ACCESS_LABEL[access]}
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
        // Postli hodimda beyjik HAMISHA bor; shaxsiy hisob unga QO'SHILADI
        // (skaneri yo'q postda parol yagona yo'l, lekin beyjigi ham amal qiladi)
        access: hasPosts
          ? user
            ? "both"
            : "badge"
          : user
            ? "password"
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
        // POSITIONS yorlig'i ham shu jadvaldan keladi, ya'ni dialog bilan
        // lavozim ustuni bir so'zni aytadi
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
            // Postlar kelmaguncha dialog ochilmaydi: post bo'lmasa tsex
            // lavozimida "Saqlash" o'chiq turadi va sababi ko'rinmaydi
            <Button onClick={() => setAdding(true)} disabled={!posts}>
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
                      <AccessCell access={p.access} />
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
                        {canEdit && p.employee && p.access !== "none" && (
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
      )}

      {/* `key` SHART: dialog ichidagi "yangi beyjik" mutatsiyasi holati komponent
          bilan yashaydi. Kalitsiz u bir hodimga beyjik qayta berilgach, KEYINGI
          hodimning dialogida ham o'sha eski javobni ko'rsatardi. */}
      {badgeFor && (
        <BadgeDialog
          key={badgeFor.id}
          employee={badgeFor}
          onClose={() => setBadgeFor(null)}
        />
      )}
      {/* "Hodim qo'shish" tugmasi kabi, TAHRIRLASH ham postlar kelguncha
          kutadi: dialog lavozim/postni bir marta ochilishda o'qiydi va qayta
          sinxronlamaydi — bo'sh katalog bilan ochilsa tsex xodimi "Kamida
          bitta post tanlang" da qotib qolardi, saqlansa esa posti o'chardi. */}
      {(adding || editFor) && posts && (
        <PersonDialog
          person={editFor}
          posts={posts}
          canManageAccounts={canManageAccounts}
          onClose={() => {
            setAdding(false)
            setEditFor(null)
          }}
        />
      )}
      <TogglePerson person={toggleFor} onClose={() => setToggleFor(null)} />
      <DeletePerson person={deleteFor} onClose={() => setDeleteFor(null)} />
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
      }
      if (p.user) {
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

// Hisobi bor qatorda o'chirish tugmasi FAQAT superuserga chiziladi
// (`p.user ? canManageAccounts : canEdit`), shuning uchun bu yerda qayta
// tekshirilmaydi — hisobli odam kelsa, huquq allaqachon bor.
function DeletePerson({
  person,
  onClose,
}: {
  person: Person | null
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
      if (p.user) {
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
    ? "tsex yozuvi ham, kirish hisobi ham o'chiriladi"
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

// Faqat `canEdit` (admin) beyjik tugmasini ko'radi, ya'ni dialog ochilgan
// bo'lsa "yangi beyjik" huquqi ham bor
function BadgeDialog({
  employee,
  onClose,
}: {
  employee: EmployeeRead
  onClose: () => void
}) {
  const [confirmRegen, setConfirmRegen] = useState(false)
  const queryClient = useQueryClient()
  // PRINTER TANLOVI. Backend bir nechta printer bo'lsa 422 bilan "qaysi biridan
  // chiqarishni tanlang" deydi va `agent_id` kutadi — UI esa uni hech qachon
  // yubormasdi, ya'ni ikkinchi printer paydo bo'lgan zahoti beyjik chop etish
  // umuman ishlamay qolardi (faqat xato toast). Bitta printer bo'lsa tanlov
  // ko'rsatilmaydi — ortiqcha qadam bo'lardi.
  const { data: agents } = useQuery(getBridgeAgentsQueryOptions())
  const printers = (agents ?? []).filter((a) => a.can_print && a.paired)
  const [agentId, setAgentId] = useState<string>("")
  const target =
    agentId || (printers.length === 1 ? String(printers[0].id) : "")
  const print = useMutation({
    mutationFn: (id: number) =>
      EmployeesService.printEmployeeBadge({
        path: { employee_id: id },
        query: target ? { agent_id: Number(target) } : undefined,
      }),
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
        {printers.length > 1 && (
          <div className="text-left">
            {/* `Field` — yorliq bilan maydon orasidagi bo'shliq va yorliqni
                bosganda fokus. Yalang'och `Label` da bo'shliq yo'q edi. */}
            <Field label="Printer">
              <Select value={target} onValueChange={setAgentId}>
                <SelectTrigger className="w-full">
                  <SelectValue placeholder="Tanlang" />
                </SelectTrigger>
                <SelectContent>
                  {printers.map((a) => (
                    <SelectItem key={a.id} value={String(a.id)}>
                      {a.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </Field>
          </div>
        )}
        <DialogFooter className="flex-col gap-2 sm:flex-col">
          <LoadingButton
            variant="outline"
            loading={print.isPending}
            disabled={printers.length > 1 && !target}
            onClick={() => print.mutate(employee.id)}
          >
            <Printer /> Chop etish
          </LoadingButton>
          <LoadingButton
            variant="destructive"
            loading={regen.isPending}
            onClick={() => setConfirmRegen(true)}
          >
            Yo'qolgan — yangi beyjik berish
          </LoadingButton>
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
