import { zodResolver } from "@hookform/resolvers/zod"
import { useMutation } from "@tanstack/react-query"
import { createFileRoute, redirect, useNavigate } from "@tanstack/react-router"
import type { AxiosError } from "axios"
import { IdCard, KeyRound } from "lucide-react"
import { useState } from "react"
import { useForm } from "react-hook-form"
import { z } from "zod"

import type { BodyLoginAccessToken as AccessToken } from "@/client"
import { LoginService, UsersService } from "@/client"
import { AuthLayout } from "@/components/Common/AuthLayout"
import { BadgePrompt } from "@/components/Common/BadgePrompt"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
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
import { PasswordInput } from "@/components/ui/password-input"
import { useAuth } from "@/hooks/useAuth"
import { useBadgeScan } from "@/hooks/useBadgeScan"
import { formatUzPhone } from "@/lib/validation"
import { extractErrorMessage } from "@/utils"

const makeFormSchema = () =>
  z.object({
    username: z
      .string()
      .min(1, { message: "Foydalanuvchi nomi yoki telefon majburiy" }),
    // Faqat bo'sh emasligi tekshiriladi — kuch talablari parol O'RNATISHDA qo'llanadi,
    // login'da esas mavjud (jumladan eski/seed) parol bilan kirish imkonini saqlash kerak.
    password: z.string().min(1, { message: "Parol majburiy" }),
  }) satisfies z.ZodType<AccessToken>

type FormData = z.infer<ReturnType<typeof makeFormSchema>>

export const Route = createFileRoute("/login")({
  component: Login,
  beforeLoad: async () => {
    try {
      await UsersService.readUserMe()
    } catch {
      return
    }
    throw redirect({ to: "/" })
  },
  head: () => ({
    meta: [
      {
        title: "Kirish | MebeliX",
      },
    ],
  }),
})

type PostChoice = { id: number; code: string; name: string }

