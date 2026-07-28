import { zodResolver } from "@hookform/resolvers/zod"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { Download, KeyRound, Plus, Trash2 } from "lucide-react"
import { useState } from "react"
import { useForm } from "react-hook-form"
import { z } from "zod"

import { type BridgeAgentRead, BridgeAgentsService, OpenAPI } from "@/client"
import { ConfirmDialog } from "@/components/Common/ConfirmDialog"
import { PageHeader } from "@/components/Common/PageHeader"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
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
import { Skeleton } from "@/components/ui/skeleton"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import useCustomToast from "@/hooks/useCustomToast"
import { formatDateTime } from "@/lib/mes"
import { handleError } from "@/utils"

export const Route = createFileRoute("/_layout/printers")({
  component: PrintersPage,
  head: () => ({ meta: [{ title: "Printer agentlar | MebeliX" }] }),
})

// Server last_seen_at ni har 5 daqiqada yangilaydi — 6 daqiqadan yangi bo'lsa onlayn
const ONLINE_MS = 6 * 60 * 1000

/** AB12CD34 -> AB12-CD34: telefonda aytish oson */
const fmtCode = (c: string) => `${c.slice(0, 4)}-${c.slice(4)}`

function PrintersPage() {
  const { data: agents, isLoading } = useQuery({
    queryKey: ["bridge-agents"],
    queryFn: () => BridgeAgentsService.readBridgeAgents(),
    refetchInterval: 60_000,
  })

  return (
    <div>
      <PageHeader
        title="Printer agentlar"
        description="Chek printerlari — ulanish kodi bilan o'rnatiladi, serverga kirish shart emas"
        actions={
          <div className="flex gap-2">
            <Button asChild variant="outline">
              <a
                href={`${OpenAPI.BASE}/api/v1/bridge-agents/download`}
                download="mebelix-agent.exe"
              >
                <Download /> Agentni yuklab olish
              </a>
            </Button>
            <AddAgent />
          </div>
        }
      />

      <div className="mb-4 rounded-lg border bg-card p-4 text-sm">
        <p className="mb-1 font-medium">
          O'rnatish — printer ulangan kompyuterda
        </p>
        <ol className="list-decimal space-y-0.5 pl-5 text-muted-foreground">
          <li>
            GoDEX drayveri o'rnatilgan bo'lsin (printer USB ulangan holda)
          </li>
          <li>"Yangi agent" bilan kod oling</li>
          <li>
            "Agentni yuklab olish" → faylni oching → kodni kiriting. Shundan
            keyin agent fonda ishlaydi va kompyuter yonganda o'zi tushadi
          </li>
        </ol>
      </div>

      {isLoading ? (
        <Skeleton className="h-64 w-full" />
      ) : (
        <div className="overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Nomi</TableHead>
                <TableHead>Holat</TableHead>
                <TableHead>Ulanish kodi</TableHead>
                <TableHead>Oxirgi ulanish</TableHead>
                <TableHead className="w-24" />
              </TableRow>
            </TableHeader>
            <TableBody>
              {agents?.length ? (
                agents.map((a) => <AgentRow key={a.id} agent={a} />)
              ) : (
                <TableRow>
                  <TableCell
                    colSpan={5}
                    className="h-24 text-center text-muted-foreground"
                  >
                    Agentlar yo'q. "Yangi agent" bilan ulanish kodi yarating.
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

function AgentRow({ agent }: { agent: BridgeAgentRead }) {
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const [confirm, setConfirm] = useState<"code" | "delete" | null>(null)
  const refresh = () =>
    queryClient.invalidateQueries({ queryKey: ["bridge-agents"] })

  const regen = useMutation({
    mutationFn: () =>
      BridgeAgentsService.regenerateBridgeCode({ agentId: agent.id }),
    onSuccess: () => {
      showSuccessToast("Yangi ulanish kodi yaratildi")
      setConfirm(null)
    },
    onError: handleError(showErrorToast),
    onSettled: refresh,
  })
  const remove = useMutation({
    mutationFn: () =>
      BridgeAgentsService.deleteBridgeAgent({ agentId: agent.id }),
    onSuccess: () => {
      showSuccessToast("Agent bekor qilindi")
      setConfirm(null)
    },
    onError: handleError(showErrorToast),
    onSettled: refresh,
  })

  const seen = agent.last_seen_at ? new Date(agent.last_seen_at) : null
  const online = seen && Date.now() - seen.getTime() < ONLINE_MS

  return (
    <TableRow>
      <TableCell className="font-medium">{agent.name}</TableCell>
      <TableCell>
        {online ? (
          <Badge>Onlayn</Badge>
        ) : agent.paired ? (
          <Badge variant="secondary">Oflayn</Badge>
        ) : agent.pair_code ? (
          <Badge variant="outline">Kod kutilmoqda</Badge>
        ) : (
          <Badge variant="outline">Kod muddati o'tgan</Badge>
        )}
      </TableCell>
      <TableCell>
        {agent.pair_code ? (
          <code className="rounded-sm bg-muted px-2 py-1 font-semibold tracking-wider">
            {fmtCode(agent.pair_code)}
          </code>
        ) : (
          <span className="text-muted-foreground">—</span>
        )}
      </TableCell>
      <TableCell className="text-muted-foreground">
        {seen ? formatDateTime(agent.last_seen_at) : "Hali ulanmagan"}
      </TableCell>
      <TableCell>
        <div className="flex gap-1">
          <Button
            variant="ghost"
            size="icon"
            title="Yangi ulanish kodi (eski token bekor bo'ladi)"
            onClick={() => setConfirm("code")}
          >
            <KeyRound />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            className="text-destructive"
            title="Agentni bekor qilish"
            onClick={() => setConfirm("delete")}
          >
            <Trash2 />
          </Button>
        </div>
        <ConfirmDialog
          open={confirm === "code"}
          onOpenChange={(v) => !v && setConfirm(null)}
          title={`${agent.name} uchun yangi kod?`}
          description="Eski token bekor bo'ladi — o'sha kompyuter keyingi ulanishda rad etiladi va yangi kod bilan qayta ulanishi kerak."
          confirmText="Yangi kod"
          loading={regen.isPending}
          onConfirm={() => regen.mutate()}
        />
        <ConfirmDialog
          open={confirm === "delete"}
          onOpenChange={(v) => !v && setConfirm(null)}
          title={`${agent.name} bekor qilinsinmi?`}
          description="Agent boshqa ulana olmaydi va chek chiqara olmaydi."
          confirmText="Agentni bekor qilish"
          cancelText="Yopish"
          destructive
          loading={remove.isPending}
          onConfirm={() => remove.mutate()}
        />
      </TableCell>
    </TableRow>
  )
}

const formSchema = z.object({
  name: z.string().trim().min(2).max(100),
})

function AddAgent() {
  const [open, setOpen] = useState(false)
  const [created, setCreated] = useState<BridgeAgentRead | null>(null)
  const queryClient = useQueryClient()
  const { showErrorToast } = useCustomToast()

  const form = useForm<z.infer<typeof formSchema>>({
    resolver: zodResolver(formSchema),
    defaultValues: { name: "" },
  })

  const mutation = useMutation({
    mutationFn: (data: z.infer<typeof formSchema>) =>
      BridgeAgentsService.createBridgeAgent({
        requestBody: { name: data.name },
      }),
    onSuccess: (agent) => {
      setCreated(agent)
      form.reset()
    },
    onError: handleError(showErrorToast),
    onSettled: () =>
      queryClient.invalidateQueries({ queryKey: ["bridge-agents"] }),
  })

  const close = (v: boolean) => {
    setOpen(v)
    if (!v) setCreated(null)
  }

  return (
    <Dialog open={open} onOpenChange={close}>
      <DialogTrigger asChild>
        <Button>
          <Plus /> Yangi agent
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-md">
        {created?.pair_code ? (
          <>
            <DialogHeader>
              <DialogTitle>Ulanish kodi — {created.name}</DialogTitle>
              <DialogDescription>
                Printerli kompyuterda agentni ishga tushiring va shu kodni
                kiriting. Kod 15 daqiqa amal qiladi va bir marta ishlaydi;
                ulangandan keyin agent doimiy ishlaydi.
              </DialogDescription>
            </DialogHeader>
            <div className="rounded-lg bg-muted py-4 text-center font-bold text-3xl tracking-[0.3em]">
              {fmtCode(created.pair_code)}
            </div>
            <Button onClick={() => close(false)}>Yopish</Button>
          </>
        ) : (
          <>
            <DialogHeader>
              <DialogTitle>Yangi printer agenti</DialogTitle>
              <DialogDescription>
                Qaysi kompyuter/post ekanini bildiruvchi nom bering — ulanish
                kodi yaratiladi.
              </DialogDescription>
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
                        <Input
                          {...field}
                          placeholder="Arrachi monoblok"
                          autoFocus
                        />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <LoadingButton
                  type="submit"
                  className="w-full"
                  loading={mutation.isPending}
                >
                  Kod yaratish
                </LoadingButton>
              </form>
            </Form>
          </>
        )}
      </DialogContent>
    </Dialog>
  )
}
