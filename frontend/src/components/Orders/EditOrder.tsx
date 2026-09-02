// Buyurtmani tahrirlash (manager): qoralamada hamma maydon, tasdiqlangandan
// keyin mijozdan tashqari (backend ham shu qoidani ushlaydi).

import { zodResolver } from "@hookform/resolvers/zod"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { Pencil } from "lucide-react"
import { useState } from "react"
import { useForm } from "react-hook-form"

import { type OrderDetail, OrdersService } from "@/client"
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
import { moneyToInput } from "@/lib/validation"
import { crudCallbacks } from "@/queries/mes"

export function EditOrder({
  order,
  onSaved,
}: {
  order: OrderDetail
  onSaved: () => void
}) {
  const [open, setOpen] = useState(false)
  const queryClient = useQueryClient()
  const cb = crudCallbacks(queryClient, ["orders"], "Buyurtma yangilandi")
  const isDraft = order.status === "draft"

  const form = useForm<FormValues>({
    resolver: zodResolver(formSchema),
    values: {
      client_id: String(order.client_id),
      deadline: order.deadline ?? "",
      priority: order.priority,
      amount: moneyToInput(order.amount),
      advance_payment: moneyToInput(order.advance_payment),
      notes: order.notes ?? "",
    },
  })

  const mutation = useMutation({
    mutationFn: (data: FormValues) =>
      OrdersService.updateOrder({
        path: { order_id: order.id },
        body: toRequestBody(data),
      }),
    ...cb,
    onSuccess: () => {
      cb.onSuccess()
      setOpen(false)
      onSaved()
    },
  })

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="outline">
          <Pencil /> Tahrirlash
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-xl">
        <DialogHeader>
          <DialogTitle>{order.number} — tahrirlash</DialogTitle>
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
                  <FormLabel>
                    Mijoz{" "}
                    {!isDraft && (
                      <span className="text-xs font-normal text-muted-foreground">
                        (faqat qoralamada almashtiriladi)
                      </span>
                    )}
                  </FormLabel>
                  <FormControl>
                    <ClientCombobox
                      value={field.value}
                      onChange={field.onChange}
                      initialLabel={order.client_name}
                      disabled={!isDraft}
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <OrderFields control={form.control} />
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
