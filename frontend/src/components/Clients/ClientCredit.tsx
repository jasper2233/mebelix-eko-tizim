// Doimiy mijoz va kredit limiti (EKO TZ Q14, Q22). Hamma ko'radi, faqat direktor o'zgartiradi:
// doimiy mijoz to'lovsiz ishlab chiqarishga kiradi, lekin ochiq qarzi limitdan oshmasa.

import { useMutation, useQueryClient } from "@tanstack/react-query"
import { useState } from "react"

import { type ClientRead, ClientsService } from "@/client"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { Input } from "@/components/ui/input"
import { LoadingButton } from "@/components/ui/loading-button"
import { useCurrentUser } from "@/hooks/useCurrentUser"
import { formatMoney } from "@/lib/mes"
import { parseNum } from "@/lib/warehouse"
import { crudCallbacks } from "@/queries/mes"

export function ClientCredit({ client }: { client: ClientRead }) {
  const { currentUser } = useCurrentUser()
  const isDirector = Boolean(
    currentUser?.is_superuser ||
      currentUser?.role === "director" ||
      currentUser?.role === "admin",
  )
  const queryClient = useQueryClient()
  const [edit, setEdit] = useState(false)
  const [doimiy, setDoimiy] = useState(Boolean(client.doimiy))
  const [limit, setLimit] = useState(
    client.kredit_limit != null ? String(Number(client.kredit_limit)) : "",
  )
  const cb = crudCallbacks(
    queryClient,
    ["clients"],
    "Kredit sozlamasi saqlandi",
  )
  const save = useMutation({
    mutationFn: () =>
      ClientsService.updateClientCredit({
        path: { client_id: client.id },
        body: {
          doimiy,
          kredit_limit: limit.trim() ? String(parseNum(limit)) : null,
        },
      }),
    ...cb,
    onSuccess: () => {
      cb.onSuccess()
      setEdit(false)
    },
  })
  const limitOk = !limit.trim() || (parseNum(limit) ?? -1) >= 0

  if (!edit) {
    return (
      <div className="flex flex-wrap items-center gap-x-6 gap-y-1 rounded-lg border border-border p-3 text-sm">
        <span>
          Doimiy mijoz: <b>{client.doimiy ? "ha" : "yo'q"}</b>
        </span>
        <span>
          Kredit limiti:{" "}
          <b className="num">
            {client.kredit_limit != null
              ? formatMoney(client.kredit_limit)
              : "—"}
          </b>
        </span>
        {isDirector && (
          <Button
            size="sm"
            variant="outline"
            className="ml-auto"
            onClick={() => setEdit(true)}
          >
            O'zgartirish
          </Button>
        )}
      </div>
    )
  }
  return (
    <div className="flex flex-wrap items-center gap-4 rounded-lg border border-primary p-3 text-sm">
      <label htmlFor="kredit-doimiy" className="flex items-center gap-2">
        <Checkbox
          id="kredit-doimiy"
          checked={doimiy}
          onCheckedChange={(v) => setDoimiy(v === true)}
        />
        Doimiy mijoz
      </label>
      <label htmlFor="kredit-limit" className="flex items-center gap-2">
        Kredit limiti, so'm
        <Input
          id="kredit-limit"
          className="num w-40 text-right"
          placeholder="limit yo'q"
          value={limit}
          onChange={(e) => setLimit(e.target.value)}
        />
      </label>
      <div className="ml-auto flex gap-2">
        <Button size="sm" variant="outline" onClick={() => setEdit(false)}>
          Bekor
        </Button>
        <LoadingButton
          size="sm"
          loading={save.isPending}
          disabled={!limitOk}
          onClick={() => save.mutate()}
        >
          Saqlash
        </LoadingButton>
      </div>
    </div>
  )
}
