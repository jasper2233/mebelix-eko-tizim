import { zodResolver } from "@hookform/resolvers/zod"
import { useMutation, useQuery } from "@tanstack/react-query"
import { createFileRoute, redirect, useNavigate } from "@tanstack/react-router"
import { useState } from "react"
import { useForm } from "react-hook-form"
import { z } from "zod"

import type { Body_login_access_token as AccessToken, ApiError } from "@/client"
import { LoginService, UsersService } from "@/client"
import { AuthLayout } from "@/components/Common/AuthLayout"
import { BadgePrompt } from "@/components/Common/BadgePrompt"
import { type PinEmployeeOption, PinPad } from "@/components/Common/PinPad"
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
import { extractErrorMessage } from "@/utils"

// Sxema modul darajasida EMAS, funksiya ichida: `routeTree.gen.ts` marshrut
// modulini statik import qiladi, shuning uchun top-level `z.object(...)` zod'ni
// entry chunk'ka tortardi — formasi umuman yo'q terminal va TABLO kioski ham
// har cold start'da uni yuklab, parse qilardi.
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

/** Kirish usuli. Beyjik — asosiy yo'l; PIN — skaneri yo'q post uchun (ARRA);
 * parol — ofis (admin/manager/texnolog), tsexda ishlamaydi. */
type Mode = "badge" | "pin" | "password"

const MODE_LABELS: Record<Mode, string> = {
  badge: "Beyjik bilan kirish",
  pin: "Kod bilan kirish",
  password: "Parol bilan kirish",
}

/** 409 POST_CHOICE dan keyin qaysi usul bilan qayta urinish kerakligi. Beyjikda
 * QR matni, PIN'da esa hodim + terilgan kod saqlanadi. */
type Pending =
  | { via: "badge"; badgeId: string }
  | { via: "pin"; employeeId: number; pin: string }

