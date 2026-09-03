// Hodim dialogi: uch savol — F.I.Sh, telefon, lavozim. Qolganini lavozim hal qiladi.
//
//   tsex lavozimi -> beyjik bilan ishlaydi, posti lavozimdan keladi (POST_ROLES bilan bir xil)
//                    skaneri yo'q postda (ARRA) esa qo'shimcha: shaxsiy login+parol
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
  type PostRead,
  type UserRead,
  type UserRole,
  UsersService,
} from "@/client"
import { ConfirmDialog } from "@/components/Common/ConfirmDialog"
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
import { OTHER_POSITION, POSITIONS } from "@/lib/mes"
import { formatUzPhone, optionalFormattedPhoneSchema } from "@/lib/validation"
import { handleError } from "@/utils"

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

/** Lavozimni MA'LUMOTDAN aniqlaydi: ofis odamida rol bo'yicha, tsex odamida
 * biriktirilgan post bo'yicha. Matn bilan solishtirish mo'rt — yorliq bir joyda
 * o'zgarsa bog'lam jimgina uzilardi. */
function positionOf(person: Person | null, posts: PostRead[]): string {
  if (person === null) return POSITIONS[0].label
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
  posts: PostRead[],
  fallback: number[],
): number[] {
  const found = POSITIONS.find((x) => x.label === label)
  if (found?.post) {
    const post = posts.find((p) => p.code === found.post)
    return post ? [post.id] : []
  }
  // Katalogda yo'q lavozim ("Boshqa", eski erkin matn) — mavjud postlar
  // SAQLANADI: aks holda shunday odamni tahrirlash uni postsiz qoldirardi.
  return found?.kind === "ofis" ? [] : fallback
}

