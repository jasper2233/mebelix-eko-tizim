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
import { formatUzPhone, optionalFormattedPhoneSchema } from "@/lib/validation"
import { crudCallbacks } from "@/queries/mes"

const formSchema = z.object({
  full_name: z.string().trim().min(2, "Kamida 2 belgi").max(150),
  phone: optionalFormattedPhoneSchema,
  phone_alt: optionalFormattedPhoneSchema,
  address: z.string().max(255).optional(),
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
  const cb = crudCallbacks(queryClient, ["clients"], "Mijoz qo'shildi")

  const form = useForm<FormValues>({
    resolver: zodResolver(formSchema),
    mode: "onBlur",
    defaultValues: {
      full_name: "",
      phone: "",
      phone_alt: "",
      address: "",
      notes: "",
    },
  })

  const mutation = useMutation({
    mutationFn: (data: FormValues) =>
      ClientsService.createClient({
        body: {
          full_name: data.full_name,
          phone: data.phone || null,
          phone_alt: data.phone_alt || null,
          address: data.address || null,
          notes: data.notes || null,
        },
      }),
    ...cb,
    onSuccess: ({ data: client }) => {
      cb.onSuccess()
      form.reset()
      setOpen(false)
      onCreated?.(client)
    },
  })

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        {trigger ?? <Button>+ Yangi mijoz</Button>}
      </DialogTrigger>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Yangi mijoz</DialogTitle>
          <DialogDescription>Mijoz ma'lumotlarini kiriting</DialogDescription>
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
                name="phone"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Telefon</FormLabel>
                    <FormControl>
                      <Input
                        {...field}
                        inputMode="tel"
                        placeholder="+998 90 123 45 67"
                        onChange={(e) =>
                          field.onChange(
                            formatUzPhone(e.target.value, field.value),
                          )
                        }
                      />
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
                      <Input
                        {...field}
                        inputMode="tel"
                        placeholder="+998 90 123 45 67"
                        onChange={(e) =>
                          field.onChange(
                            formatUzPhone(e.target.value, field.value),
                          )
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