function Login() {
  const navigate = useNavigate()
  const { loginMutation } = useAuth()
  const [formSchema] = useState(makeFormSchema)
  const [mode, setMode] = useState<Mode>("badge")
  const [employee, setEmployee] = useState<PinEmployeeOption | null>(null)
  const [digits, setDigits] = useState("")
  // Bir nechta postga biriktirilgan hodim: server 409 bilan ro'yxat qaytaradi
  const [choice, setChoice] = useState<{
    pending: Pending
    employeeName: string
    posts: PostChoice[]
  } | null>(null)

  // Ro'yxat FAQAT kod rejimida so'raladi: beyjik yo'lida u hech qachon
  // ko'rinmaydi, ya'ni monoblok uni bekorga yuklamasin.
  const { data: pinEmployees } = useQuery({
    queryKey: ["pin-employees"],
    queryFn: () => LoginService.listPinEmployees(),
    enabled: mode === "pin",
    staleTime: 60_000,
  })

  // 409 detali OBYEKT bo'ladi (odatdagi xatolarda — satr): hodim bir nechta
  // postga biriktirilgan, qaysi biriga kirayotganini o'zi tanlaydi. Ikkala
  // usulda ham bir xil, faqat qayta urinish ma'lumoti farq qiladi.
  const postChoice = (e: unknown, pending: Pending) => {
    const { detail } = ((e as ApiError)?.body ?? {}) as {
      detail?: { code?: string; employee_name?: string; posts?: PostChoice[] }
    }
    if (detail?.code === "POST_CHOICE")
      setChoice({
        pending,
        employeeName: detail.employee_name ?? "",
        posts: detail.posts ?? [],
      })
  }

  const badge = useMutation({
    mutationFn: (v: { badgeId: string; postId?: number }) =>
      LoginService.loginWithBadge({
        requestBody: { badge_id: v.badgeId, post_id: v.postId ?? null },
      }),
    onSuccess: () => {
      setChoice(null)
      navigate({ to: "/" })
    },
    onError: (e, v) => postChoice(e, { via: "badge", badgeId: v.badgeId }),
  })

  const pin = useMutation({
    mutationFn: (v: { employeeId: number; pin: string; postId?: number }) =>
      LoginService.loginWithPin({
        requestBody: {
          employee_id: v.employeeId,
          pin: v.pin,
          post_id: v.postId ?? null,
        },
      }),
    onSuccess: () => {
      setChoice(null)
      navigate({ to: "/" })
    },
    onError: (e, v) => {
      setDigits("")
      postChoice(e, { via: "pin", employeeId: v.employeeId, pin: v.pin })
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
    criteriaMode: "all",
    defaultValues: {
      username: "",
      password: "",
    },
  })

  const onSubmit = (data: FormData) => {
    if (loginMutation.isPending) return
    // Maydon IKKI xil qiymat qabul qiladi: foydalanuvchi nomi yoki telefon.
    // Shuning uchun bu yerda yozish paytida formatlash YO'Q — `formatUzPhone`
    // harflarni tashlab yuborardi va "admin" deb yozib bo'lmasdi.
    // Faqat yuborishdan oldin tozalaymiz: qiymat telefonga o'xshasa (faqat
    // +, raqam, bo'shliq, tire) ajratgichlar olib tashlanadi — shunda
    // "+998 90 123-45-67" ko'rinishida joylashtirilgan raqam ham ishlaydi.
    // Foydalanuvchi nomiga tegilmaydi: unda boshqa belgilar bor.
    const username = /^\+?[\d\s-]+$/.test(data.username.trim())
      ? data.username.replace(/[\s-]+/g, "")
      : data.username.trim()
    loginMutation.mutate({ ...data, username })
  }

  const badgeError =
    badge.isError && !choice ? extractErrorMessage(badge.error as ApiError) : ""

  return (
    <AuthLayout>
      <Form {...form}>
        <form
          onSubmit={form.handleSubmit(onSubmit)}
          className="flex flex-col gap-6"
        >
          {/* Markazlashgan: tsexdagi monoblokka kelgan odamning ko'zi markazga
              tushadi va u yerda bitta ish turadi — beyjikni skanerlash. */}
          <div className="flex flex-col items-center gap-1.5">
            <p className="text-2xs font-medium uppercase tracking-[0.3em] text-(--brand-gold-deep)">
              MebeliX MES
            </p>
            <h1 className="text-3xl font-bold tracking-tight">Kirish</h1>
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
          {mode === "badge" && <BadgePrompt pending={badge.isPending} />}

          {mode === "pin" && (
            <PinPad
              employees={pinEmployees ?? []}
              selected={employee}
              onSelect={(e) => {
                setEmployee(e)
                setDigits("")
                pin.reset()
              }}
              digits={digits}
              onDigits={setDigits}
              onComplete={(code) =>
                employee && pin.mutate({ employeeId: employee.id, pin: code })
              }
              pending={pin.isPending}
              error={
                pin.isError && !choice
                  ? extractErrorMessage(pin.error as ApiError)
                  : ""
              }
            />
          )}

          {!!badgeError && (
            <div
              role="alert"
              className="rounded-md border border-destructive/30 bg-destructive/5 px-3 py-2.5 text-sm text-destructive"
            >
              {badgeError}
            </div>
          )}

          {mode === "password" && (
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
                    <div className="flex items-center">
                      <FormLabel>Parol</FormLabel>
                    </div>
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
                  {extractErrorMessage(loginMutation.error as ApiError)}
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

          {/* Boshqa yo'llar HAR DOIM bir joyda — pastda, ajratgich ostida.
              Almashtirish qaytariladi: ilgari parolga o'tgan odam beyjikka
              qayta olmasdi. */}
          <div className="flex flex-wrap items-center justify-center gap-1 border-t pt-5">
            {(["badge", "pin", "password"] as const)
              .filter((m) => m !== mode)
              .map((m) => (
                <Button
                  key={m}
                  type="button"
                  variant="ghost"
                  className="text-muted-foreground"
                  onClick={() => {
                    setMode(m)
                    setEmployee(null)
                    setDigits("")
                  }}
                >
                  {MODE_LABELS[m]}
                </Button>
              ))}
          </div>
        </form>
      </Form>

      {/* Bir nechta postga biriktirilgan hodim qaysi biriga kirayotganini aytadi */}
      <Dialog open={!!choice} onOpenChange={(o) => !o && setChoice(null)}>
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
                disabled={badge.isPending || pin.isPending}
                onClick={() =>
                  choice.pending.via === "badge"
                    ? badge.mutate({
                        badgeId: choice.pending.badgeId,
                        postId: p.id,
                      })
                    : pin.mutate({
                        employeeId: choice.pending.employeeId,
                        pin: choice.pending.pin,
                        postId: p.id,
                      })
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
