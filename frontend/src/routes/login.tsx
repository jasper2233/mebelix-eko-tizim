import { zodResolver } from "@hookform/resolvers/zod"
import { useMutation } from "@tanstack/react-query"
import { createFileRoute, redirect, useNavigate } from "@tanstack/react-router"
import { KeyRound, Loader2, ScanLine } from "lucide-react"
import { useRef, useState } from "react"
import { useForm } from "react-hook-form"
import { z } from "zod"

import type { Body_login_access_token as AccessToken, ApiError } from "@/client"
import { LoginService, UsersService } from "@/client"
import { AuthLayout } from "@/components/Common/AuthLayout"
import { useScanFocus } from "@/components/Terminal/useKiosk"
import { Button } from "@/components/ui/button"
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
import { pairedDevice, savePairedDevice } from "@/lib/device"
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

/** Sexdagi bog'langan monoblok beyjik ekranidan boshlaydi, ofis — paroldan. */
type View = "badge" | "password" | "pair"

function Login() {
  const [device, setDevice] = useState(pairedDevice)
  const [view, setView] = useState<View>(() =>
    pairedDevice() ? "badge" : "password",
  )

  if (view === "badge" && device)
    return <BadgeLogin device={device} onPassword={() => setView("password")} />
  if (view === "pair")
    return (
      <PairDevice
        onPaired={(d) => {
          setDevice(d)
          setView("badge")
        }}
        onCancel={() => setView("password")}
      />
    )
  return (
    <PasswordLogin
      onBadge={device ? () => setView("badge") : undefined}
      onPair={() => setView("pair")}
    />
  )
}

// Sexdagi kirish. Ekranda bitta ish bor — beyjikni skanerlash, shuning uchun
// bitta yozuv va bitta katta belgi. Input ko'rinmaydi (skaner klaviatura kabi
// yozadi), lekin doim fokusda: `useScanFocus` terminaldagi bilan bir xil qoida.
function BadgeLogin({
  device,
  onPassword,
}: {
  device: NonNullable<ReturnType<typeof pairedDevice>>
  onPassword: () => void
}) {
  const navigate = useNavigate()
  const inputRef = useRef<HTMLInputElement>(null)
  const badge = useMutation({
    mutationFn: (badgeId: string) =>
      LoginService.loginWithBadge({
        requestBody: { badge_id: badgeId, device_token: device.token },
      }),
    onSuccess: () => navigate({ to: "/" }),
  })
  useScanFocus(!badge.isPending, inputRef)

  return (
    <AuthLayout>
      <div className="flex flex-col gap-6">
        <div className="flex flex-col gap-1.5">
          <p className="text-2xs font-medium uppercase tracking-[0.3em] text-(--brand-gold-deep)">
            {device.postName || "MebeliX MES"}
          </p>
          <h1 className="text-3xl font-bold tracking-tight">
            Beyjikni skanerlang
          </h1>
          <p className="text-muted-foreground">{device.machineName}</p>
        </div>

        <div className="flex flex-col items-center gap-4 rounded-xl border-2 border-dashed border-primary/30 py-10">
          {badge.isPending ? (
            <Loader2 className="size-16 animate-spin text-primary" />
          ) : (
            <ScanLine className="size-16 text-primary/70" />
          )}
          <p className="text-lg font-bold">
            {badge.isPending
              ? "Tekshirilmoqda..."
              : "Beyjik QR — skanerga tuting"}
          </p>
        </div>

        {/* Skaner yozadigan yagona maydon. Ko'rinmaydi: operator hech nima
            termaydi, ko'rinsa faqat chalg'itardi. */}
        <input
          ref={inputRef}
          className="sr-only"
          aria-label="Beyjik QR"
          onKeyDown={(e) => {
            if (e.key !== "Enter") return
            const el = e.target as HTMLInputElement
            const value = el.value.trim()
            el.value = ""
            if (value) badge.mutate(value)
          }}
        />

        {badge.isError && (
          <div
            role="alert"
            className="rounded-md border border-destructive/30 bg-destructive/5 px-3 py-2.5 text-sm text-destructive"
          >
            {extractErrorMessage(badge.error as ApiError)}
          </div>
        )}

        {/* Ofis xodimi shu monoblokka kirishi kerak bo'lganda */}
        <Button
          variant="ghost"
          className="text-muted-foreground"
          onClick={onPassword}
        >
          <KeyRound /> Parol bilan kirish
        </Button>
      </div>
    </AuthLayout>
  )
}

