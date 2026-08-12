import { useQuery } from "@tanstack/react-query"
import type { UseFormReturn } from "react-hook-form"
import { z } from "zod"

import type { UserRole } from "@/client"
import { Checkbox } from "@/components/ui/checkbox"
import {
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form"
import { Input } from "@/components/ui/input"
import { PasswordInput } from "@/components/ui/password-input"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { MACHINE_BOUND_ROLES, ROLE_LABELS } from "@/lib/mes"
import {
  optionalNameSchema,
  optionalPasswordSchema,
  passwordSchema,
  phoneSchema,
} from "@/lib/validation"
import { getMachinesQueryOptions } from "@/queries/mes"

/** Rol stanokka bog'langanmi — terminal/TABLO uchun stanok tanlash majburiy. */
export const isMachineBoundRole = (role: UserRole) =>
  (MACHINE_BOUND_ROLES as readonly UserRole[]).includes(role)

export type UserFormData = {
  phone: string
  name?: string
  password?: string
  confirm_password?: string
  role: UserRole
  machine_id?: string
  is_superuser: boolean
  is_active: boolean
}

/**
 * Add/Edit umumiy sxemasi. `requirePassword`: Add'da parol majburiy,
 * Edit'da bo'sh qoldirilsa parol o'zgartirilmaydi.
 */
export function buildUserFormSchema(
  requirePassword: boolean,
): z.ZodType<UserFormData, UserFormData> {
  return z
    .object({
      phone: phoneSchema,
      name: optionalNameSchema,
      password: requirePassword ? passwordSchema : optionalPasswordSchema,
      confirm_password: requirePassword
        ? z.string().min(1, { message: "Parolni tasdiqlang" })
        : z.string().optional(),
      role: z.enum(Object.keys(ROLE_LABELS) as [UserRole, ...UserRole[]]),
      machine_id: z.string().optional(),
      is_superuser: z.boolean(),
      is_active: z.boolean(),
    })
    .refine((d) => !isMachineBoundRole(d.role) || d.machine_id, {
      message: "Terminal/TABLO uchun stanok tanlang",
      path: ["machine_id"],
    })
    .refine(
      (d) =>
        (!requirePassword && !d.password) || d.password === d.confirm_password,
      { message: "Parollar mos emas", path: ["confirm_password"] },
    )
}

/** AddUser/EditUser dialoglari uchun umumiy 8 ta maydon (grid bilan birga). */
export function UserFormFields({
  form,
  passwordRequired,
}: {
  form: UseFormReturn<UserFormData>
  passwordRequired: boolean
}) {
  const { data: machines } = useQuery(getMachinesQueryOptions())

  return (
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
            <FormLabel>
              Parol o'rnatish
              {passwordRequired && (
                <>
                  {" "}
                  <span className="text-destructive">*</span>
                </>
              )}
            </FormLabel>
            <FormControl>
              <PasswordInput
                placeholder="Parol"
                {...field}
                required={passwordRequired}
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
            <FormLabel>
              Parolni tasdiqlash
              {passwordRequired && (
                <>
                  {" "}
                  <span className="text-destructive">*</span>
                </>
              )}
            </FormLabel>
            <FormControl>
              <PasswordInput
                placeholder="Parol"
                {...field}
                required={passwordRequired}
              />
            </FormControl>
            <FormMessage />
          </FormItem>
        )}
      />

      <FormField
        control={form.control}
        name="role"
        render={({ field }) => (
          <FormItem>
            <FormLabel>Rol</FormLabel>
            <Select value={field.value} onValueChange={field.onChange}>
              <FormControl>
                <SelectTrigger className="w-full">
                  <SelectValue />
                </SelectTrigger>
              </FormControl>
              <SelectContent>
                {Object.entries(ROLE_LABELS).map(([v, l]) => (
                  <SelectItem key={v} value={v}>
                    {l}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <FormMessage />
          </FormItem>
        )}
      />

      {isMachineBoundRole(form.watch("role")) && (
        <FormField
          control={form.control}
          name="machine_id"
          render={({ field }) => (
            <FormItem>
              <FormLabel>
                Stanok <span className="text-destructive">*</span>
              </FormLabel>
              <Select value={field.value ?? ""} onValueChange={field.onChange}>
                <FormControl>
                  <SelectTrigger className="w-full">
                    <SelectValue placeholder="Stanokni tanlang" />
                  </SelectTrigger>
                </FormControl>
                <SelectContent>
                  {(machines ?? []).map((m) => (
                    <SelectItem key={m.id} value={String(m.id)}>
                      {m.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <FormMessage />
            </FormItem>
          )}
        />
      )}

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
  )
}
