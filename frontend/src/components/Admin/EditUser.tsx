import { zodResolver } from "@hookform/resolvers/zod"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { Pencil } from "lucide-react"
import { useState } from "react"
import { useForm } from "react-hook-form"
import { z } from "zod"

import { type UserAdminUpdate, type UserRead, UsersService } from "@/client"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { DropdownMenuItem } from "@/components/ui/dropdown-menu"
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
import useCustomToast from "@/hooks/useCustomToast"
import { optionalNameSchema, optionalPasswordSchema, phoneSchema } from "@/lib/validation"
import { handleError } from "@/utils"

const formSchema = z
  .object({
    phone: phoneSchema,
    name: optionalNameSchema,
    password: optionalPasswordSchema,
    confirm_password: z.string().optional(),
    is_superuser: z.boolean().optional(),
    is_active: z.boolean().optional(),
  })
  .refine((data) => !data.password || data.password === data.confirm_password, {
    message: "Parollar mos emas",
    path: ["confirm_password"],
  })

type FormData = z.infer<typeof formSchema>

interface EditUserProps {
  user: UserRead
  onSuccess: () => void
}

const EditUser = ({ user, onSuccess }: EditUserProps) => {
  const [isOpen, setIsOpen] = useState(false)
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()

  const form = useForm<FormData>({
    resolver: zodResolver(formSchema),
    mode: "onBlur",
    criteriaMode: "all",
    defaultValues: {
      phone: user.phone,
      name: user.name ?? undefined,
      is_superuser: user.is_superuser,
      is_active: user.is_active,
    },
  })

  const mutation = useMutation({
    mutationFn: (requestBody: UserAdminUpdate) =>
      UsersService.updateUser({
        userId: Number.parseInt(user.id, 10),
        requestBody,
      }),
    onSuccess: () => {
      showSuccessToast("Foydalanuvchi muvaffaqiyatli yangilandi")
      setIsOpen(false)
      onSuccess()
    },
    onError: handleError(showErrorToast),
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["users"] })
    },
  })

  const onSubmit = (data: FormData) => {
    const payload: UserAdminUpdate = {
      phone: data.phone,
      name: data.name,
      is_superuser: data.is_superuser,
      is_active: data.is_active,
    }
    if (data.password) {
      payload.password = data.password
    }
    mutation.mutate(payload)
  }

  return (
    <Dialog open={isOpen} onOpenChange={setIsOpen}>
      <DropdownMenuItem
        onSelect={(e) => e.preventDefault()}
        onClick={() => setIsOpen(true)}
      >
        <Pencil />
        Foydalanuvchini tahrirlash
      </DropdownMenuItem>
      <DialogContent className="sm:max-w-md">
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)}>
            <DialogHeader>
              <DialogTitle>Foydalanuvchini tahrirlash</DialogTitle>
              <DialogDescription>
                Foydalanuvchi ma'lumotlarini quyida yangilang.
              </DialogDescription>
            </DialogHeader>
            <div className="grid gap-4 py-4">
              <FormField
                control={form.control}
                name="phone"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>
                      Telefon <span className="text-destructive">*</span>
                    </FormLabel>
                    <FormControl>
                      <Input
                        placeholder="+998901234567"
                        type="tel"
                        {...field}
                        required
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="name"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>To'liq ism</FormLabel>
                    <FormControl>
                      <Input placeholder="To'liq ism" type="text" {...field} />
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
                    <FormLabel>Parol o'rnatish</FormLabel>
                    <FormControl>
                      <Input
                        placeholder="Parol"
                        type="password"
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
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Parolni tasdiqlash</FormLabel>
                    <FormControl>
                      <Input
                        placeholder="Parol"
                        type="password"
                        {...field}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="is_superuser"
                render={({ field }) => (
                  <FormItem className="flex items-center gap-3 space-y-0">
                    <FormControl>
                      <Checkbox
                        checked={field.value}
                        onCheckedChange={field.onChange}
                      />
                    </FormControl>
                    <FormLabel className="font-normal">Admin?</FormLabel>
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="is_active"
                render={({ field }) => (
                  <FormItem className="flex items-center gap-3 space-y-0">
                    <FormControl>
                      <Checkbox
                        checked={field.value}
                        onCheckedChange={field.onChange}
                      />
                    </FormControl>
                    <FormLabel className="font-normal">Faol?</FormLabel>
                  </FormItem>
                )}
              />
            </div>

            <DialogFooter>
              <DialogClose asChild>
                <Button variant="outline" disabled={mutation.isPending}>
                  Bekor qilish
                </Button>
              </DialogClose>
              <LoadingButton type="submit" loading={mutation.isPending}>
                Saqlash
              </LoadingButton>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  )
}

export default EditUser