export function PersonDialog({
  person,
  posts,
  canManageAccounts,
  onClose,
}: {
  person: Person | null // null = yangi hodim
  posts: PostRead[]
  canManageAccounts: boolean
  onClose: () => void
}) {
  const editing = person !== null
  const initialPosition = positionOf(person, posts)
  const [confirmSwitch, setConfirmSwitch] = useState(false)
  const [form, setForm] = useState({
    name: person?.name ?? "",
    position: initialPosition,
    otherPosition:
      initialPosition === OTHER_POSITION ? (person?.position ?? "") : "",
    phone: formatUzPhone(person?.phone ?? ""),
    // Postni DIALOG OCHILGANDA ham lavozimdan olamiz. Ilgari u faqat lavozim
    // QO'LDA almashtirilganda to'ldirilardi: admin tayyor turgan "Arrachi" ga
    // tegmasdan saqlasa, postsiz hodim yaratilardi va uning beyjigi ishlamasdi.
    posts: postsFor(initialPosition, posts, person?.posts ?? []),
    username: person?.user?.username ?? "",
    password: "",
  })
  // Tsex xodimiga SHAXSIY hisob: skaneri yo'q postda beyjikni skanerlash
  // imkoni yo'q, shuning uchun u monoblokda login va parol bilan kiradi.
  // Kirgan zahoti smenasi ochiladi (`login._open_shift_for`).
  const [shopLogin, setShopLogin] = useState(
    !!person?.user &&
      POSITIONS.find((x) => x.label === initialPosition)?.kind === "tsex",
  )
  const set = (key: keyof typeof form, value: string) =>
    setForm((f) => ({ ...f, [key]: value }))

  const chosen = POSITIONS.find((x) => x.label === form.position)
  const kind = chosen?.kind ?? "boshqa"
  // Hisob faqat tsex lavozimida, faqat superuser qo'li bilan ochiladi
  const withLogin = kind === "tsex" && shopLogin && canManageAccounts
  const positionText =
    kind === "boshqa" ? form.otherPosition.trim() : form.position

  const pickPosition = (label: string) =>
    setForm((f) => ({
      ...f,
      position: label,
      posts: postsFor(label, posts, f.posts),
    }))

  const queryClient = useQueryClient()
  // Telefon FORMATLANGAN holda saqlanadi (boshqa 4 chaqiruvchidagi kabi), shu
  // sabab payload ham, ko'rinish ham aynan shu satr: "901234567" paste qilinsa
  // ekranda ham, serverda ham "+998 90 123-45-67" bo'ladi.
  const parsedPhone = optionalFormattedPhoneSchema.safeParse(form.phone)
  const phone =
    parsedPhone.success && parsedPhone.data ? parsedPhone.data : null

  // Lavozim turi o'zgarsa qarama-qarshi yozuv o'chiriladi (tsexdan ofisga
  // o'tgan odamning beyjigi bekor bo'ladi va aksincha). Bu JIM bo'lmasin.
  // `!withLogin` SHART: shaxsiy logini saqlanayotgan tsex xodimini tahrirlashda
  // hisob o'chmaydi (mutatsiya `updateUser` qiladi), demak tasdiq ham kerak emas.
  const switching =
    editing &&
    ((kind === "ofis" && !!person?.employee) ||
      (kind !== "ofis" && !!person?.user && !withLogin))
  // Allaqachon tsexda bo'lgan xodimning logini olib tashlanmoqda — bu «tsexga
  // o'tkazish» emas, tasdiq matni ham shunga mos bo'lsin.
  const removingLogin = kind !== "ofis" && !!person?.employee

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

      let userId = person?.user ? Number(person.user.id) : null
      const account = withLogin && chosen?.role
      if (account && userId !== null) {
        await UsersService.updateUser({
          path: { user_id: userId },
          body: {
            name: form.name.trim(),
            role: chosen.role as UserRole,
            ...(phone ? { phone } : {}),
            ...(form.password ? { password: form.password } : {}),
          },
        })
      }

      // Hodim yozuvi HISOBDAN OLDIN (ikki so'rov bitta tranzaksiya emas): hodim tushsa hisob yetim qolmaydi.
      // Hisob keyin `updateEmployee({user_id})` bilan bog'lanadi — parolli smena shu bog'lamdan ochiladi.
      const body = {
        full_name: form.name.trim(),
        position: positionText || null,
        phone,
        assigned_post_ids: kind === "boshqa" ? [] : form.posts,
        user_id: account ? userId : null,
      }
      let employeeId = person?.employee ? Number(person.employee.id) : null
      if (employeeId !== null) {
        await EmployeesService.updateEmployee({
          path: { employee_id: employeeId },
          body,
        })
      } else {
        const created = await EmployeesService.createEmployee({ body })
        employeeId = Number(created.data.id)
      }
      if (account && userId === null) {
        const created = await UsersService.createUser({
          body: {
            name: form.name.trim(),
            username: form.username.trim() || undefined,
            phone: phone ?? "",
            password: form.password,
            role: chosen.role as UserRole,
          },
        })
        userId = Number(created.data.id)
        await EmployeesService.updateEmployee({
          path: { employee_id: employeeId },
          body: { user_id: userId },
        })
      }
      // Hisob KERAK EMAS bo'lib qolsa yopiladi: ofisdan tsexga o'tkazilganda
      // (eski paroli bilan ofis paneliga kiraverardi) yoki tsex xodimidan
      // parol bilan kirish olib tashlanganda. Bog'lam yuqorida uzilgan.
      if (!account && userId !== null && canManageAccounts) {
        await UsersService.deleteUser({ path: { user_id: userId } })
      }
    },
    onSuccess: () => {
      toast.success(editing ? "Saqlandi" : "Hodim qo'shildi")
      onClose()
    },
    onError: handleError,
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["employees"] })
      queryClient.invalidateQueries({ queryKey: ["users"] })
    },
  })

  // O'chiq tugma sababini AYTADI: ilgari u shunchaki o'chiq turardi va admin
  // nima yetishmayotganini topa olmasdi
  const missing =
    form.name.trim().length < 2
      ? "F.I.Sh yozing"
      : kind === "boshqa" && form.otherPosition.trim().length < 2
        ? "Lavozim nomini yozing"
        : kind === "tsex" && form.posts.length === 0
          ? "Kamida bitta post tanlang"
          : form.phone !== "" && phone === null
            ? "Telefon +998XXXXXXXXX formatida bo'lsin"
            : (kind === "ofis" || withLogin) && !phone
              ? "Kirish uchun telefon kerak — login o'shandan olinadi"
              : (kind === "ofis" || withLogin) &&
                  !person?.user &&
                  form.password.length === 0
                ? "Parol kiriting"
                : null
  const valid = missing === null

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

          <Field
            label={
              kind === "ofis" || withLogin ? "Telefon (majburiy)" : "Telefon"
            }
          >
            <Input
              value={form.phone}
              onChange={(e) =>
                set("phone", formatUzPhone(e.target.value, form.phone))
              }
              placeholder="+998 90 123-45-67"
              inputMode="tel"
            />
          </Field>

          <Field label="Lavozim">
            <SelectField
              value={form.position}
              onChange={pickPosition}
              // Ro'yxatda FAQAT lavozim nomi turadi. Ilgari yonida post kodi
              // ko'rsatilardi ("Arrachi  ARRA") — u ikki marta bir narsani
              // aytardi va lavozim ro'yxatiga post atamasini olib kirardi.
              // Tanlov OQIBATI baribir darhol ko'rinadi: ofisda parol bloki
              // ochiladi, "Boshqa" da lavozim nomi maydoni chiqadi.
              options={[
                ...options.map((x) => ({ value: x.label, label: x.label })),
                { value: OTHER_POSITION, label: OTHER_POSITION },
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

          {kind === "tsex" && canManageAccounts && (
            // biome-ignore lint/a11y/noLabelWithoutControl: Checkbox (Radix) ichida
            <label className="flex cursor-pointer items-start gap-2.5 rounded-md border p-3 text-sm">
              <Checkbox
                checked={shopLogin}
                onCheckedChange={(v) => setShopLogin(v === true)}
                className="mt-0.5"
              />
              <span>
                Postda skaner yo'q — parol bilan kiradi
                <span className="mt-0.5 block text-2xs text-muted-foreground">
                  Monoblokda login va parol teradi, smenasi o'zi ochiladi.
                  Skaner bo'lsa buni belgilamang — beyjik tezroq.
                </span>
                {person?.user && !shopLogin && (
                  <span className="mt-1 block text-2xs text-destructive">
                    Saqlansa kirish hisobi o'chiriladi — u faqat beyjik bilan
                    ishlaydi.
                  </span>
                )}
              </span>
            </label>
          )}

          {(kind === "ofis" || withLogin) && (
            <div className="grid gap-3 rounded-md border border-dashed p-3">
              {!person?.user && (
                <Field label="Login">
                  <Input
                    value={form.username}
                    onChange={(e) => set("username", e.target.value)}
                    placeholder="bo'sh — telefondan olinadi"
                    maxLength={20}
                  />
                  <span className="text-2xs text-muted-foreground">
                    faqat kichik lotin harflari va raqamlar
                  </span>
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
                {/* Qoida EKRANDA turadi: ilgari u faqat serverdan xato bo'lib
                    qaytardi va admin uch marta urinib topardi */}
                <span className="text-2xs text-muted-foreground">
                  kamida 8 belgi, katta va kichik harf, raqam va belgi (! yoki
                  *)
                </span>
              </Field>
            </div>
          )}
        </div>

        <DialogFooter className="flex-col items-end gap-2 sm:flex-col sm:items-end">
          {missing && (
            <span className="text-xs text-muted-foreground">{missing}</span>
          )}
          <LoadingButton
            disabled={!valid}
            loading={mutation.isPending}
            onClick={() =>
              switching ? setConfirmSwitch(true) : mutation.mutate()
            }
          >
            Saqlash
          </LoadingButton>
        </DialogFooter>
        <ConfirmDialog
          open={confirmSwitch}
          onOpenChange={setConfirmSwitch}
          title={
            kind === "ofis"
              ? "Ofisga o'tkazilsinmi?"
              : removingLogin
                ? "Kirish hisobi o'chirilsinmi?"
                : "Tsexga o'tkazilsinmi?"
          }
          description={
            kind === "ofis"
              ? `${form.name} endi ofisda ishlaydi: beyjigi bekor qilinadi va tsexda smena ocha olmaydi. Skan tarixi saqlanadi.`
              : removingLogin
                ? `${form.name} ning kirish hisobi o'chiriladi va u ofis paneliga kira olmaydi. Tsex yozuvi va beyjigi qoladi.`
                : `${form.name} endi tsexda ishlaydi: kirish hisobi o'chiriladi va u ofis paneliga kira olmaydi.`
          }
          confirmText={
            kind === "ofis"
              ? "Ofisga o'tkazish"
              : removingLogin
                ? "Hisobni o'chirish"
                : "Tsexga o'tkazish"
          }
          destructive
          loading={mutation.isPending}
          onConfirm={() => mutation.mutate()}
        />
      </DialogContent>
    </Dialog>
  )
}
