import { zodResolver } from "@hookform/resolvers/zod"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useNavigate } from "@tanstack/react-router"
import { Plus } from "lucide-react"
import { useState } from "react"
import { useForm } from "react-hook-form"
import { z } from "zod"

import { OrdersService } from "@/client"
import { AddClient } from "@/components/Clients/AddClient"
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
import { getClientsQueryOptions } from "@/queries/mes"
import { handleError } from "@/utils"

const formSchema = z.object({
  client_id: z.string().min(1, "Mijozni tanlang"),
  deadline: z.string().optional(),
  priority: z.enum(["low", "medium", "high", "urgent"]),
  amount: z.string().optional(),
  notes: z.string().optional(),
})

type FormValues = z.infer<typeof formSchema>

export function AddOrder() {
  const [open, setOpen] = useState(false)
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const { data: clients } = useQuery(getClientsQueryOptions())

  const form = useForm<FormValues>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      client_id: "",
      deadline: "",
      priority: "medium",
      amount: "",
      notes: "",
    },
  })

  const mutation = useMutation({
    mutationFn: (data: FormValues) =>
      OrdersService.createOrder({
        requestBody: {
          client_id: Number(data.client_id),
          deadline: data.deadline || null,
          priority: data.priority,
          amount: data.amount || null,
          notes: data.notes || null,
        },
      }),
    onSuccess: (order) => {
      showSuccessToast(`Buyurtma yaratildi: ${order.number}`)
      form.reset()
      setOpen(false)
      navigate({
        to: "/orders/$orderId",
        params: { orderId: String(order.id) },
      })
    },
    onError: handleError(showErrorToast),
    onSettled: () => queryClient.invalidateQueries({ queryKey: ["orders"] }),
  })

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button>
          <Plus /> Yangi buyurtma
        </Button>
      </DialogTrigger>
      <DialogContent className="max-w-md">
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
                  <div className="flex gap-2">
                    <Select value={field.value} onValueChange={field.onChange}>
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
                    <AddClient
                      trigger={
                        <Button
                          type="button"
                          variant="outline"
                          size="icon"
                          title="Yangi mijoz"
                        >
                          <Plus />
                        </Button>
                      }
                      onCreated={(c) => field.onChange(String(c.id))}
                    />
                  </div>
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
                      <Input type="date" {...field} />
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
            <FormField
              control={form.control}
              name="amount"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Summa (so'm)</FormLabel>
                  <FormControl>
                    <Input type="number" min="0" {...field} />
                  </FormControl>
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="notes"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Izoh</FormLabel>
                  <FormControl>
                    <Input
                      {...field}
                      placeholder="Maxsus talablar (masalan, qora kromka)"
                    />
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
