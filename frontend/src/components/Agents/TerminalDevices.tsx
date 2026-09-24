// Chek qurilmalari — /agents sahifasining ikkinchi bo'limi.
//
// Terminal hisobi odamga bog'langan: arrachi telefondan o'z hisobiga kirsa ham
// chek postdagi printerdan chiqardi (2026-09-24 da ikki bir xil chek ikki
// detalga yopishtirilgan). Ish markaziga qurilma ULANSA, chek faqat o'sha
// monoblokning brauzeridan chiqadi (backend `services/terminal_device.py`).

import { zodResolver } from "@hookform/resolvers/zod"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { KeyRound, Plus, Trash2 } from "lucide-react"
import { useState } from "react"
import { useForm } from "react-hook-form"
import { z } from "zod"

import { type TerminalDeviceRead, TerminalDevicesService } from "@/client"
import { ConfirmDialog } from "@/components/Common/ConfirmDialog"
import { EmptyRow } from "@/components/Common/EmptyRow"
import { CodeTtl, fmtCode } from "@/components/Common/PairCode"
import { QueryError } from "@/components/Common/QueryError"
import { RowAction } from "@/components/Common/RowAction"
import { SectionTitle } from "@/components/Common/SectionTitle"
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
  FormDescription,
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
import { useMesWs } from "@/hooks/useMesWs"
import { formatAgo, formatDateTime } from "@/lib/mes"
import { cn } from "@/lib/utils"
import { crudCallbacks, getMachinesQueryOptions } from "@/queries/mes"
import { handleError } from "@/utils"

const DEVICES_KEY = ["terminal-devices"]

/** Kod qaysi brauzerda kiritilgan — User-Agent dan qo'pol tur. Maqsad bitta:
 *  admin telefon ulab olinganini darhol ko'rsin (kodni ishchi ko'rib, o'z
 *  telefonida kiritgan bo'lsa). Aniq model kerak emas. */
function deviceKind(ua?: string | null): { label: string; phone: boolean } {
  if (!ua) return { label: "noma'lum qurilma", phone: false }
  if (/iPhone|iPad|Android|Mobile/i.test(ua))
    return { label: "TELEFON", phone: true }
  if (/Windows/i.test(ua)) return { label: "Windows kompyuter", phone: false }
  if (/Linux|X11/i.test(ua)) return { label: "Linux kompyuter", phone: false }
  if (/Macintosh/i.test(ua)) return { label: "Mac kompyuter", phone: false }
  return { label: "kompyuter", phone: false }
}

export function TerminalDevicesSection() {
  const queryClient = useQueryClient()
  const {
    data: devices,
    isLoading,
    isError,
    refetch,
  } = useQuery({
    queryKey: DEVICES_KEY,
    queryFn: async () =>
      (await TerminalDevicesService.readTerminalDevices()).data,
    // WS asosiy signal (kod kiritilishi bilan «Ulangan»); polling — zaxira
    refetchInterval: 30_000,
  })
  useMesWs((event) => {
    if (event.type.startsWith("terminal_device.")) {
      queryClient.invalidateQueries({ queryKey: DEVICES_KEY })
    }
  })

  return (
    <section className="mt-10">
      <div className="mb-2 flex flex-wrap items-end justify-between gap-3">
        <div>
          <SectionTitle>Chek qurilmalari (post monobloklari)</SectionTitle>
          <p className="max-w-3xl text-sm text-muted-foreground">
            Ish markaziga monoblok ulansa, chek FAQAT shu monoblokdan chiqadi —
            telefondan yoki boshqa kompyuterdan chek chiqarish to'siladi (skan
            va xarita ishlayveradi). Qurilma ulanmagan ish markazida cheklov
            yo'q.
          </p>
        </div>
        <AddDevice />
      </div>

      <div className="mb-4 rounded-xl border bg-card p-4 text-sm">
        <p className="mb-1 font-medium">Ulash — postning o'zida</p>
        <ol className="list-decimal space-y-0.5 pl-5 text-muted-foreground">
          <li>"Yangi qurilma" — ish markazini tanlab kod oling</li>
          <li>
            Postning monoblokida terminal ochiq bo'lsin — sarlavhada «Qurilmani
            ulash» tugmasi chiqadi, kodni shu yerga kiriting
          </li>
          <li>
            Kod kiritilishi bilan cheklov yoqiladi: shu ish markazining cheki
            endi faqat o'sha monoblokdan chiqadi
          </li>
        </ol>
      </div>

      {isLoading ? (
        <Skeleton className="h-32 w-full" />
      ) : isError ? (
        <QueryError onRetry={() => refetch()} />
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Nomi</TableHead>
              <TableHead>Ish markazi</TableHead>
              <TableHead>Holat</TableHead>
              <TableHead>Oxirgi faollik</TableHead>
              <TableHead className="w-20" />
            </TableRow>
          </TableHeader>
          <TableBody>
            {devices?.length ? (
              devices.map((d) => (
                <DeviceRow
                  key={d.id}
                  device={d}
                  // Cheklov ish markazida ULANGAN qurilma borligiga bog'liq —
                  // tasdiq matni shu qurilma ketgach nima bo'lishini aniq aytsin
                  othersPaired={devices.some(
                    (o) =>
                      o.id !== d.id &&
                      o.machine_id === d.machine_id &&
                      o.paired,
                  )}
                />
              ))
            ) : (
              <EmptyRow colSpan={5}>
                Qurilma yo'q — chek hozir har qurilmadan chiqadi.
              </EmptyRow>
            )}
          </TableBody>
        </Table>
      )}
    </section>
  )
}

