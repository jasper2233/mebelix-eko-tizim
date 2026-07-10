// Buyurtmani tahrirlash (manager): qoralamada hamma maydon, tasdiqlangandan
// keyin mijozdan tashqari (backend ham shu qoidani ushlaydi).

import { zodResolver } from "@hookform/resolvers/zod"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Pencil } from "lucide-react"
import { useState } from "react"
import { useForm } from "react-hook-form"
import { z } from "zod"

import { type OrderDetail, OrdersService } from "@/client"
import { Button } from "@/components/ui/button"
import { DatePicker } from "@/components/ui/date-picker"
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
import { Input } from "@/components/ui/input"
import { LoadingButton } from "@/components/ui/loading-button"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import useCustomToast from "@/hooks/useCustomToast"
import { PRIORITY_LABELS } from "@/lib/mes"
import { formatMoneyInput } from "@/lib/validation"
import { getClientsQueryOptions } from "@/queries/mes"
import { handleError } from "@/utils"

const money = (v: string) => v.replace(/\s+/g, "")

const formSchema = z
  .object({
    client_id: z.string().min(1, "Mijozni tanlang"),
    deadline: z.string().optional(),
    priority: z.enum(["low", "medium", "high", "urgent"]),
    amount: z.string().min(1, "Umumiy narxni kiriting"),
    advance_payment: z.string().optional(),
    notes: z.string().optional(),
  })
  .refine(
    (d) =>
      !d.advance_payment ||
      Number(money(d.advance_payment)) <= Number(money(d.amount)),
    {
      message: "Boshlang'ich to'lov umumiy narxdan oshmasligi kerak",
      path: ["advance_payment"],
    },
  )

type FormValues = z.infer<typeof formSchema>

export function EditOrder({
  order,
  onSaved,
}: {
  order: OrderDetail
  onSaved: () => void
}) {
  const [open, setOpen] = useState(false)
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const { data: clients } = useQuery(getClientsQueryOptions())
  const isDraft = order.status === "draft"

  const form = useForm<FormValues>({
    resolver: zodResolver(formSchema),
    values: {
      client_id: String(order.client_id),
      deadline: order.deadline ?? "",
      priority: order.priority,
      amount: formatMoneyInput(order.amount ?? ""),
      advance_payment: formatMoneyInput(order.advance_payment ?? ""),
      notes: order.notes ?? "",
    },
  })

  const mutation = useMutation({
    mutationFn: (data: FormValues) =>
      OrdersService.updateOrder({
        orderId: order.id,
        requestBody: {
          client_id: Number(data.client_id),
          deadline: data.deadline || null,
          priority: data.priority,
          amount: money(data.amount) || null,
          advance_payment: money(data.advance_payment ?? "") || null,
          notes: data.notes || null,
        },
      }),
    onSuccess: () => {
      showSuccessToast("Buyurtma yangilandi")
      setOpen(false)
      onSaved()
    },
    onError: handleError(showErrorToast),
    onSettled: () => queryClient.invalidateQueries({ queryKey: ["orders"] }),
  })

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="outline">
          <Pencil /> Tahrirlash
        </Button>
      </DialogTrigger>
      <DialogContent className="max-w-md">
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
                  <Select
                    value={field.value}
                    onValueChange={field.onChange}
                    disabled={!isDraft}
                  >
                    <FormControl>
                      <SelectTrigger className="w-full">
                        <SelectValue placeholder="Mijozni tanlang" />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      {clients?.data.map((c) => (
                        <SelectItem key={c.id} value={String(c.id)}>
                          {c.full_name} {c.phone ? `(${c.phone})` : ""}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <FormMessage />
                </FormItem>
              )}
            />
            <div className="grid grid-cols-2 gap-3">
              <FormField
                control={form.control}
                name="deadline"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Topshirish sanasi</FormLabel>
                    <FormControl>
                      <DatePicker
                        value={field.value ?? ""}
                        onChange={field.onChange}
                        className="w-full"
                      />
                    </FormControl>
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="priority"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Prioritet</FormLabel>
                    <Select value={field.value} onValueChange={field.onChange}>
                      <FormControl>
                        <SelectTrigger className="w-full">
                          <SelectValue />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        {Object.entries(PRIORITY_LABELS).map(
                          ([value, label]) => (
                            <SelectItem key={value} value={value}>
                              {label}
                            </SelectItem>
                          ),
                        )}
                      </SelectContent>
                    </Select>
                  </FormItem>
                )}
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <FormField
                control={form.control}
                name="amount"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Umumiy narx (so'm)</FormLabel>
                    <FormControl>
                      <Input
                        {...field}
                        inputMode="numeric"
                        className="num"
                        onChange={(e) =>
                          field.onChange(formatMoneyInput(e.target.value))
                        }
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="advance_payment"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Boshlang'ich to'lov (so'm)</FormLabel>
                    <FormControl>
                      <Input
                        {...field}
                        inputMode="numeric"
                        className="num"
                        onChange={(e) =>
                          field.onChange(formatMoneyInput(e.target.value))
                        }
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>
            <FormField
              control={form.control}
              name="notes"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Izoh</FormLabel>
                  <FormControl>
                    <Input {...field} />
                  </FormControl>
                </FormItem>
              )}
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
