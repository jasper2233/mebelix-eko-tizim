import { zodResolver } from "@hookform/resolvers/zod"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { useState } from "react"
import { useForm } from "react-hook-form"
import { z } from "zod"

import { type ClientRead, ClientsService } from "@/client"
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
import { PHONE_PATTERN } from "@/lib/validation"
import { handleError } from "@/utils"

const formSchema = z.object({
  full_name: z.string().trim().min(2, "Kamida 2 belgi").max(150),
  client_type: z.enum(["individual", "legal"]),
  phone: z
    .string()
    .regex(PHONE_PATTERN, "+998XXXXXXXXX formatida")
    .or(z.literal("")),
  phone_alt: z
    .string()
    .regex(PHONE_PATTERN, "+998XXXXXXXXX formatida")
    .or(z.literal("")),
  address: z.string().max(255).optional(),
  inn: z.string().max(20).optional(),
  notes: z.string().optional(),
})

type FormValues = z.infer<typeof formSchema>

export function AddClient({
  trigger,
  onCreated,
}: {
  trigger?: React.ReactNode
  onCreated?: (client: ClientRead) => void
}) {
  const [open, setOpen] = useState(false)
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()

  const form = useForm<FormValues>({
    resolver: zodResolver(formSchema),
    mode: "onBlur",
    defaultValues: {
      full_name: "",
      client_type: "individual",
      phone: "",
      phone_alt: "",
      address: "",
      inn: "",
      notes: "",
    },
  })

  const mutation = useMutation({
    mutationFn: (data: FormValues) =>
      ClientsService.createClient({
        requestBody: {
          full_name: data.full_name,
          client_type: data.client_type,
          phone: data.phone || null,
          phone_alt: data.phone_alt || null,
          address: data.address || null,
          inn: data.inn || null,
          notes: data.notes || null,
        },
      }),
    onSuccess: (client) => {
      showSuccessToast("Mijoz qo'shildi")
      form.reset()
      setOpen(false)
      onCreated?.(client)
    },
    onError: handleError(showErrorToast),
    onSettled: () => queryClient.invalidateQueries({ queryKey: ["clients"] }),
  })

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        {trigger ?? <Button>+ Yangi mijoz</Button>}
      </DialogTrigger>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Yangi mijoz</DialogTitle>
          <DialogDescription>
            Mijoz ma'lumotlarini kiriting (TZ 4.6)
          </DialogDescription>
        </DialogHeader>
        <Form {...form}>
          <form
            onSubmit={form.handleSubmit((d) => mutation.mutate(d))}
            className="space-y-3"
          >
            <FormField
              control={form.control}
              name="full_name"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>F.I.Sh / Kompaniya nomi</FormLabel>
                  <FormControl>
                    <Input {...field} autoFocus />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <div className="grid grid-cols-2 gap-3">
              <FormField
                control={form.control}
                name="client_type"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Turi</FormLabel>
                    <Select value={field.value} onValueChange={field.onChange}>
                      <FormControl>
                        <SelectTrigger className="w-full">
                          <SelectValue />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        <SelectItem value="individual">Jismoniy</SelectItem>
                        <SelectItem value="legal">Yuridik</SelectItem>
                      </SelectContent>
                    </Select>
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="inn"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>STIR (INN)</FormLabel>
                    <FormControl>
                      <Input {...field} placeholder="Yuridik shaxs uchun" />
                    </FormControl>
                  </FormItem>
                )}
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <FormField
                control={form.control}
                name="phone"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Telefon</FormLabel>
                    <FormControl>
                      <Input {...field} placeholder="+998901234567" />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="phone_alt"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Qo'shimcha tel.</FormLabel>
                    <FormControl>
                      <Input {...field} placeholder="+998..." />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>
            <FormField
              control={form.control}
              name="address"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Manzil</FormLabel>
                  <FormControl>
                    <Input {...field} />
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
