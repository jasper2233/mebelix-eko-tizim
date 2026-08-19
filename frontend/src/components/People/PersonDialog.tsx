// Hodim dialogi: BITTA tanlov — lavozim — qolganini hal qiladi.
//
//   tsex lavozimi   -> beyjik bilan ishlaydi; posti oldindan belgilanadi
//                      (backend `POST_ROLES` bilan bir xil jadval), o'zgartirsa bo'ladi
//   ofis lavozimi   -> parol bilan kiradi; roli lavozimdan keladi
//   "Boshqa"        -> tizimga kirmaydi (haydovchi, farrosh) — nomi qo'lda yoziladi
//
// Ilgari bu yerda "Kirish usuli" tanlovi bor edi (beyjik/parol/ikkalasi/yo'q).
// U adminni BIZNING ma'lumot modelimizni tasvirlashga majburlardi, holbuki javob
// lavozimning o'zida yotibdi: arrachi — beyjik, menejer — parol.

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
import { OTHER_POSITION, POSITIONS, POST_COLORS, ROLE_LABELS } from "@/lib/mes"
import { formatUzPhone } from "@/lib/validation"
import { detailMessage } from "@/utils"

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

type Form = {
  name: string
  position: string
  otherPosition: string
  phone: string
  posts: number[]
  username: string
  password: string
}

export function PersonDialog({
  person,
  posts,
  canManageAccounts,
  onClose,
}: {
  person: Person | null // null = yangi hodim
  posts: { id: number; code: string; name: string }[]
  canManageAccounts: boolean
  onClose: () => void
}) {
  const editing = person !== null
  const known = POSITIONS.find((x) => x.label === person?.position)
  const [form, setForm] = useState<Form>({
    name: person?.name ?? "",
    position: person ? (known ? known.label : OTHER_POSITION) : "Arrachi",
    otherPosition: person && !known ? (person.position ?? "") : "",
    phone: person?.phone ?? "",
    posts: person?.posts ?? [],
    username: person?.user?.username ?? "",
    password: "",
  })
  const set = <K extends keyof Form>(key: K, value: Form[K]) =>
    setForm((f) => ({ ...f, [key]: value }))

  const chosen = POSITIONS.find((x) => x.label === form.position)
  const kind = chosen?.kind ?? "boshqa"
  const positionText =
    kind === "boshqa" ? form.otherPosition.trim() : form.position

  /** Lavozim almashganda posti ham almashadi — arrachidan kromkachiga o'tkazilgan
   * odam eski postida qolib ketmasin. */
  const pickPosition = (label: string) => {
    const next = POSITIONS.find((x) => x.label === label)
    const post = next?.post
      ? posts.find((p) => p.code === next.post)
      : undefined
    setForm((f) => ({
      ...f,
      position: label,
      posts: post ? [post.id] : next?.kind === "ofis" ? [] : f.posts,
    }))
  }

  const queryClient = useQueryClient()
  const digits = form.phone.replace(/\D/g, "")
  const phone = digits ? `+${digits}` : null

  const mutation = useMutation({
    mutationFn: async () => {
      if (kind === "ofis") {
        const role = chosen?.role as UserRole
        if (person?.user) {
          await UsersService.updateUser({
            path: { user_id: Number(person.user.id) },
            body: {
              name: form.name.trim(),
              role,
              ...(phone ? { phone } : {}),
              ...(form.password ? { password: form.password } : {}),
            },
          })
        } else {
          await UsersService.createUser({
            body: {
              name: form.name.trim(),
              username: form.username.trim() || undefined,
              phone: phone ?? "",
              password: form.password,
              role,
            },
          })
        }
        return
      }

      const body = {
        full_name: form.name.trim(),
        position: positionText || null,
        phone,
        assigned_post_ids: kind === "boshqa" ? [] : form.posts,
      }
      if (person?.employee) {
        await EmployeesService.updateEmployee({
          path: { employee_id: person.employee.id },
          body,
        })
      } else {
        await EmployeesService.createEmployee({ body })
      }
    },
    onSuccess: () => {
      toast.success(editing ? "Saqlandi" : "Hodim qo'shildi")
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
    (kind !== "boshqa" || form.otherPosition.trim().length > 1) &&
    (kind !== "ofis" ||
      (!!phone && (!!person?.user || form.password.length > 0)))

  // Ofis lavozimi kirish hisobi ochadi — uni faqat superuser bera oladi
  const positionOptions = POSITIONS.filter(
    (x) => canManageAccounts || x.kind !== "ofis",
  )

  return (
    <Dialog open onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>{editing ? form.name : "Yangi hodim"}</DialogTitle>
          <DialogDescription>
            Lavozim qolganini hal qiladi: tsex lavozimi beyjik va post beradi,
            ofis lavozimi parol bilan kirish ochadi
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
              <SelectField
                value={form.position}
                onChange={pickPosition}
                options={[
                  ...positionOptions.map((x) => ({
                    value: x.label,
                    label: x.label,
                    hint: x.post ?? (x.role ? ROLE_LABELS[x.role] : undefined),
                  })),
                  {
                    value: OTHER_POSITION,
                    label: OTHER_POSITION,
                    hint: "kirmaydi",
                  },
                ]}
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

          {kind === "boshqa" && (
            <Field label="Lavozim nomi">
              <Input
                value={form.otherPosition}
                onChange={(e) => set("otherPosition", e.target.value)}
                placeholder="Haydovchi, farrosh, qorovul..."
                maxLength={50}
              />
            </Field>
          )}

          {kind === "tsex" && (
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

          {kind === "ofis" && (
            <div className="grid gap-3 rounded-md border border-dashed p-3">
              <p className="text-2xs uppercase tracking-wider text-muted-foreground">
                Kirish hisobi — rol:{" "}
                {chosen?.role ? ROLE_LABELS[chosen.role] : "—"}
              </p>
              {!person?.user && (
                <Field label="Login">
                  <Input
                    value={form.username}
                    onChange={(e) => set("username", e.target.value)}
                    placeholder="bo'sh — telefondan olinadi"
                    maxLength={20}
                  />
                </Field>
              )}
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
