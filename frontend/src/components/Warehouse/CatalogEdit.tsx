import { zodResolver } from "@hookform/resolvers/zod"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { useForm } from "react-hook-form"
import { z } from "zod"

import { type CatalogItemRead, CatalogService } from "@/client"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
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
import { crudCallbacks } from "@/queries/mes"

// Faqat OMBOR maydonlari. Kod, nom, o'lcham va guruh ataylab yo'q: ular
// katalogdan (`Katalog.xlsx` -> `scripts/catalog_import.py`) keladi va bu
// yerda o'zgartirilsa keyingi yuklashda ustiga yozilardi.
const formSchema = z.object({
  quantity: z
    .string()
    .trim()
    .regex(/^\d+([.,]\d{1,3})?$/, "Manfiy bo'lmagan son"),
  min_quantity: z
    .string()
    .trim()
    .regex(/^(\d+([.,]\d{1,3})?)?$/, "Manfiy bo'lmagan son yoki bo'sh"),
  location: z.string().trim().max(40, "Ko'pi bilan 40 belgi"),
  purchase_price: z.string().trim().regex(/^\d*$/, "Faqat raqam"),
  sale_price: z.string().trim().regex(/^\d*$/, "Faqat raqam"),
})

type FormValues = z.infer<typeof formSchema>

const son = (v: string) => (v.trim() === "" ? null : v.trim().replace(",", "."))

export function CatalogEdit({
  item,
  onClose,
}: {
  item: CatalogItemRead | null
  onClose: () => void
}) {
  const queryClient = useQueryClient()
  const cb = crudCallbacks(queryClient, ["catalog"], "Ombor yozuvi yangilandi")

  const form = useForm<FormValues>({
    resolver: zodResolver(formSchema),
    mode: "onBlur",
    // `key` bilan qayta yaratiladi (pastda) — shuning uchun defaultValues yetadi
    defaultValues: {
      quantity: item ? String(Number(item.quantity)) : "0",
      min_quantity: item?.min_quantity ? String(Number(item.min_quantity)) : "",
      location: item?.location ?? "",
      purchase_price: item?.purchase_price
        ? String(Math.round(Number(item.purchase_price)))
        : "",
      sale_price: item?.sale_price
        ? String(Math.round(Number(item.sale_price)))
        : "",
    },
  })

  const mutation = useMutation({
    mutationFn: (data: FormValues) =>
      CatalogService.updateCatalogItem({
        path: { item_id: item?.id ?? 0 },
        body: {
          quantity: son(data.quantity),
          min_quantity: son(data.min_quantity),
          location: data.location.trim() || null,
          purchase_price: son(data.purchase_price),
          sale_price: son(data.sale_price),
        },
      }),
    ...cb,
    onSuccess: () => {
      cb.onSuccess()
      onClose()
    },
  })

  if (!item) return null

  return (
    <Dialog open onOpenChange={(v) => !v && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Ombor yozuvi</DialogTitle>
          {/* Kod dialogda ko'rinib tursin: omborchi javonda aynan shuni izlaydi */}
          <DialogDescription>
            <span className="num font-semibold text-foreground">
              {item.code}
            </span>{" "}
            — {item.name}
          </DialogDescription>
        </DialogHeader>
        <Form {...form}>
          <form
            onSubmit={form.handleSubmit((d) => mutation.mutate(d))}
            className="space-y-4"
          >
            <div className="grid grid-cols-2 gap-4">
              <FormField
                control={form.control}
                name="quantity"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>
                      Qoldiq{item.unit ? `, ${item.unit}` : ""}
                    </FormLabel>
                    <FormControl>
                      <Input inputMode="decimal" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="min_quantity"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Eng kam qoldiq</FormLabel>
                    <FormControl>
                      <Input inputMode="decimal" placeholder="—" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="location"
                render={({ field }) => (
                  <FormItem className="col-span-2">
                    <FormLabel>Joylashuv</FormLabel>
                    <FormControl>
                      <Input placeholder="Masalan: A-3 javon" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="purchase_price"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Xarid, so'm</FormLabel>
                    <FormControl>
                      <Input inputMode="numeric" placeholder="—" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="sale_price"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Sotuv, so'm</FormLabel>
                    <FormControl>
                      <Input inputMode="numeric" placeholder="—" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>
            <DialogFooter>
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
