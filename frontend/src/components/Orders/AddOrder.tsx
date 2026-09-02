import { zodResolver } from "@hookform/resolvers/zod"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { useNavigate } from "@tanstack/react-router"
import { Plus } from "lucide-react"
import { useState } from "react"
import { useForm } from "react-hook-form"
import { toast } from "sonner"

import { OrdersService } from "@/client"
import { ClientCombobox } from "@/components/Clients/ClientCombobox"
import {
  type FormValues,
  formSchema,
  OrderFields,
  toRequestBody,
} from "@/components/Orders/orderForm"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form"
import { LoadingButton } from "@/components/ui/loading-button"
import { handleError } from "@/utils"

export function AddOrder() {
  const [open, setOpen] = useState(false)
  const queryClient = useQueryClient()
  const navigate = useNavigate()

  const form = useForm<FormValues>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      client_id: "",
      deadline: "",
      priority: "medium",
      amount: "",
      advance_payment: "",
      notes: "",
    },
  })

  const mutation = useMutation({
    mutationFn: (data: FormValues) =>
      OrdersService.createOrder({ body: toRequestBody(data) }),
    onSuccess: ({ data: order }) => {
      toast.success(`Buyurtma yaratildi: ${order.number}`)
      form.reset()
      setOpen(false)
      navigate({
        to: "/orders/$orderId",
        params: { orderId: String(order.id) },
      })
    },
    onError: handleError,
    onSettled: () => queryClient.invalidateQueries({ queryKey: ["orders"] }),
  })

  return (
    // Yopilganda formani tozalaymiz — aks holda keyingi ochilishda ko'rinmas
    // (combobox unmount bo'lgani uchun nomsiz) mijoz forma ichida qolib ketardi
    <Dialog
      open={open}
      onOpenChange={(o) => {
        setOpen(o)
        if (!o) form.reset()
      }}
    >
      <DialogTrigger asChild>
        <Button>
          <Plus /> Yangi buyurtma
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-xl">
        <DialogHeader>
          <DialogTitle>Yangi buyurtma</DialogTitle>
          <DialogDescription>
            Raqam tizim tomonidan beriladi (B-YYYY-NNN). Fayl keyin texnolog
            tomonidan yuklanadi.
          </DialogDescription>
        </DialogHeader>
        <Form {...form}>
          <form
            onSubmit={form.handleSubmit((d) => mutation.mutate(d))}
            className="space-y-3"
          >
            <FormField
              control={form.control}
              name="client_id"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Mijoz</FormLabel>
                  <FormControl>
                    <ClientCombobox
                      value={field.value}
                      onChange={field.onChange}
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <OrderFields
              control={form.control}
              notesPlaceholder="Maxsus talablar (masalan, qora kromka)"
            />
            <DialogFooter className="pt-2">
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
