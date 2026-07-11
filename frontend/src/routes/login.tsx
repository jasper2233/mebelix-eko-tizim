import { zodResolver } from "@hookform/resolvers/zod"
import { createFileRoute, redirect } from "@tanstack/react-router"
import { useForm } from "react-hook-form"
import { z } from "zod"

import type { Body_login_access_token as AccessToken, ApiError } from "@/client"
import { UsersService } from "@/client"
import { AuthLayout } from "@/components/Common/AuthLayout"
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
import useAuth from "@/hooks/useAuth"
import { extractErrorMessage } from "@/utils"

const formSchema = z.object({
  username: z
    .string()
    .min(1, { message: "Foydalanuvchi nomi yoki telefon majburiy" }),
  // Faqat bo'sh emasligi tekshiriladi — kuch talablari parol O'RNATISHDA qo'llanadi,
  // login'da esas mavjud (jumladan eski/seed) parol bilan kirish imkonini saqlash kerak.
  password: z.string().min(1, { message: "Parol majburiy" }),
}) satisfies z.ZodType<AccessToken>

type FormData = z.infer<typeof formSchema>

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
        title: "Kirish - MebeliX",
      },
    ],
  }),
})

function Login() {
  const { loginMutation } = useAuth()
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
    loginMutation.mutate(data)
  }

  return (
    <AuthLayout>
      <Form {...form}>
        <form
          onSubmit={form.handleSubmit(onSubmit)}
          className="flex flex-col gap-6"
        >
          <div className="flex flex-col gap-1.5">
            <p className="text-[11px] font-medium uppercase tracking-[0.3em] text-(--brand-gold-deep)">
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
                      placeholder="foydalanuvchi nomi yoki +998901234567"
                      type="text"
                      autoComplete="username"
                      className="h-11"
                      {...field}
                    />
                  </FormControl>
                  <FormMessage className="text-xs" />
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
                  <FormMessage className="text-xs" />
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
        </form>
      </Form>
    </AuthLayout>
  )
}
