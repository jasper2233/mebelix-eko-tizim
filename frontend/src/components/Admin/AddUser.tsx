import { zodResolver } from "@hookform/resolvers/zod"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { Plus } from "lucide-react"
import { useState } from "react"
import { useForm } from "react-hook-form"
import { toast } from "sonner"

import { type UserCreate, UsersService } from "@/client"
import {
  buildUserFormSchema,
  isMachineBoundRole,
  type UserFormData,
  UserFormFields,
} from "@/components/Admin/UserForm"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { Form } from "@/components/ui/form"
import { LoadingButton } from "@/components/ui/loading-button"
import { handleError } from "@/utils"

const formSchema = buildUserFormSchema(true)

export function AddUser() {
  const [isOpen, setIsOpen] = useState(false)
  const queryClient = useQueryClient()

  const form = useForm<UserFormData>({
    resolver: zodResolver(formSchema),
    mode: "onBlur",
    criteriaMode: "all",
    defaultValues: {
      phone: "",
      name: "",
      password: "",
      confirm_password: "",
      role: "manager",
      machine_id: "",
      is_superuser: false,
      is_active: true,
    },
  })

  const mutation = useMutation({
    mutationFn: (data: UserCreate) =>
      UsersService.createUser({ requestBody: data }),
    onSuccess: () => {
      toast.success("Foydalanuvchi muvaffaqiyatli yaratildi")
      form.reset()
      setIsOpen(false)
    },
    onError: handleError,
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["users"] })
    },
  })

  const onSubmit = (data: UserFormData) => {
    mutation.mutate({
      phone: data.phone,
      name: data.name,
      // Sxema parolni majburiy qiladi — "??" faqat tip uchun
      password: data.password ?? "",
      role: data.role,
      // Ish markazi faqat terminal/tablo rollarga tegishli — rol keyin almashtirilsa
      // yashirin qolgan tanlov ofis rolga ham jo'nab ketmasin
      machine_id:
        isMachineBoundRole(data.role) && data.machine_id
          ? Number(data.machine_id)
          : null,
      is_superuser: data.is_superuser,
      is_active: data.is_active,
    })
  }

  return (
    <Dialog open={isOpen} onOpenChange={setIsOpen}>
      <DialogTrigger asChild>
        <Button className="my-4">
          <Plus className="mr-2" />
          Foydalanuvchi qo'shish
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Foydalanuvchi qo'shish</DialogTitle>
          <DialogDescription>
            Yangi foydalanuvchi qo'shish uchun quyidagi maydonlarni to'ldiring.
          </DialogDescription>
        </DialogHeader>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)}>
            <UserFormFields form={form} passwordRequired />
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
