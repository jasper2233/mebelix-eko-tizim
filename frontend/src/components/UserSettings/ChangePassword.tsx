import { zodResolver } from "@hookform/resolvers/zod"
import { useMutation } from "@tanstack/react-query"
import { useForm } from "react-hook-form"
import { toast } from "sonner"
import { z } from "zod"

import { type UpdatePassword, UsersService } from "@/client"
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form"
import { LoadingButton } from "@/components/ui/loading-button"
import { PasswordInput } from "@/components/ui/password-input"
import { passwordSchema } from "@/lib/validation"
import { handleError } from "@/utils"

const formSchema = z
  .object({
    // Joriy parolga kuch sxemasi QO'LLANMAYDI: eski/seed parol bugungi siyosatga mos kelmasligi mumkin,
    // backend uni faqat hash bilan solishtiradi — aks holda parolni umuman almashtirib bo'lmasdi.
    current_password: z.string().min(1, { message: "Joriy parol majburiy" }),
    new_password: passwordSchema,
    confirm_password: z.string().min(1, { message: "Parolni tasdiqlang" }),
  })
  .refine((data) => data.new_password === data.confirm_password, {
    message: "Parollar mos emas",
    path: ["confirm_password"],
  })

type FormData = z.infer<typeof formSchema>

export const ChangePassword = () => {
  const form = useForm<FormData>({
    resolver: zodResolver(formSchema),
    mode: "onSubmit",
    defaultValues: {
      current_password: "",
      new_password: "",
      confirm_password: "",
    },
  })

  const mutation = useMutation({
    mutationFn: (data: UpdatePassword) =>
      UsersService.updatePasswordMe({ body: data }),
    onSuccess: () => {
      toast.success("Parol muvaffaqiyatli yangilandi")
      form.reset()
    },
    onError: handleError,
  })

  // confirm_password faqat brauzerda tekshiriladi — serverga yuborilmaydi
  const onSubmit = ({ current_password, new_password }: FormData) =>
    mutation.mutate({ current_password, new_password })

  return (
    <div className="max-w-md">
      <h3 className="py-4 text-base font-semibold">Parolni o'zgartirish</h3>
      <Form {...form}>
        <form
          onSubmit={form.handleSubmit(onSubmit)}
          className="flex flex-col gap-4"
        >
          <FormField
            control={form.control}
            name="current_password"
            render={({ field, fieldState }) => (
              <FormItem>
                <FormLabel>Joriy parol</FormLabel>
                <FormControl>
                  <PasswordInput
                    placeholder="••••••••"
                    aria-invalid={fieldState.invalid}
                    {...field}
                  />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />

          <FormField
            control={form.control}
            name="new_password"
            render={({ field, fieldState }) => (
              <FormItem>
                <FormLabel>Yangi parol</FormLabel>
                <FormControl>
                  <PasswordInput
                    placeholder="••••••••"
                    aria-invalid={fieldState.invalid}
                    {...field}
                  />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />

          <FormField
            control={form.control}
            name="confirm_password"
            render={({ field, fieldState }) => (
              <FormItem>
                <FormLabel>Parolni tasdiqlash</FormLabel>
                <FormControl>
                  <PasswordInput
                    placeholder="••••••••"
                    aria-invalid={fieldState.invalid}
                    {...field}
                  />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />

          <LoadingButton
            type="submit"
            loading={mutation.isPending}
            className="self-start"
          >
            Parolni yangilash
          </LoadingButton>
        </form>
      </Form>
    </div>
  )
}