/** Qurilma ketgach (o'chirilsa / yangi kod) ish markazida nima bo'ladi.
 *  Cheklov faqat ULANGAN qurilmalar bilan yashaydi (backend `print_device`). */
function afterText(
  device: TerminalDeviceRead,
  machine: string,
  othersPaired: boolean,
): string {
  if (!device.paired)
    return othersPaired
      ? `Bu qurilma hali ulanmagan — cheklov o'zgarmaydi: ${machine} cheki qolgan ulangan qurilmadan chiqadi.`
      : `Bu qurilma hali ulanmagan — cheklov o'zgarmaydi: ${machine} cheki hozir ham har qurilmadan chiqadi.`
  return othersPaired
    ? `Bu brauzerdan chek chiqmay qoladi. ${machine} cheki qolgan ulangan qurilmadan chiqaveradi.`
    : `${machine} ishida boshqa ulangan qurilma YO'Q — cheklov o'chadi: chek yana har qurilmadan (telefondan ham) chiqadi.`
}

function DeviceRow({
  device,
  othersPaired,
}: {
  device: TerminalDeviceRead
  othersPaired: boolean
}) {
  const queryClient = useQueryClient()
  const [confirm, setConfirm] = useState<"code" | "delete" | null>(null)
  const cb = (msg: string) => crudCallbacks(queryClient, DEVICES_KEY, msg)

  const regenCb = cb("Yangi ulanish kodi yaratildi")
  const regen = useMutation({
    mutationFn: () =>
      TerminalDevicesService.regenerateTerminalDeviceCode({
        path: { device_id: device.id },
      }),
    ...regenCb,
    onSuccess: () => {
      regenCb.onSuccess()
      setConfirm(null)
    },
  })
  const removeCb = cb("Qurilma o'chirildi")
  const remove = useMutation({
    mutationFn: () =>
      TerminalDevicesService.deleteTerminalDevice({
        path: { device_id: device.id },
      }),
    ...removeCb,
    onSuccess: () => {
      removeCb.onSuccess()
      setConfirm(null)
    },
  })

  const machine = device.machine_name ?? `#${device.machine_id}`
  return (
    <TableRow>
      <TableCell className="font-medium">{device.name}</TableCell>
      <TableCell>{machine}</TableCell>
      <TableCell>
        {device.paired ? (
          <Badge>Ulangan</Badge>
        ) : device.pair_code ? (
          <Badge variant="outline">Kod kutilmoqda</Badge>
        ) : (
          <Badge variant="outline">Kod muddati o'tgan</Badge>
        )}
        {device.pair_code && (
          <div className="mt-1.5">
            <code className="rounded-sm bg-muted px-2 py-1 font-semibold tracking-wider">
              {fmtCode(device.pair_code)}
            </code>
            {device.pair_expires_at && (
              <CodeTtl expiresAt={device.pair_expires_at} />
            )}
          </div>
        )}
        {device.paired && <PairedOn device={device} />}
        {!device.paired && !device.pair_code && (
          <div className="mt-1 text-xs text-muted-foreground">
            «Yangi ulanish kodi» tugmasi bilan qayta bering
          </div>
        )}
      </TableCell>
      <TableCell className="text-muted-foreground">
        {device.last_seen_at ? (
          <>
            <div className="num">{formatDateTime(device.last_seen_at)}</div>
            <div className="text-xs">{formatAgo(device.last_seen_at)}</div>
          </>
        ) : (
          "Hali ulanmagan"
        )}
      </TableCell>
      <TableCell>
        <div className="flex gap-1">
          <RowAction
            icon={KeyRound}
            title="Yangi ulanish kodi (eski ulanish bekor bo'ladi)"
            onClick={() => setConfirm("code")}
          />
          <RowAction
            icon={Trash2}
            title="Qurilmani o'chirish"
            danger
            onClick={() => setConfirm("delete")}
          />
        </div>
        <ConfirmDialog
          open={confirm === "code"}
          onOpenChange={(v) => !v && setConfirm(null)}
          title={`${device.name} uchun yangi kod?`}
          description={`Eski kod va ulanish darhol bekor bo'ladi. ${afterText(device, machine, othersPaired)}${device.paired ? " Yangi kod monoblokda kiritilgach cheklov qaytadi." : ""}`}
          confirmText="Yangi kod"
          loading={regen.isPending}
          onConfirm={() => regen.mutate()}
        />
        <ConfirmDialog
          open={confirm === "delete"}
          onOpenChange={(v) => !v && setConfirm(null)}
          title={`${device.name} o'chirilsinmi?`}
          description={afterText(device, machine, othersPaired)}
          confirmText="O'chirish"
          cancelText="Yopish"
          destructive
          loading={remove.isPending}
          onConfirm={() => remove.mutate()}
        />
      </TableCell>
    </TableRow>
  )
}

