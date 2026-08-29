import { zodResolver } from "@hookform/resolvers/zod"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { type ReactNode, useState } from "react"
import { useForm } from "react-hook-form"
import { toast } from "sonner"
import { z } from "zod"

import { UsersService, type UserUpdate } from "@/client"
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
import { useCurrentUser } from "@/hooks/useCurrentUser"
import { cn } from "@/lib/utils"
import {
  formattedPhoneSchema,
  formatUzPhone,
  optionalNameSchema,
} from "@/lib/validation"
import { handleError } from "@/utils"

const formSchema = z.object({
  name: optionalNameSchema,
  phone: formattedPhoneSchema,
})

type FormData = z.infer<typeof formSchema>

/** Ko'rish va tahrir shakli BITTA joyda. Ilgari har maydon o'z juftini
 * yozardi va ular ajralib ketgandi: ism bo'sh bo'lsa "—" chiqarardi,
 * telefon esa jimgina bo'sh qatorni. */
function ProfileField({
  label,
  editMode,
  value,
  children,
}: {
  label: string
  editMode: boolean
  value: string | undefined
  children: ReactNode
}) {
  return (
    <FormItem>
      <FormLabel>{label}</FormLabel>
      {editMode ? (
        <>
          <FormControl>{children}</FormControl>
          <FormMessage />
        </>
      ) : (
        <p
          className={cn(
            "py-2 truncate max-w-sm",
            !value && "text-muted-foreground",
          )}
        >
          {value || "—"}
        </p>
      )}
    </FormItem>
  )
}

export const UserInformation = () => {
  const queryClient = useQueryClient()
  const [editMode, setEditMode] = useState(false)
  const { currentUser } = useCurrentUser()

  const form = useForm<FormData>({
    resolver: zodResolver(formSchema),
    mode: "onBlur",
    defaultValues: {
      name: currentUser?.name ?? undefined,
      phone: formatUzPhone(currentUser?.phone ?? ""),
    },
  })

  const mutation = useMutation({
    mutationFn: (data: UserUpdate) => UsersService.updateUserMe({ body: data }),
    onSuccess: () => {
      toast.success("Foydalanuvchi muvaffaqiyatli yangilandi")
      form.reset(form.getValues())
      setEditMode(false)
    },
    onError: handleError,
    onSettled: () => {
      // Faqat profil keshi — kalitsiz chaqiruv BUTUN ilova querylarini qayta so'rardi
      queryClient.invalidateQueries({ queryKey: ["currentUser"] })
    },
  })

  const onSubmit = (data: FormData) => {
    const updateData: UserUpdate = {}
    if (data.name !== currentUser?.name) {
      updateData.name = data.name
    }
    if (data.phone !== currentUser?.phone) {
      updateData.phone = data.phone
    }
    mutation.mutate(updateData)
  }

  const onCancel = () => {
    form.reset()
    setEditMode(false)
  }

  return (
    <div className="max-w-md">
      <h3 className="py-4 text-base font-semibold">
        Foydalanuvchi ma'lumotlari
      </h3>
      <Form {...form}>
        <form
          onSubmit={form.handleSubmit(onSubmit)}
          className="flex flex-col gap-4"
        >
          <FormField
            control={form.control}
            name="name"
            render={({ field }) => (
              <ProfileField
                label="To'liq ism"
                editMode={editMode}
                value={field.value}
              >
                <Input type="text" {...field} />
              </ProfileField>
            )}
          />

          <FormField
            control={form.control}
            name="phone"
            render={({ field }) => (
              <ProfileField
                label="Telefon"
                editMode={editMode}
                value={field.value}
              >
                <Input
                  type="tel"
                  inputMode="numeric"
                  placeholder="+998 90 123-45-67"
                  {...field}
                  onChange={(e) =>
                    field.onChange(formatUzPhone(e.target.value, field.value))
                  }
                />
              </ProfileField>
            )}
          />

          <div className="flex gap-3">
            {editMode ? (
              <>
                <LoadingButton
                  type="submit"
                  loading={mutation.isPending}
                  disabled={!form.formState.isDirty}
                >
                  Saqlash
                </LoadingButton>
                <Button
                  type="button"
                  variant="outline"
                  onClick={onCancel}
                  disabled={mutation.isPending}
                >
                  Bekor qilish
                </Button>
              </>
            ) : (
              <Button type="button" onClick={() => setEditMode(true)}>
                Tahrirlash
              </Button>
            )}
          </div>
        </form>
      </Form>
    </div>
  )
}
