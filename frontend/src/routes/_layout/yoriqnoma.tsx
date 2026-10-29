// Yo'riqnoma (EKO TZ §11, 7-bosqich «xodimlarni o'qitish»): har rol uchun qisqa qo'llanma. Matn manbasi —
// `src/yoriqnoma/*.md` (frontend image faqat `frontend/` dan quriladi, shuning uchun `docs/` da emas; `docs/eko-tizim`
// shu fayllarga havola beradi). Ochilganda foydalanuvchining o'z roli birinchi.

import { createFileRoute, useNavigate } from "@tanstack/react-router"
import { Printer } from "lucide-react"
import { Fragment, type ReactNode } from "react"

import { Button } from "@/components/ui/button"
import { cardSurface } from "@/components/ui/card"
import { Table, TableBody, TableCell, TableRow } from "@/components/ui/table"
import { useCurrentUser } from "@/hooks/useCurrentUser"
import { cn } from "@/lib/utils"
import direktor from "@/yoriqnoma/direktor.md?raw"
import kassir from "@/yoriqnoma/kassir.md?raw"
import moliyachi from "@/yoriqnoma/moliyachi.md?raw"
import omborchi from "@/yoriqnoma/omborchi.md?raw"

const ROLLAR = [
  { v: "kassir", l: "Kassir", md: kassir },
  { v: "omborchi", l: "Omborchi", md: omborchi },
  { v: "moliyachi", l: "Moliyachi", md: moliyachi },
  { v: "direktor", l: "Direktor", md: direktor },
] as const
type Rol = (typeof ROLLAR)[number]["v"]

export const Route = createFileRoute("/_layout/yoriqnoma")({
  component: Yoriqnoma,
  validateSearch: (s: Record<string, unknown>): { rol?: Rol } => ({
    rol: ROLLAR.some((r) => r.v === s.rol) ? (s.rol as Rol) : undefined,
  }),
  head: () => ({ meta: [{ title: "Yo'riqnoma | MebeliX" }] }),
})

/** Foydalanuvchi roli → yo'riqnoma */
const ROLDAN: Record<string, Rol> = {
  kassir: "kassir",
  skladchi: "omborchi",
  moliyachi: "moliyachi",
}

function Yoriqnoma() {
  const { rol } = Route.useSearch()
  const { currentUser } = useCurrentUser()
  const navigate = useNavigate({ from: "/yoriqnoma" })
  const tanlangan = rol ?? ROLDAN[currentUser?.role ?? ""] ?? "direktor"
  const r = ROLLAR.find((x) => x.v === tanlangan) ?? ROLLAR[3]
  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-2 print:hidden">
        <h1 className="mr-4 text-xl font-bold">YO'RIQNOMA</h1>
        {ROLLAR.map((x) => (
          <button
            key={x.v}
            type="button"
            onClick={() => navigate({ search: { rol: x.v } })}
            className={cn(
              "rounded-full border px-3 py-1 text-sm",
              tanlangan === x.v &&
                "border-primary bg-primary text-primary-foreground",
            )}
          >
            {x.l}
          </button>
        ))}
        <Button
          variant="outline"
          size="sm"
          className="ml-auto"
          onClick={() => window.print()}
        >
          <Printer /> Chop etish
        </Button>
      </div>
      <article
        className={cn(
          cardSurface,
          "max-w-4xl p-6 leading-relaxed print:shadow-none",
        )}
      >
        <Markdown matn={r.md} />
      </article>
    </div>
  )
}

/** Satr ichidagi belgilash: **qalin** va `kod` */
function ichki(s: string): ReactNode {
  return s.split(/(\*\*[^*]+\*\*|`[^`]+`)/g).map((q, i) =>
    q.startsWith("**") ? (
      <b key={i}>{q.slice(2, -2)}</b>
    ) : q.startsWith("`") ? (
      <code key={i} className="rounded bg-muted px-1 font-mono text-[0.9em]">
        {q.slice(1, -1)}
      </code>
    ) : (
      <Fragment key={i}>{q}</Fragment>
    ),
  )
}

type Blok =
  | { t: "h"; d: number; s: string }
  | { t: "p"; s: string }
  | { t: "q"; s: string }
  | { t: "ul" | "ol"; items: { s: string; sub: string[] }[] }
  | { t: "table"; rows: string[][] }

