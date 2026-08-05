import { zodResolver } from "@hookform/resolvers/zod"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { useState } from "react"
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
import { optionalNameSchema, phoneSchema } from "@/lib/validation"
import { handleError } from "@/utils"

const formSchema = z.object({
  name: optionalNameSchema,
  phone: phoneSchema,
})

type FormData = z.infer<typeof formSchema>

export const UserInformation = () => {
  const queryClient = useQueryClient()
  const [editMode, setEditMode] = useState(false)
  const { currentUser } = useCurrentUser()

  const form = useForm<FormData>({
    resolver: zodResolver(formSchema),
    mode: "onBlur",
    criteriaMode: "all",
    defaultValues: {
      name: currentUser?.name ?? undefined,
      phone: currentUser?.phone,
    },
  })

  const toggleEditMode = () => {
    setEditMode(!editMode)
  }

  const mutation = useMutation({
    mutationFn: (data: UserUpdate) =>
      UsersService.updateUserMe({ requestBody: data }),
    onSuccess: () => {
      toast.success("Foydalanuvchi muvaffaqiyatli yangilandi")
      form.reset(form.getValues())
      toggleEditMode()
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
    toggleEditMode()
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
            render={({ field }) =>
              editMode ? (
                <FormItem>
                  <FormLabel>To'liq ism</FormLabel>
                  <FormControl>
                    <Input type="text" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              ) : (
                <FormItem>
                  <FormLabel>To'liq ism</FormLabel>
                  <p
                    className={cn(
                      "py-2 truncate max-w-sm",
                      !field.value && "text-muted-foreground",
                    )}
                  >
                    {field.value || "N/A"}
                  </p>
                </FormItem>
              )
            }
          />

          <FormField
            control={form.control}
            name="phone"
            render={({ field }) =>
              editMode ? (
                <FormItem>
                  <FormLabel>Telefon</FormLabel>
                  <FormControl>
                    <Input type="tel" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              ) : (
                <FormItem>
                  <FormLabel>Telefon</FormLabel>
                  <p className="py-2 truncate max-w-sm">{field.value}</p>
                </FormItem>
              )
            }
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
              <Button type="button" onClick={toggleEditMode}>
                Tahrirlash
              </Button>
            )}
          </div>
        </form>
      </Form>
    </div>
  )
}