// Bir martalik kod monoblokni stanokka bog'laydi. Admin panelda "Ulanish kodi"
// bosilib, kod shu yerga teriladi — bir marta, o'rnatishda.
function PairDevice({
  onPaired,
  onCancel,
}: {
  onPaired: (d: NonNullable<ReturnType<typeof pairedDevice>>) => void
  onCancel: () => void
}) {
  const [code, setCode] = useState("")
  const pair = useMutation({
    mutationFn: (value: string) =>
      LoginService.pairTerminalDevice({ requestBody: { code: value } }),
    onSuccess: (r) => {
      const d = {
        token: r.token,
        machineName: r.machine_name,
        postName: r.post_name,
      }
      savePairedDevice(d)
      onPaired(d)
    },
  })

  return (
    <AuthLayout>
      <form
        className="flex flex-col gap-6"
        onSubmit={(e) => {
          e.preventDefault()
          if (code.trim() && !pair.isPending) pair.mutate(code.trim())
        }}
      >
        <div className="flex flex-col gap-1.5">
          <p className="text-2xs font-medium uppercase tracking-[0.3em] text-(--brand-gold-deep)">
            MebeliX MES
          </p>
          <h1 className="text-3xl font-bold tracking-tight">
            Terminalni bog'lash
          </h1>
          {/* Qaysi sahifa ekani ATAYLAB yozilgan: admin panelda ikkita ulanish
              kodi bor (Stanoklar — terminal, Printer agentlar — printerli
              kompyuter) va ikkalasi ham 8 belgili. */}
          <p className="text-muted-foreground">
            Admin panelning <b>Stanoklar</b> sahifasida shu stanok qatoridagi{" "}
            <b>Ulanish kodi</b> tugmasini bosing va kodni bu yerga tering. Bir
            marta — shundan keyin monoblokda beyjik bilan kiriladi.
          </p>
        </div>

        <Input
          autoFocus
          value={code}
          onChange={(e) => setCode(e.target.value.toUpperCase())}
          placeholder="Masalan: K7M2PQTX"
          maxLength={16}
          className="num h-14 text-center text-2xl font-black tracking-[0.35em]"
        />

        {pair.isError && (
          <div
            role="alert"
            className="rounded-md border border-destructive/30 bg-destructive/5 px-3 py-2.5 text-sm text-destructive"
          >
            {extractErrorMessage(pair.error as ApiError)}
          </div>
        )}

        <div className="grid gap-2">
          <LoadingButton
            type="submit"
            className="h-11 text-base"
            loading={pair.isPending}
            disabled={!code.trim()}
          >
            Bog'lash
          </LoadingButton>
          <Button variant="ghost" type="button" onClick={onCancel}>
            Bekor qilish
          </Button>
        </div>
      </form>
    </AuthLayout>
  )
}

function PasswordLogin({
  onBadge,
  onPair,
}: {
  onBadge?: () => void
  onPair: () => void
}) {
  const { loginMutation } = useAuth()
  const [formSchema] = useState(makeFormSchema)
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

  return (
    <AuthLayout>
      <Form {...form}>
        <form
          onSubmit={form.handleSubmit(onSubmit)}
          className="flex flex-col gap-6"
        >
          <div className="flex flex-col gap-1.5">
            <p className="text-2xs font-medium uppercase tracking-[0.3em] text-(--brand-gold-deep)">
              MebeliX MES
            </p>
            <h1 className="text-3xl font-bold tracking-tight">
              Tizimga kirish
            </h1>
            <p className="text-muted-foreground">
              Davom etish uchun ma'lumotlaringizni kiriting
            </p>
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
                      // Terminal va ofisda har kirishda ortiqcha bosish bo'lmasin
                      // (boshqa formalar ham birinchi maydonga fokus beradi)
                      autoFocus
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

            {/* Sexdagi monoblok: bog'langan bo'lsa beyjikka qaytish, bo'lmasa
                o'rnatishda bir marta bog'lash */}
            <Button
              variant="ghost"
              type="button"
              className="text-muted-foreground"
              onClick={onBadge ?? onPair}
            >
              <ScanLine />
              {onBadge ? "Beyjik bilan kirish" : "Terminalni bog'lash"}
            </Button>
          </div>
        </form>
      </Form>
    </AuthLayout>
  )
}
