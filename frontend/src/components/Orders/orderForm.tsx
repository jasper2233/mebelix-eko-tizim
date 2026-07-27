// Buyurtma formasi: sxema, payload va umumiy maydonlar — AddOrder/EditOrder
// bitta backend kontraktiga tegadi, shuning uchun bir manbadan.

import type { Control } from "react-hook-form"
import { z } from "zod"

import { DatePicker } from "@/components/ui/date-picker"
import {
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form"
import { Input } from "@/components/ui/input"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { PRIORITY_DOT_CLASSES, PRIORITY_LABELS } from "@/lib/mes"
import { formatMoneyInput } from "@/lib/validation"

const money = (v: string) => v.replace(/\s+/g, "")

export const formSchema = z
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

export type FormValues = z.infer<typeof formSchema>

// create va update bir xil payload kutadi
export const toRequestBody = (data: FormValues) => ({
  client_id: Number(data.client_id),
  deadline: data.deadline || null,
  priority: data.priority,
  amount: money(data.amount) || null,
  advance_payment: money(data.advance_payment ?? "") || null,
  notes: data.notes || null,
})

// Mijoz va izoh maydonlari dialoglarda qoladi — ular ikkalasida farq qiladi
export function OrderFields({ control }: { control: Control<FormValues> }) {
  return (
    <>
      <div className="grid grid-cols-2 gap-3">
        <FormField
          control={control}
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
          control={control}
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
                  {Object.entries(PRIORITY_LABELS).map(([value, label]) => (
                    <SelectItem key={value} value={value}>
                      <span
                        className={`size-2 shrink-0 rounded-full ${PRIORITY_DOT_CLASSES[value]}`}
                      />
                      {label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </FormItem>
          )}
        />
      </div>
      <div className="grid grid-cols-2 gap-3">
        <FormField
          control={control}
          name="amount"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Umumiy narx (so'm)</FormLabel>
              <FormControl>
                <Input
                  {...field}
                  inputMode="numeric"
                  className="num"
                  placeholder="5 000 000"
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
          control={control}
          name="advance_payment"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Boshlang'ich to'lov (so'm)</FormLabel>
              <FormControl>
                <Input
                  {...field}
                  inputMode="numeric"
                  className="num"
                  placeholder="2 000 000"
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
    </>
  )
}
