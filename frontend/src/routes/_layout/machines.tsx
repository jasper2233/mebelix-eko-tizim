import { zodResolver } from "@hookform/resolvers/zod"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { Plus } from "lucide-react"
import { useState } from "react"
import { useForm } from "react-hook-form"
import { z } from "zod"

import { MachinesService } from "@/client"
import { PageHeader } from "@/components/Common/PageHeader"
import { Badge } from "@/components/ui/badge"
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
import { Input } from "@/components/ui/input"
import { LoadingButton } from "@/components/ui/loading-button"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import useCurrentUser from "@/hooks/useCurrentUser"
import useCustomToast from "@/hooks/useCustomToast"
import { MACHINE_STATUS_LABELS, POST_COLORS } from "@/lib/mes"
import { getMachinesQueryOptions, getPostsQueryOptions } from "@/queries/mes"
import { handleError } from "@/utils"

export const Route = createFileRoute("/_layout/machines")({
  component: MachinesPage,
  head: () => ({ meta: [{ title: "Stanoklar | MebeliX" }] }),
})

const CAPACITY_UNITS: Record<string, string> = {
  m2_per_hour: "m²/soat",
  meter_per_hour: "metr/soat",
  units_per_hour: "dona/soat",
}

function MachinesPage() {
  const { data: machines, isLoading } = useQuery(getMachinesQueryOptions())
  const { data: posts } = useQuery(getPostsQueryOptions())
  const { currentUser } = useCurrentUser()
  const isAdmin = currentUser?.is_superuser || currentUser?.role === "admin"
  const postById = new Map((posts ?? []).map((p) => [p.id, p]))

  return (
    <div>
      <PageHeader
        title="Stanoklar"
        description="Postlar zanjiri bo'yicha jihozlar"
        actions={isAdmin ? <AddMachine /> : undefined}
      />
      {isLoading ? (
        <Skeleton className="h-64 w-full" />
      ) : (
        <div className="overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Stanok</TableHead>
                <TableHead>Post</TableHead>
                <TableHead>IP manzil</TableHead>
                <TableHead>Quvvat</TableHead>
                <TableHead>Holat</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {machines?.length ? (
                machines.map((m) => {
                  const post = postById.get(m.post_id)
                  return (
                    <TableRow key={m.id}>
                      <TableCell className="font-medium">{m.name}</TableCell>
                      <TableCell>
                        {post && (
                          <span
                            className="rounded px-2 py-0.5 text-xs font-bold"
                            style={{
                              color: POST_COLORS[post.code],
                              backgroundColor: `color-mix(in srgb, ${POST_COLORS[post.code]} 12%, white)`,
                            }}
                          >
                            {post.code}
                          </span>
                        )}
                      </TableCell>
                      <TableCell className="num">
                        {m.ip_address ?? "—"}
                      </TableCell>
                      <TableCell className="num">
                        {m.capacity
                          ? `${m.capacity} ${CAPACITY_UNITS[m.capacity_unit ?? ""] ?? ""}`
                          : "—"}
                      </TableCell>
                      <TableCell>
                        <Badge
                          variant={
                            m.status === "active" ? "default" : "secondary"
                          }
                        >
                          {MACHINE_STATUS_LABELS[m.status]}
                        </Badge>
                      </TableCell>
                    </TableRow>
                  )
                })
              ) : (
                <TableRow>
                  <TableCell
                    colSpan={5}
                    className="h-24 text-center text-muted-foreground"
                  >
                    Stanoklar yo'q.
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  )
}

const formSchema = z.object({
  name: z.string().trim().min(2).max(100),
  post_id: z.string().min(1, "Postni tanlang"),
  ip_address: z.string().max(45).optional(),
  capacity: z.string().optional(),
  capacity_unit: z
    .enum(["m2_per_hour", "meter_per_hour", "units_per_hour"])
    .optional(),
})

function AddMachine() {
  const [open, setOpen] = useState(false)
  const { data: posts } = useQuery(getPostsQueryOptions())
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()

  const form = useForm<z.infer<typeof formSchema>>({
    resolver: zodResolver(formSchema),
    defaultValues: { name: "", post_id: "", ip_address: "", capacity: "" },
  })

  const mutation = useMutation({
    mutationFn: (data: z.infer<typeof formSchema>) =>
      MachinesService.createMachine({
        requestBody: {
          name: data.name,
          post_id: Number(data.post_id),
          ip_address: data.ip_address || null,
          capacity: data.capacity ? Number(data.capacity) : null,
          capacity_unit: data.capacity_unit ?? null,
        },
      }),
    onSuccess: () => {
      showSuccessToast("Stanok qo'shildi")
      form.reset()
      setOpen(false)
    },
    onError: handleError(showErrorToast),
    onSettled: () => queryClient.invalidateQueries({ queryKey: ["machines"] }),
  })

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button>
          <Plus /> Stanok qo'shish
        </Button>
      </DialogTrigger>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Yangi stanok</DialogTitle>
        </DialogHeader>
        <Form {...form}>
          <form
            onSubmit={form.handleSubmit((d) => mutation.mutate(d))}
            className="space-y-3"
          >
            <FormField
              control={form.control}
              name="name"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Nomi</FormLabel>
                  <FormControl>
                    <Input {...field} placeholder="01 ARRA STANOGI" autoFocus />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="post_id"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Post</FormLabel>
                  <Select value={field.value} onValueChange={field.onChange}>
                    <FormControl>
                      <SelectTrigger className="w-full">
                        <SelectValue placeholder="Postni tanlang" />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      {(posts ?? []).map((p) => (
                        <SelectItem key={p.id} value={String(p.id)}>
                          {p.code} — {p.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <FormMessage />
                </FormItem>
              )}
            />
            <div className="grid grid-cols-3 gap-3">
              <FormField
                control={form.control}
                name="ip_address"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>IP</FormLabel>
                    <FormControl>
                      <Input {...field} placeholder="192.168.1.80" />
                    </FormControl>
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="capacity"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Quvvat</FormLabel>
                    <FormControl>
                      <Input type="number" min="0" {...field} />
                    </FormControl>
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="capacity_unit"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Birlik</FormLabel>
                    <Select
                      value={field.value ?? ""}
                      onValueChange={field.onChange}
                    >
                      <FormControl>
                        <SelectTrigger className="w-full">
                          <SelectValue placeholder="—" />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        {Object.entries(CAPACITY_UNITS).map(([v, l]) => (
                          <SelectItem key={v} value={v}>
                            {l}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </FormItem>
                )}
              />
            </div>
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
