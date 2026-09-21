// «Bu detal qayerda?» — ofis javobi. Reestr qidiruvi BUYURTMA qaytaradi,
// detal joylashuvini emas; shuning uchun o'sha maydonga Detal ID kiritilsa
// jadval o'rniga shu panel chiqadi (docs/06).

import { useQuery } from "@tanstack/react-query"
import { Link } from "@tanstack/react-router"

import type { InstanceTrace } from "@/client"
import { QueryError } from "@/components/Common/QueryError"
import { StagePipeline } from "@/components/Common/StagePipeline"
import { StatusBadge } from "@/components/Common/StatusBadge"
import { Skeleton } from "@/components/ui/skeleton"
import { formatAgo, ORDER_PREFIX } from "@/lib/mes"
import { getInstanceTraceQueryOptions } from "@/queries/mes"

/** SHAKL bo'yicha, «`_` bor» emas: prod loyiha nomlarining yarmida `_` bor.
 *  O'lchov va ikkinchi naqshning sababi — docs/06. */
const PREFIKSSIZ = /^\d{3,6}_\d{1,3}_/
export const looksLikePartId = (q: string) => {
  const t = q.trim()
  return ORDER_PREFIX.test(t) || PREFIKSSIZ.test(t)
}

/** Backend `trace.py: _LIMIT` bilan bir xil — ro'yxat kesilganini aytish uchun. */
const LIMIT = 50

export function PartTrace({ q }: { q: string }) {
  const { data, isLoading, isError, refetch } = useQuery(
    getInstanceTraceQueryOptions(q),
  )

  if (isLoading) return <Skeleton className="h-32 w-full" />
  if (isError) return <QueryError onRetry={() => refetch()} />
  if (!data?.length)
    return (
      <p className="rounded-xl border border-dashed p-8 text-center text-sm text-muted-foreground">
        «{q}» bo'yicha detal topilmadi. Detal ID chekda yozilgan — masalan
        <span className="num"> B-2026-001_121301_01_002</span>. Buyurtma
        qidirmoqchi bo'lsangiz raqam yoki loyiha nomini kiriting.
      </p>
    )

  return (
    <div className="space-y-3">
      {data.map((t) => (
        <TraceCard key={t.qr_text} t={t} />
      ))}
      {data.length >= LIMIT && (
        <p className="text-center text-xs text-muted-foreground">
          Faqat dastlabki {LIMIT} ta nusxa — Detal ID ni to'liqroq kiriting.
        </p>
      )}
    </div>
  )
}

function TraceCard({ t }: { t: InstanceTrace }) {
  const tugagan = t.next_post === null
  // Oxirgi skan va kutilayotgan qadam bir postda — detal shu yerda ish ostida.
  const ish_ostida = t.last_post !== null && t.last_post === t.next_post
  // Post KODI bo'yicha emas: bir post marshrutda ikki marta uchrashi mumkin va
  // kod bo'yicha izlansa BIRINCHI, allaqachon tugagani topilardi.
  const joriy = t.steps.find((s) => s.done < s.need)
  return (
    <Link
      to="/orders/$orderId"
      params={{ orderId: String(t.order_id) }}
      className="block rounded-xl border p-4 transition-colors hover:border-primary"
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="num font-semibold text-primary">{t.qr_text}</div>
          <div className="truncate text-xs text-muted-foreground">
            {t.part_name} · {t.order_number}
            {t.instance_no > 1 && ` · ${t.instance_no}-nusxa`}
          </div>
        </div>
        <StatusBadge status={t.order_status} />
      </div>

      <div className="mt-3">
        <StagePipeline
          showLabels
          stages={t.steps.map((s) => ({
            code: s.post_code,
            done: s.done,
            total: s.need,
          }))}
        />
      </div>

      <div className="mt-2 text-sm">
        {ish_ostida ? (
          <>
            <span className="font-semibold">{t.last_post}</span> da — ish ostida
            {joriy && (
              <span className="num">
                {" "}
                ({joriy.done}/{joriy.need})
              </span>
            )}
            <span className="text-muted-foreground">
              {t.last_at && ` · oxirgi skan ${formatAgo(t.last_at)}`}
            </span>
          </>
        ) : t.last_post ? (
          <>
            <span className="font-semibold">{t.last_post}</span> dan o'tgan
            <span className="text-muted-foreground">
              {t.last_at && ` · ${formatAgo(t.last_at)}`}
            </span>
            {!tugagan && (
              <>
                {" → "}
                <span className="font-semibold">{t.next_post}</span> navbatida
              </>
            )}
          </>
        ) : t.next_post ? (
          <>
            Hali skanlanmagan —{" "}
            <span className="font-semibold">{t.next_post}</span> dan boshlanadi
          </>
        ) : (
          <span className="text-muted-foreground">Marshrut belgilanmagan</span>
        )}
        {tugagan && t.steps.length > 0 && (
          <span className="ml-1 font-semibold text-emerald-700">
            · marshrut tugagan
          </span>
        )}
      </div>

      {t.defect_post && (
        <div className="mt-2 rounded-lg bg-destructive/10 px-3 py-1.5 text-sm font-semibold text-destructive">
          BRAK · {t.defect_post}
          {t.defect_reason && ` — ${t.defect_reason}`}
        </div>
      )}
    </Link>
  )
}
