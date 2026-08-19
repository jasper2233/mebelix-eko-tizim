// Odam dialogi: bitta forma ham tsex xodimini, ham ofis hisobini yaratadi.
// "Kirish usuli" qaysi yozuv kerakligini hal qiladi:
//   beyjik    -> faqat `employee` qatori (postlar bilan)
//   parol     -> faqat `user` qatori (ofis xodimi, tsexga tushmaydi)
//   ikkalasi  -> ikkala qator, `employee.user_id` bilan bog'lanadi
//   yo'q      -> `employee` qatori, postsiz (haydovchi, farrosh — tizimga kirmaydi)

import { useMutation, useQueryClient } from "@tanstack/react-query"
import { useState } from "react"
import { toast } from "sonner"

import {
  type EmployeeRead,
  EmployeesService,
  type UserRead,
  type UserRole,
  UsersService,
} from "@/client"
import { Field } from "@/components/Common/Field"
import { SelectField } from "@/components/Common/SelectField"
import { Checkbox } from "@/components/ui/checkbox"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { LoadingButton } from "@/components/ui/loading-button"
import { PasswordInput } from "@/components/ui/password-input"
import { POST_COLORS, ROLE_LABELS } from "@/lib/mes"
import { formatUzPhone } from "@/lib/validation"
import { detailMessage } from "@/utils"

/** Odam hisoblari — qurilma va post hisoblari bu ro'yxatda YO'Q: ular odam emas. */
const PERSON_ROLES: UserRole[] = [
  "manager",
  "texnolog",
  "director",
  "material_omborchi",
  "admin",
]

export type Access = "badge" | "password" | "both" | "none"

export type Person = {
  employee: EmployeeRead | null
  user: UserRead | null
  name: string
  position: string | null
  phone: string | null
  posts: number[]
  access: Access
}

const ACCESS_OPTIONS = [
  { value: "badge", label: "Beyjik", hint: "tsexda skan qiladi" },
  { value: "password", label: "Parol", hint: "ofisda kompyuterda" },
  { value: "both", label: "Ikkalasi", hint: "ofis + tsex" },
  { value: "none", label: "Yo'q", hint: "tizimga kirmaydi" },
]

type Form = {
  name: string
  position: string
  phone: string
  access: Access
  posts: number[]
  username: string
  role: UserRole
  password: string
}