function PairedOn({ device }: { device: TerminalDeviceRead }) {
  const kind = deviceKind(device.paired_user_agent)
  return (
    <div
      className={cn(
        "mt-1 text-xs",
        kind.phone ? "font-semibold text-destructive" : "text-muted-foreground",
      )}
      title={device.paired_user_agent ?? undefined}
    >
      {kind.label}
      {device.paired_at && ` · ${formatDateTime(device.paired_at)}`}
      {kind.phone && " — telefon ulangan! Yangi kod berib, monoblokda ulang"}
    </div>
  )
}

const formSchema = z.object({
  name: z
    .string()
    .trim()
    .min(2, { message: "Nom kamida 2 ta belgidan iborat bo'lsin" })
    .max(100, { message: "Nom ko'pi bilan 100 ta belgi" }),
  // MAJBURIY: qurilma aynan shu ish markazining chekini chiqaradi
  machine_id: z.string().min(1, { message: "Ish markazini tanlang" }),
})

function AddDevice() {
  const [open, setOpen] = useState(false)
  const [created, setCreated] = useState<TerminalDeviceRead | null>(null)
  const queryClient = useQueryClient()
  const { data: machines } = useQuery(getMachinesQueryOptions())

  const form = useForm<z.infer<typeof formSchema>>({
    resolver: zodResolver(formSchema),
    defaultValues: { name: "", machine_id: "" },
  })

  const mutation = useMutation({
    mutationFn: async (data: z.infer<typeof formSchema>) =>
      (
        await TerminalDevicesService.createTerminalDevice({
          body: { name: data.name, machine_id: Number(data.machine_id) },
        })
      ).data,
    onSuccess: (device) => {
      setCreated(device)
      form.reset()
    },
    onError: handleError,
    onSettled: () => queryClient.invalidateQueries({ queryKey: DEVICES_KEY }),
  })

  const close = (v: boolean) => {
    setOpen(v)
    if (!v) setCreated(null)
  }

  return (
    <Dialog open={open} onOpenChange={close}>
      <DialogTrigger asChild>
        <Button variant="outline">
          <Plus /> Yangi qurilma
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-md">
        {created?.pair_code ? (
          <>
            <DialogHeader>
              <DialogTitle>Ulanish kodi — {created.name}</DialogTitle>
              <DialogDescription>
                {created.machine_name} monoblokida terminal sarlavhasidagi
                «Qurilmani ulash» tugmasini bosib shu kodni kiriting. Kod 15
                daqiqa amal qiladi va bir marta ishlaydi.
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
              <DialogTitle>Yangi chek qurilmasi</DialogTitle>
              <DialogDescription>
                Nom va ish markazini tanlang — shundan keyin ulanish kodi
                beriladi.
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
                          placeholder="Arra monobloki"
                          autoFocus
                        />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="machine_id"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Ish markazi</FormLabel>
                      <FormDescription>
                        Qurilma ulangach shu ish markazining cheki faqat undan
                        chiqadi.
                      </FormDescription>
                      <Select
                        value={field.value}
                        onValueChange={field.onChange}
                      >
                        <FormControl>
                          <SelectTrigger className="w-full">
                            <SelectValue placeholder="Tanlang" />
                          </SelectTrigger>
                        </FormControl>
                        <SelectContent>
                          {machines?.map((m) => (
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
