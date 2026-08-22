import { zodResolver } from "@hookform/resolvers/zod"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { FileText, KeyRound, Plus, Trash2 } from "lucide-react"
import { useCallback, useEffect, useState } from "react"
import { useForm } from "react-hook-form"
import { z } from "zod"

import { type BridgeAgentRead, BridgeAgentsService } from "@/client"
import { ConfirmDialog } from "@/components/Common/ConfirmDialog"
import { EmptyRow } from "@/components/Common/EmptyRow"
import { PageHeader } from "@/components/Common/PageHeader"
import { QueryError } from "@/components/Common/QueryError"
import { RowAction } from "@/components/Common/RowAction"
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Skeleton } from "@/components/ui/skeleton"
import { Switch } from "@/components/ui/switch"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { useMesWs } from "@/hooks/useMesWs"
import { requireAccess } from "@/lib/guards"
import { formatDateTime, isAdmin } from "@/lib/mes"
import { cn } from "@/lib/utils"
import {
  crudCallbacks,
  getBridgeAgentsQueryOptions,
  getMachinesQueryOptions,
} from "@/queries/mes"
import { handleError } from "@/utils"

export const Route = createFileRoute("/_layout/printers")({
  component: PrintersPage,
  // Backend ham AdminUser talab qiladi — guardsiz admin bo'lmagan odam bo'sh
  // jadval ko'rib, 403 qaytaradigan endpointni har 10 soniyada so'rab turardi.
  beforeLoad: requireAccess(isAdmin),
  head: () => ({ meta: [{ title: "Printer agentlar | MebeliX" }] }),
})

// Server last_seen_at ni har 5 daqiqada yangilaydi — 6 daqiqadan yangi bo'lsa onlayn
const ONLINE_MS = 6 * 60 * 1000

/** AB12CD34 -> AB12-CD34: telefonda aytish oson */
const fmtCode = (c: string) => `${c.slice(0, 4)}-${c.slice(4)}`

/** Kodning qolgan muddati — backendda `PAIR_TTL` 15 daqiqa.
 *
 * Kodni ko'rsatib, muddatini yashirish odamni taxminga majbur qilardi: agent
 * o'rnatilayotgan kompyuterga borguncha 12 daqiqa qoldimi yoki 20 soniyami —
 * bilinmasdi. Muddati o'tgani esa faqat kod TERILGANDAN KEYIN ma'lum bo'lardi.
 *
 * Soat SHU komponent ichida: bo'lmasa har soniyada butun jadval qayta chizilardi.
 */
function CodeTtl({ expiresAt }: { expiresAt: string }) {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(id)
  }, [])
  const qoldi = Math.max(
    0,
    Math.round((new Date(expiresAt).getTime() - now) / 1000),
  )
  return (
    <span
      className={cn(
        "num mt-1 block text-xs tabular-nums",
        // Oxirgi 2 daqiqa — endi yangi kod olish tezroq
        qoldi <= 120
          ? "font-semibold text-destructive"
          : "text-muted-foreground",
      )}
    >
      {Math.floor(qoldi / 60)}:{String(qoldi % 60).padStart(2, "0")} qoldi
    </span>
  )
}

/** Agent loglari — tsexdagi kompyuterga bormasdan nosozlikni ko'rish.
 *
 * Agent har 30 soniyada o'z log satrlarini serverga yuboradi; server ularni
 * Redisda oxirgi 200 tasini saqlaydi. Ilgari admin operatordan tsexdagi
 * kompyuterda log faylini ochishni so'rashga majbur edi — masofadan kirish yo'q.
 */
function AgentLogs({ agent }: { agent: BridgeAgentRead }) {
  const [open, setOpen] = useState(false)
  const { data, isFetching } = useQuery({
    queryKey: ["bridge-agents", agent.id, "logs"],
    queryFn: async () =>
      (
        await BridgeAgentsService.readBridgeLogs({
          path: { agent_id: agent.id },
        })
      ).data,
    // Faqat oyna ochiq bo'lganda — yopiq turganda so'rov yubormaydi
    enabled: open,
    refetchInterval: open ? 10_000 : false,
  })
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <span>
          <RowAction
            icon={FileText}
            title="Loglar"
            onClick={() => setOpen(true)}
          />
        </span>
      </DialogTrigger>
      <DialogContent className="max-w-3xl">
        <DialogHeader>
          <DialogTitle>{agent.name} — loglar</DialogTitle>
          <DialogDescription>
            Agent yuborgan oxirgi satrlar, eng yangisi tepada. Har 30 soniyada
            yangilanadi.
          </DialogDescription>
        </DialogHeader>
        {!data?.length ? (
          <p className="py-8 text-center text-muted-foreground">
            {isFetching
              ? "Yuklanmoqda..."
              : "Hali log yo'q — agent ulangach 30 soniya ichida keladi."}
          </p>
        ) : (
          <pre className="max-h-[60vh] overflow-auto rounded-md bg-muted p-3 text-xs leading-relaxed">
            {data.join("\n")}
          </pre>
        )}
      </DialogContent>
    </Dialog>
  )
}