function Login() {
  const navigate = useNavigate()
  const { loginMutation } = useAuth()
  const [formSchema] = useState(makeFormSchema)
  const [showPassword, setShowPassword] = useState(false)
  // Bir nechta postga biriktirilgan hodim: server 409 bilan ro'yxat qaytaradi
  const [choice, setChoice] = useState<{
    badgeId: string
    employeeName: string
    posts: PostChoice[]
  } | null>(null)

  const badge = useMutation({
    mutationFn: (v: { badgeId: string; postId?: number }) =>
      LoginService.loginWithBadge({
        body: { badge_id: v.badgeId, post_id: v.postId ?? null },
      }),
    onSuccess: () => {
      setChoice(null)
      navigate({ to: "/" })
    },
    onError: (e, v) => {
      // 409 detali OBYEKT bo'ladi (odatdagi xatolarda — satr): hodim bir nechta
      // postga biriktirilgan, qaysi biriga kirayotganini o'zi tanlaydi.
      const { detail } = ((e as AxiosError)?.response?.data ?? {}) as {
        detail?: { code?: string; employee_name?: string; posts?: PostChoice[] }
      }
      if (detail?.code === "POST_CHOICE")
        setChoice({
          badgeId: v.badgeId,
          employeeName: detail.employee_name ?? "",
          posts: detail.posts ?? [],
        })
      // Boshqa xato (400/500) dialogni YOPADI: `choice` turganda `badgeError` bo'sh bo'lar, dialogda
      // xato bloki yo'q — operator tugmani javobsiz takror bosaverardi.
      else setChoice(null)
    },
  })

  // Beyjik butun sahifada tinglanadi: ofis xodimi parolni terayotganda ham
  // fokus tortilmaydi, tsexdagi operator esa hech nima bosmasdan skanerlaydi.
  useBadgeScan((badgeId) => {
    if (!badge.isPending) badge.mutate({ badgeId })
  })

  const form = useForm<FormData>({
    resolver: zodResolver(formSchema),
    mode: "onBlur",
    defaultValues: {
      username: "",
      password: "",
    },
  })

  const onSubmit = (data: FormData) => {
    if (loginMutation.isPending) return
    // Maydon IKKI xil qiymat qabul qiladi: foydalanuvchi nomi yoki telefon.
    // Yozish paytidagi formatlash SHARTLI (maydonning `onChange` iga qarang) —
    // harfli nomga tegilmaydi. Bu yerda esa yuborishdan oldin tozalaymiz:
    // qiymat telefonga o'xshasa (faqat
    // +, raqam, bo'shliq, tire) ajratgichlar olib tashlanadi — shunda
    // "+998 90 123-45-67" ko'rinishida joylashtirilgan raqam ham ishlaydi.
    // Foydalanuvchi nomiga tegilmaydi: unda boshqa belgilar bor.
    const username = /^\+?[\d\s-]+$/.test(data.username.trim())
      ? data.username.replace(/[\s-]+/g, "")
      : data.username.trim()
    loginMutation.mutate({ ...data, username })
  }

  // `!choice` — POST_CHOICE signalini bostirish uchun: u xato emas, tanlov
  // so'rovi. Haqiqiy xatoda `onError` `choice` ni tozalaydi, shuning uchun
  // dialogdan kelgan 400/500 ham shu yerda chiqadi.
  const badgeError =
    badge.isError && !choice ? extractErrorMessage(badge.error) : ""

  return (
    <AuthLayout>
      <Form {...form}>
        <form
          onSubmit={form.handleSubmit(onSubmit)}
          className="flex flex-col gap-6"
        >
          {/* Markazlashgan: tsexdagi monoblokka kelgan odamning ko'zi markazga
              tushadi va u yerda bitta ish turadi — beyjikni skanerlash. */}
          {/* Sahifa nomi eyebrow darajasida: sahifada bitta katta sarlavha
              qoladi — "Beyjikni skanerlang" (amal), "Kirish" u bilan
              raqobatlashmaydi. */}
          <div className="flex flex-col items-center gap-1.5">
            <h1 className="text-2xs font-medium uppercase tracking-[0.3em] text-(--brand-gold-deep)">
              MebeliX MES · Kirish
            </h1>
            {/* Chap paneldagi o'lcham chizig'ining aks-sadosi */}
            <svg
              width="96"
              height="10"
              aria-hidden="true"
              className="mt-2 text-(--brand-gold)"
            >
              <line
                x1="1"
                y1="5"
                x2="95"
                y2="5"
                stroke="currentColor"
                strokeOpacity="0.7"
              />
              <line
                x1="1"
                y1="0.5"
                x2="1"
                y2="9.5"
                stroke="currentColor"
                strokeOpacity="0.7"
              />
              <line
                x1="95"
                y1="0.5"
                x2="95"
                y2="9.5"
                stroke="currentColor"
                strokeOpacity="0.7"
              />
            </svg>
          </div>

          {/* Beyjik — sahifaning ASOSIY yo'li. Gap chastotada emas (skan ikkala
              holatda ham tinglanadi), BELGIDA: monoblokka kelgan odam forma
              ko'rsa terishga urinadi, chizilgan beyjik esa "kartani ko'taring"
              deydi. */}
          {!showPassword && <BadgePrompt pending={badge.isPending} />}

          {!!badgeError && (
            <div
              role="alert"
              className="rounded-md border border-destructive/30 bg-destructive/5 px-3 py-2.5 text-sm text-destructive"
            >
              {badgeError}
            </div>
          )}

          {showPassword && (
            <div className="grid gap-4">
              <FormField
                control={form.control}
                name="username"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Foydalanuvchi nomi yoki telefon</FormLabel>
                    <FormControl>
                      <Input
                        placeholder="foydalanuvchi nomi yoki +998 90 123-45-67"
                        type="text"
                        autoComplete="username"
                        // `autoFocus` YO'Q: forma tugma bosilganda ochiladi,
                        // fokus esa darhol tugmaga qaytib `onBlur` tekshiruvini
                        // ishga tushirardi — foydalanuvchi bitta ham harf
                        // yozmasdan "majburiy" xatosini ko'rardi.
                        className="h-11"
                        {...field}
                        // TELEFON YOZILSA — jonli ajratgich, foydalanuvchi
                        // nomiga TEGILMAYDI. Maydon ikki xil qiymat qabul
                        // qiladi, shuning uchun formatlash shartli: qiymatda
                        // faqat +, raqam, bo'shliq va tire bo'lsa VA kamida uch
                        // raqam terilgan bo'lsa. "admin" kabi nom harf tufayli
                        // shartga tushmaydi; qo'yib yozilgan (paste) raqam ham
                        // shu yerdan o'tadi, chunki `onChange` paste'da ham
                        // ishlaydi. Ilgari formatlash umuman yo'q edi —
                        // "+998 90 123-45-67" faqat YUBORISHDA tozalanardi,
                        // ya'ni ekranda raqam ajratgichsiz turardi.
                        onChange={(e) => {
                          const v = e.target.value
                          const raqam = v.replace(/\D/g, "")
                          field.onChange(
                            /^[+\d\s-]*$/.test(v) && raqam.length >= 3
                              ? formatUzPhone(v, field.value)
                              : v,
                          )
                        }}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="password"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Parol</FormLabel>
                    <FormControl>
                      <PasswordInput
                        placeholder="Parol"
                        className="h-11"
                        {...field}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              {loginMutation.isError && (
                <div
                  role="alert"
                  className="rounded-md border border-destructive/30 bg-destructive/5 px-3 py-2.5 text-sm text-destructive"
                >
                  {extractErrorMessage(loginMutation.error)}
                </div>
              )}

              <LoadingButton
                type="submit"
                className="h-11 text-base"
                loading={loginMutation.isPending}
              >
                Kirish
              </LoadingButton>
            </div>
          )}

          {/* Ikkinchi yo'l HAR IKKALA holatda bir joyda — pastda, ajratgich
              ostida. Almashtirish qaytariladi: ilgari parolga o'tgan odam
              beyjikka qayta olmasdi. */}
          <div className="flex flex-col items-center border-t pt-5">
            {/* Havola ko'rinishida (ikonka + doimiy underline): sensor
                ekranda hover yo'q, kulrang ghost matn bosiladigan narsaga
                o'xshamasdi. */}
            <Button
              type="button"
              variant="ghost"
              className="text-muted-foreground underline decoration-muted-foreground/40 underline-offset-4 hover:decoration-current"
              onClick={() => setShowPassword(!showPassword)}
            >
              {showPassword ? (
                <>
                  <IdCard /> Beyjik bilan kirish
                </>
              ) : (
                <>
                  <KeyRound /> Parol bilan kirish
                </>
              )}
            </Button>
          </div>
        </form>
      </Form>

      {/* Bir nechta postga biriktirilgan hodim qaysi biriga kirayotganini aytadi */}
      <Dialog
        open={!!choice}
        onOpenChange={(o) => {
          if (o) return
          setChoice(null)
          // Dialog bekor qilinganda mutatsiya ham tozalanadi: aks holda
          // "POST_CHOICE" signal xatosi ekranda haqiqiy xato bo'lib qolardi.
          badge.reset()
        }}
      >
        <DialogContent className="sm:max-w-sm">
          <DialogHeader>
            <DialogTitle>{choice?.employeeName} — qaysi postda?</DialogTitle>
          </DialogHeader>
          <div className="grid gap-2">
            {choice?.posts.map((p) => (
              <Button
                key={p.id}
                variant="outline"
                className="h-14 justify-start text-base font-bold"
                disabled={badge.isPending}
                onClick={() =>
                  badge.mutate({ badgeId: choice.badgeId, postId: p.id })
                }
              >
                {p.name}
              </Button>
            ))}
          </div>
        </DialogContent>
      </Dialog>
    </AuthLayout>
  )
}