/** Yo'riqnomalarda ishlatiladigan markdown qismi: sarlavha, paragraf, ro'yxat (bir pog'ona ichki), jadval, eslatma */
function bloklar(md: string): Blok[] {
  const out: Blok[] = []
  const satr = md.replace(/\r/g, "").split("\n")
  for (let i = 0; i < satr.length; i++) {
    const l = satr[i]
    if (!l.trim()) continue
    const h = /^(#{1,3}) (.*)$/.exec(l)
    if (h) {
      out.push({ t: "h", d: h[1].length, s: h[2] })
      continue
    }
    if (l.startsWith("|")) {
      const rows: string[][] = []
      while (i < satr.length && satr[i].startsWith("|")) {
        const cells = satr[i]
          .split("|")
          .slice(1, -1)
          .map((c) => c.trim())
        if (!cells.every((c) => /^-+$/.test(c))) rows.push(cells)
        i++
      }
      i--
      out.push({ t: "table", rows })
      continue
    }
    if (l.startsWith("> ")) {
      let s = l.slice(2)
      while (i + 1 < satr.length && satr[i + 1].startsWith("> "))
        s += ` ${satr[++i].slice(2)}`
      out.push({ t: "q", s })
      continue
    }
    const li = /^(- |\d+\. )(.*)$/.exec(l)
    if (li) {
      const t = li[1] === "- " ? "ul" : "ol"
      const items: { s: string; sub: string[] }[] = []
      while (i < satr.length) {
        const m = /^(- |\d+\. )(.*)$/.exec(satr[i])
        const sub = /^ {2,}- (.*)$/.exec(satr[i])
        const davom = /^ {2,}(\S.*)$/.exec(satr[i])
        if (m) items.push({ s: m[2], sub: [] })
        else if (sub && items.length) items[items.length - 1].sub.push(sub[1])
        else if (davom && items.length) {
          const it = items[items.length - 1]
          if (it.sub.length) it.sub[it.sub.length - 1] += ` ${davom[1]}`
          else it.s += ` ${davom[1]}`
        } else break
        i++
      }
      i--
      out.push({ t, items })
      continue
    }
    let s = l
    while (
      i + 1 < satr.length &&
      satr[i + 1].trim() &&
      !/^(#|\||> |- |\d+\. )/.test(satr[i + 1])
    )
      s += ` ${satr[++i]}`
    out.push({ t: "p", s })
  }
  return out
}

function Markdown({ matn }: { matn: string }) {
  return (
    <>
      {bloklar(matn).map((b, i) => {
        const key = `${b.t}-${i}`
        if (b.t === "h")
          return b.d === 1 ? (
            <h1 key={key} className="mb-3 text-2xl font-bold">
              {ichki(b.s)}
            </h1>
          ) : b.d === 2 ? (
            <h2
              key={key}
              className="mt-6 mb-2 border-b pb-1 text-lg font-semibold"
            >
              {ichki(b.s)}
            </h2>
          ) : (
            <h3 key={key} className="mt-4 mb-1 font-semibold">
              {ichki(b.s)}
            </h3>
          )
        if (b.t === "p")
          return (
            <p key={key} className="my-2">
              {ichki(b.s)}
            </p>
          )
        if (b.t === "q")
          return (
            <div
              key={key}
              className="my-3 rounded border-l-4 border-amber-400 bg-amber-50 px-3 py-2 text-sm text-amber-950"
            >
              {ichki(b.s)}
            </div>
          )
        if (b.t === "table")
          return (
            <div key={key} className="my-3 overflow-x-auto">
              <Table className="w-full border-collapse text-sm">
                <TableBody>
                  {b.rows.map((row, ri) => (
                    <TableRow
                      key={ri}
                      className={cn(ri === 0 && "bg-muted font-semibold")}
                    >
                      {row.map((c, ci) => (
                        <TableCell
                          key={ci}
                          className="border px-2 py-1 align-top"
                        >
                          {ichki(c)}
                        </TableCell>
                      ))}
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )
        const Teg = b.t === "ul" ? "ul" : "ol"
        return (
          <Teg
            key={key}
            className={cn(
              "my-2 space-y-1 pl-6",
              b.t === "ul" ? "list-disc" : "list-decimal",
            )}
          >
            {b.items.map((it, ii) => (
              <li key={ii}>
                {ichki(it.s)}
                {it.sub.length > 0 && (
                  <ul className="mt-1 list-disc space-y-1 pl-5">
                    {it.sub.map((s, si) => (
                      <li key={si}>{ichki(s)}</li>
                    ))}
                  </ul>
                )}
              </li>
            ))}
          </Teg>
        )
      })}
    </>
  )
}