function PrintersPage() {
  const queryClient = useQueryClient()
  const {
    data: agents,
    isLoading,
    isError,
    refetch,
  } = useQuery({
    ...getBridgeAgentsQueryOptions(),
    // WS asosiy signal; 10s polling — zaxira (WS uzilib qolgan holat uchun)
    refetchInterval: 10_000,
  })
  // Jonli holat: agent kod terib ulanishi bilan (bridge.paired/connected)
  // sahifa DARHOL yangilanadi — pollingni kutmasdan
  useMesWs(
    useCallback(
      (event) => {
        if (event.type.startsWith("bridge.")) {
          queryClient.invalidateQueries({ queryKey: ["bridge-agents"] })
        }
      },
      [queryClient],
    ),
  )

  return (
    <div>
      <PageHeader
        title="Printer agentlar"
        description="Chek printerlari — ulanish kodi bilan o'rnatiladi, serverga kirish shart emas"
        actions={<AddAgent />}
      />

      <div className="mb-4 rounded-xl border bg-card p-4 text-sm">
        <p className="mb-1 font-medium">
          O'rnatish — printer ulangan kompyuterda
        </p>
        <ol className="list-decimal space-y-0.5 pl-5 text-muted-foreground">
          <li>
            GoDEX drayveri o'rnatilgan bo'lsin (printer USB ulangan holda)
          </li>
          <li>"Yangi agent" bilan kod oling</li>
          <li>
            mebelix-agent.exe ni ishga tushirib kodni kiriting. Shundan keyin
            agent fonda ishlaydi va kompyuter yonganda o'zi tushadi
          </li>
        </ol>
      </div>

      {isLoading ? (
        <Skeleton className="h-64 w-full" />
      ) : isError ? (
        <QueryError onRetry={() => refetch()} />
      ) : (
        <div className="overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Nomi</TableHead>
                <TableHead>Holat</TableHead>
                <TableHead>Ulanish kodi</TableHead>
                <TableHead>Ish markazi (skan-forvard)</TableHead>
                <TableHead>Chek chiqarish</TableHead>
                <TableHead>Oxirgi ulanish</TableHead>
                <TableHead className="w-24" />
              </TableRow>
            </TableHeader>
            <TableBody>
              {agents?.length ? (
                agents.map((a) => <AgentRow key={a.id} agent={a} />)
              ) : (
                <EmptyRow colSpan={7}>
                  Agentlar yo'q. "Yangi agent" bilan ulanish kodi yarating.
                </EmptyRow>
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
  const [confirm, setConfirm] = useState<"code" | "delete" | null>(null)
  // Ish markazi almashinuvi tasdiq bilan: noto'g'ri tanlov keyingi barcha skan-forvard
  // skanlarini BOSHQA post nomidan yozadi — jimgina o'tib ketmasin
  const [pendingMachine, setPendingMachine] = useState<number | null | "unset">(
    "unset",
  )
  // Chek chiqarish belgisi ham tasdiq bilan: printersiz kompyuterda yoqilsa
  // umumiy navbatdan chek "o'g'irlanadi", printerlida o'chirilsa chek to'xtaydi
  const [pendingPrint, setPendingPrint] = useState<boolean | null>(null)
  const { data: machines } = useQuery(getMachinesQueryOptions())
  const cb = (msg: string) => crudCallbacks(queryClient, ["bridge-agents"], msg)

  const printCb = cb("Saqlandi")
  const togglePrint = useMutation({
    mutationFn: (v: boolean) =>
      BridgeAgentsService.updateBridgeAgent({
        path: { agent_id: agent.id },
        body: { can_print: v },
      }),
    ...printCb,
    onSuccess: () => {
      printCb.onSuccess()
      setPendingPrint(null)
    },
  })

  const linkCb = cb("Ish markazi bog'landi")
  const linkMachine = useMutation({
    mutationFn: (machineId: number | null) =>
      BridgeAgentsService.updateBridgeAgent({
        path: { agent_id: agent.id },
        body: { machine_id: machineId },
      }),
    ...linkCb,
    onSuccess: () => {
      linkCb.onSuccess()
      setPendingMachine("unset")
    },
  })
  const pendingName =
    pendingMachine !== "unset" && pendingMachine !== null
      ? (machines?.find((m) => m.id === pendingMachine)?.name ?? "?")
      : null

  const regenCb = cb("Yangi ulanish kodi yaratildi")
  const regen = useMutation({
    mutationFn: () =>
      BridgeAgentsService.regenerateBridgeCode({
        path: { agent_id: agent.id },
      }),
    ...regenCb,
    onSuccess: () => {
      regenCb.onSuccess()
      setConfirm(null)
    },
  })
  const removeCb = cb("Agent bekor qilindi")
  const remove = useMutation({
    mutationFn: () =>
      BridgeAgentsService.deleteBridgeAgent({ path: { agent_id: agent.id } }),
    ...removeCb,
    onSuccess: () => {
      removeCb.onSuccess()
      setConfirm(null)
    },
  })

  const seen = agent.last_seen_at ? new Date(agent.last_seen_at) : null
  const online = seen && Date.now() - seen.getTime() < ONLINE_MS

  return (
    <TableRow>
      <TableCell className="font-medium">{agent.name}</TableCell>
      <TableCell>
        {online ? (
          <span className="inline-flex items-center gap-1.5">
            <Badge>Ulandi</Badge>
            {/* null = eski (versiyasiz) exe — yangilash kerakligi darhol ko'rinadi */}
            <span className="num text-xs text-muted-foreground">
              {agent.version ? `v${agent.version}` : "eski exe"}
            </span>
          </span>
        ) : agent.paired ? (
          <Badge variant="secondary">Uzilgan</Badge>
        ) : agent.pair_code ? (
          <Badge variant="outline">Kod kutilmoqda</Badge>
        ) : (
          <Badge variant="outline">Kod muddati o'tgan</Badge>
        )}
      </TableCell>
      <TableCell>
        {agent.pair_code ? (
          <>
            <code className="rounded-sm bg-muted px-2 py-1 font-semibold tracking-wider">
              {fmtCode(agent.pair_code)}
            </code>
            {agent.pair_expires_at && (
              <CodeTtl expiresAt={agent.pair_expires_at} />
            )}
          </>
        ) : (
          <span className="text-muted-foreground">—</span>
        )}
      </TableCell>
      <TableCell>
        {/* Skan-forvard: stanok skaneri o'qigan QR MES'ga shu stanok nomidan yoziladi */}
        <Select
          value={agent.machine_id ? String(agent.machine_id) : "none"}
          onValueChange={(v) => {
            const next = v === "none" ? null : Number(v)
            if (next !== (agent.machine_id ?? null)) setPendingMachine(next)
          }}
        >
          <SelectTrigger className="h-9 w-44">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="none">— bog'lanmagan</SelectItem>
            {machines?.map((m) => (
              <SelectItem key={m.id} value={String(m.id)}>
                {m.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <ConfirmDialog
          open={pendingMachine !== "unset"}
          onOpenChange={(v) => !v && setPendingMachine("unset")}
          title={
            pendingName
              ? `${pendingName} ish markaziga bog'lansinmi?`
              : "Ish markazi bog'lami olib tashlansinmi?"
          }
          description={
            pendingName
              ? `${agent.name} kompyuteridagi skaner o'qigan QR endi "${pendingName}" nomidan yoziladi. Noto'g'ri ish markazi tanlansa skanlar boshqa postga yozilib ketadi.`
              : `${agent.name} skan-forvardi o'chadi — skaner o'qigan QR MES'ga yozilmaydi (Nanxing'da ochilaveradi).`
          }
          confirmText={pendingName ? "Bog'lash" : "Olib tashlash"}
          loading={linkMachine.isPending}
          onConfirm={() => {
            if (pendingMachine !== "unset") linkMachine.mutate(pendingMachine)
          }}
        />
      </TableCell>
      <TableCell>
        <Switch
          checked={agent.can_print}
          onCheckedChange={(v) => setPendingPrint(v)}
          aria-label="Chek chiqarish"
        />
        <ConfirmDialog
          open={pendingPrint !== null}
          onOpenChange={(v) => !v && setPendingPrint(null)}
          title={
            pendingPrint
              ? "Chek chiqarish yoqilsinmi?"
              : "Chek chiqarish o'chirilsinmi?"
          }
          description={
            pendingPrint
              ? `${agent.name} chek navbatidan ish oladi. Bu kompyuterda GoDEX printer ulangan bo'lishi SHART — aks holda cheklar shu yerga tushib, printerli agentga yetib bormaydi.`
              : `${agent.name} chek navbatidan ish olmaydi — faqat skan-forvard va holat uchun ulanadi (printersiz stansiya uchun to'g'ri). Ulangan agentda ~5 daqiqada kuchga kiradi.`
          }
          confirmText={pendingPrint ? "Yoqish" : "O'chirish"}
          loading={togglePrint.isPending}
          onConfirm={() => {
            if (pendingPrint !== null) togglePrint.mutate(pendingPrint)
          }}
        />
      </TableCell>
      <TableCell className="text-muted-foreground">
        {seen ? formatDateTime(agent.last_seen_at) : "Hali ulanmagan"}
      </TableCell>
      <TableCell>
        <div className="flex gap-1">
          <AgentLogs agent={agent} />
          <RowAction
            icon={KeyRound}
            title="Yangi ulanish kodi (eski token bekor bo'ladi)"
            onClick={() => setConfirm("code")}
          />
          <RowAction
            icon={Trash2}
            title="Agentni bekor qilish"
            danger
            onClick={() => setConfirm("delete")}
          />
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

  const form = useForm<z.infer<typeof formSchema>>({
    resolver: zodResolver(formSchema),
    defaultValues: { name: "" },
  })

  const mutation = useMutation({
    mutationFn: async (data: z.infer<typeof formSchema>) =>
      (
        await BridgeAgentsService.createBridgeAgent({
          body: { name: data.name },
        })
      ).data,
    onSuccess: (agent) => {
      setCreated(agent)
      form.reset()
    },
    onError: handleError,
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
