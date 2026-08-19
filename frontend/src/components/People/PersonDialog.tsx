// Hodim dialogi: uch savol — F.I.Sh, telefon, lavozim. Qolganini lavozim hal qiladi.
//
//   tsex lavozimi -> beyjik bilan ishlaydi, posti lavozimdan keladi (POST_ROLES bilan bir xil)
//   ofis lavozimi -> parol bilan kiradi, roli lavozimdan keladi; post ham, beyjik ham berilmaydi
//   "Boshqa"      -> tizimga kirmaydi (haydovchi, farrosh); nomi qo'lda yoziladi
//
// LAVOZIM MATNDAN EMAS, MA'LUMOTDAN tiklanadi: ofis odamida `user.role` dan,
// tsex odamida esa biriktirilgan postdan. Ilgari u `position` MATNI bilan
// solishtirilardi va "Manager" != "Menejer" bo'lgani uchun menejerni tahrirlash
// hisobni emas, YANGI hodim yozuvini yaratardi.

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
import { OTHER_POSITION, POSITIONS } from "@/lib/mes"
import { formatUzPhone } from "@/lib/validation"
import { detailMessage } from "@/utils"

export type Access = "badge" | "password" | "none"

export type Person = {
  employee: EmployeeRead | null
  user: UserRead | null
  name: string
  position: string | null
  phone: string | null
  posts: number[]
  access: Access
}

type PostRow = { id: number; code: string; name: string }

/** Lavozimni MA'LUMOTDAN aniqlaydi: ofis odamida rol bo'yicha, tsex odamida
 * biriktirilgan post bo'yicha. Matn bilan solishtirish mo'rt — yorliq bir joyda
 * o'zgarsa bog'lam jimgina uzilardi. */
function positionOf(person: Person | null, posts: PostRow[]): string {
  if (person === null) return "Arrachi"
  if (person.user) {
    const byRole = POSITIONS.find((x) => x.role === person.user?.role)
    if (byRole) return byRole.label
  }
  const code = posts.find((p) => p.id === person.posts[0])?.code
  const byPost = code ? POSITIONS.find((x) => x.post === code) : undefined
  // Post bo'yicha topilgani hodimning yozib qo'yilgan lavozimiga mos kelsa —
  // o'shani olamiz; aks holda lavozim ro'yxatdan tashqarida (haydovchi va h.k.)
  if (byPost && (!person.position || person.position === byPost.label))
    return byPost.label
  const byLabel = POSITIONS.find((x) => x.label === person.position)
  return byLabel ? byLabel.label : OTHER_POSITION
}

function postsFor(
  label: string,
  posts: PostRow[],
  fallback: number[],
): number[] {
  const found = POSITIONS.find((x) => x.label === label)
  if (found?.post) {
    const post = posts.find((p) => p.code === found.post)
    return post ? [post.id] : []
  }
  return found?.kind === "ofis" ? [] : fallback
}

export function PersonDialog({
  person,
  posts,
  canManageAccounts,
  onClose,
}: {
  person: Person | null // null = yangi hodim
  posts: PostRow[]
  canManageAccounts: boolean
  onClose: () => void
}) {
  const editing = person !== null
  const initialPosition = positionOf(person, posts)
  const [form, setForm] = useState({
    name: person?.name ?? "",
    position: initialPosition,
    otherPosition:
      initialPosition === OTHER_POSITION ? (person?.position ?? "") : "",
    phone: person?.phone ?? "",
    // Postni DIALOG OCHILGANDA ham lavozimdan olamiz. Ilgari u faqat lavozim
    // QO'LDA almashtirilganda to'ldirilardi: admin tayyor turgan "Arrachi" ga
    // tegmasdan saqlasa, postsiz hodim yaratilardi va uning beyjigi ishlamasdi.
    posts: postsFor(initialPosition, posts, person?.posts ?? []),
    username: person?.user?.username ?? "",
    password: "",
  })
  const set = (key: keyof typeof form, value: string) =>
    setForm((f) => ({ ...f, [key]: value }))

  const chosen = POSITIONS.find((x) => x.label === form.position)
  const kind = chosen?.kind ?? "boshqa"
  const positionText =
    kind === "boshqa" ? form.otherPosition.trim() : form.position

  const pickPosition = (label: string) =>
    setForm((f) => ({
      ...f,
      position: label,
      posts: postsFor(label, posts, f.posts),
    }))

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
        // Tsexdan ofisga o'tkazilgan odamning ESKI beyjigi qolib ketmasin:
        // u ofisda ishlayotgan bo'lsa ham tsexda smena ocha olardi
        if (person?.employee) {
          await EmployeesService.deleteEmployee({
            path: { employee_id: person.employee.id },
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
      // Ofisdan tsexga o'tkazilgan bo'lsa kirish hisobi yopiladi — aks holda
      // u eski paroli bilan ofis paneliga kiraverardi
      if (person?.user && canManageAccounts) {
        await UsersService.deleteUser({
          path: { user_id: Number(person.user.id) },
        })
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
    (kind !== "tsex" || form.posts.length > 0) &&
    (kind !== "ofis" ||
      (!!phone && (!!person?.user || form.password.length > 0)))

  // Ofis lavozimi kirish hisobi ochadi — buni faqat superuser qila oladi
  const options = POSITIONS.filter(
    (x) => canManageAccounts || x.kind !== "ofis",
  )

  return (
    <Dialog open onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{editing ? form.name : "Yangi hodim"}</DialogTitle>
          <DialogDescription>
            Lavozim qolganini hal qiladi: tsex lavozimi postni va beyjikni, ofis
            lavozimi parol bilan kirishni beradi
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

          <Field label="Telefon">
            <Input
              value={formatUzPhone(form.phone)}
              onChange={(e) => set("phone", e.target.value)}
              placeholder="+998 90 123-45-67"
              inputMode="tel"
            />
          </Field>

          <Field label="Lavozim">
            <SelectField
              value={form.position}
              onChange={pickPosition}
              options={[
                ...options.map((x) => ({
                  value: x.label,
                  label: x.label,
                  hint: x.post,
                })),
                {
                  value: OTHER_POSITION,
                  label: OTHER_POSITION,
                  hint: "tizimga kirmaydi",
                },
              ]}
            />
          </Field>

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

          {kind === "ofis" && (
            <div className="grid gap-3 rounded-md border border-dashed p-3">
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