export function PersonDialog({
  person,
  posts,
  canManageAccounts,
  onClose,
}: {
  person: Person | null // null = yangi odam
  posts: { id: number; code: string; name: string }[]
  canManageAccounts: boolean
  onClose: () => void
}) {
  const editing = person !== null
  const [form, setForm] = useState<Form>({
    name: person?.name ?? "",
    position: person?.position ?? "",
    phone: person?.phone ?? "",
    access: person?.access ?? "badge",
    posts: person?.posts ?? [],
    username: person?.user?.username ?? "",
    role: (person?.user?.role as UserRole) ?? "manager",
    password: "",
  })
  const set = <K extends keyof Form>(key: K, value: Form[K]) =>
    setForm((f) => ({ ...f, [key]: value }))

  const queryClient = useQueryClient()
  const needsEmployee = form.access !== "password"
  const needsUser = form.access === "password" || form.access === "both"
  const digits = form.phone.replace(/\D/g, "")
  const phone = digits ? `+${digits}` : null

  const mutation = useMutation({
    mutationFn: async () => {
      // Hisob AVVAL yaratiladi: hodim qatoriga uning id'si kerak.
      // `UserRead.id` ATAYLAB satr (JWT `sub` bilan solishtiriladi) — bu yerda songa o'tkaziladi
      let userId: number | null = person?.user ? Number(person.user.id) : null
      if (needsUser && userId === null) {
        const created = await UsersService.createUser({
          body: {
            name: form.name.trim(),
            username: form.username.trim() || undefined,
            phone: phone ?? "",
            password: form.password,
            role: form.role,
          },
        })
        userId = Number(created.data.id)
      } else if (needsUser && userId !== null) {
        await UsersService.updateUser({
          path: { user_id: userId },
          body: {
            name: form.name.trim(),
            role: form.role,
            ...(form.password ? { password: form.password } : {}),
          },
        })
      }

      const body = {
        full_name: form.name.trim(),
        position: form.position.trim() || null,
        phone,
        assigned_post_ids: form.access === "none" ? [] : form.posts,
        user_id: needsUser ? userId : null,
      }
      if (needsEmployee) {
        if (person?.employee) {
          await EmployeesService.updateEmployee({
            path: { employee_id: person.employee.id },
            body,
          })
        } else {
          await EmployeesService.createEmployee({ body })
        }
      } else if (person?.employee) {
        // "Parol" ga o'tkazildi — tsex yozuvi endi kerak emas
        await EmployeesService.deleteEmployee({
          path: { employee_id: person.employee.id },
        })
      }
    },
    onSuccess: () => {
      toast.success(editing ? "Saqlandi" : "Odam qo'shildi")
      onClose()
    },
    onError: (e) => toast.error(detailMessage(e)),
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["employees"] })
      queryClient.invalidateQueries({ queryKey: ["users"] })
    },
  })

  const valid =
    form.name.trim().length > 1 &&
    (!needsUser ||
      (!!phone && (person?.user !== null || form.password.length > 0)))

  return (
    <Dialog open onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>{editing ? form.name : "Yangi odam"}</DialogTitle>
          <DialogDescription>
            Kirish usuli qanday yozuv kerakligini hal qiladi — tsex beyjigi,
            ofis paroli yoki ikkalasi
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-3">
          <Field label="F.I.Sh">
            <Input
              value={form.name}
              onChange={(e) => set("name", e.target.value)}
              maxLength={100}
              autoFocus
            />
          </Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Lavozim">
              <Input
                value={form.position}
                onChange={(e) => set("position", e.target.value)}
                placeholder="Arrachi, Haydovchi..."
                maxLength={50}
              />
            </Field>
            <Field label="Telefon">
              <Input
                value={formatUzPhone(form.phone)}
                onChange={(e) => set("phone", e.target.value)}
                placeholder="+998 90 123-45-67"
                inputMode="tel"
              />
            </Field>
          </div>

          <Field label="Kirish usuli">
            <SelectField
              value={form.access}
              onChange={(v) => set("access", v as Access)}
              options={
                canManageAccounts
                  ? ACCESS_OPTIONS
                  : ACCESS_OPTIONS.filter(
                      (o) => o.value === "badge" || o.value === "none",
                    )
              }
            />
          </Field>

          {form.access !== "none" && form.access !== "password" && (
            <Field label="Qaysi postlarda ishlaydi">
              <div className="flex flex-wrap gap-3 rounded-md border p-3">
                {posts.map((p) => (
                  <div key={p.id} className="flex items-center gap-1.5 text-sm">
                    <Checkbox
                      id={`post-${p.id}`}
                      aria-label={p.code}
                      checked={form.posts.includes(p.id)}
                      onCheckedChange={(on) =>
                        set(
                          "posts",
                          on === true
                            ? [...form.posts, p.id]
                            : form.posts.filter((x) => x !== p.id),
                        )
                      }
                    />
                    <label
                      htmlFor={`post-${p.id}`}
                      className="cursor-pointer"
                      style={{ color: POST_COLORS[p.code] }}
                    >
                      {p.code}
                    </label>
                  </div>
                ))}
              </div>
            </Field>
          )}

          {needsUser && (
            <div className="grid gap-3 rounded-md border border-dashed p-3">
              <div className="grid grid-cols-2 gap-3">
                <Field label="Login">
                  <Input
                    value={form.username}
                    onChange={(e) => set("username", e.target.value)}
                    placeholder="bo'sh — telefondan olinadi"
                    maxLength={20}
                  />
                </Field>
                <Field label="Rol">
                  <SelectField
                    value={form.role}
                    onChange={(v) => set("role", v as UserRole)}
                    options={PERSON_ROLES.map((r) => ({
                      value: r,
                      label: ROLE_LABELS[r],
                    }))}
                  />
                </Field>
              </div>
              <Field
                label={
                  person?.user ? "Yangi parol (bo'sh — o'zgarmaydi)" : "Parol"
                }
              >
                <PasswordInput
                  value={form.password}
                  onChange={(e) => set("password", e.target.value)}
                  autoComplete="new-password"
                />
              </Field>
            </div>
          )}
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
