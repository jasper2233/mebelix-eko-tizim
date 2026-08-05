import { zodResolver } from "@hookform/resolvers/zod"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { Plus } from "lucide-react"
import { useState } from "react"
import { useForm } from "react-hook-form"
import { z } from "zod"

import { MachinesService } from "@/client"
import { EmptyRow } from "@/components/Common/EmptyRow"
import { PageHeader } from "@/components/Common/PageHeader"
import { PostBadge } from "@/components/Common/PostBadge"
import { QueryError } from "@/components/Common/QueryError"
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
import { useCurrentUser } from "@/hooks/useCurrentUser"
import { requireAccess } from "@/lib/guards"
import { isAdmin, isProductionStaff, MACHINE_STATUS_LABELS } from "@/lib/mes"
import {
  crudCallbacks,
  getMachinesQueryOptions,
  getPostsQueryOptions,
} from "@/queries/mes"

export const Route = createFileRoute("/_layout/machines")({
  component: MachinesPage,
  // Sidebar ko'rinishi bilan bir xil rollar to'plami (lib/mes)
  beforeLoad: requireAccess(isProductionStaff),
  head: () => ({ meta: [{ title: "Stanoklar | MebeliX" }] }),
})

function MachinesPage() {
  const {
    data: machines,
    isLoading,
    isError,
    refetch,
  } = useQuery(getMachinesQueryOptions())
  const { data: posts } = useQuery(getPostsQueryOptions())
  const { currentUser } = useCurrentUser()
  const admin = isAdmin(currentUser)
  const postById = new Map((posts ?? []).map((p) => [p.id, p]))

  return (
    <div>
      <PageHeader
        title="Stanoklar"
        description="Postlar zanjiri bo'yicha jihozlar"
        actions={admin ? <AddMachine /> : undefined}
      />
      {isLoading ? (
        <Skeleton className="h-64 w-full" />
      ) : isError ? (
        <QueryError onRetry={() => refetch()} />
      ) : (
        <div className="overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Stanok</TableHead>
                <TableHead>Post</TableHead>
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
                        {post && <PostBadge code={post.code} />}
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
                <EmptyRow colSpan={3}>Stanoklar yo'q.</EmptyRow>
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
})

function AddMachine() {
  const [open, setOpen] = useState(false)
  const { data: posts } = useQuery(getPostsQueryOptions())
  const queryClient = useQueryClient()
  const cb = crudCallbacks(queryClient, ["machines"], "Stanok qo'shildi")

  const form = useForm<z.infer<typeof formSchema>>({
    resolver: zodResolver(formSchema),
    defaultValues: { name: "", post_id: "" },
  })

  const mutation = useMutation({
    mutationFn: (data: z.infer<typeof formSchema>) =>
      MachinesService.createMachine({
        requestBody: {
          name: data.name,
          post_id: Number(data.post_id),
        },
      }),
    ...cb,
    onSuccess: () => {
      cb.onSuccess()
      form.reset()
      setOpen(false)
    },
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
