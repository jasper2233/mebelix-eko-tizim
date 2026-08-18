import { Button } from "@/components/ui/button"

/**
 * Jadval sahifalagichi — reyestrlarda BITTA ko'rinish.
 *
 * Ilgari har reyestr o'zinikini yozardi va ikkitasi ikki xil chiqardi:
 * biri `[1 / 3][Oldingi][Keyingi]`, ikkinchisi `[N tadan X–Y][Oldingi][1 / 7]
 * [Keyingi]` — ya'ni sahifa raqami birida tugmalardan oldin, boshqasida
 * orasida turardi. Bu yerda tartib bitta: chapda oraliq, o'ngda boshqaruv.
 *
 * Natija bo'sh bo'lsa umuman chizilmaydi — aks holda "1 / 1" va ikkala
 * o'chgan tugma osilib qolardi.
 */
export function TablePagination({
  page,
  pageSize,
  total,
  onPage,
}: {
  /** 0 dan boshlanadi (so'rovdagi `skip = page * pageSize`). */
  page: number
  pageSize: number
  total: number
  onPage: (page: number) => void
}) {
  if (total === 0) return null
  const pages = Math.max(1, Math.ceil(total / pageSize))
  const from = page * pageSize + 1
  const to = Math.min((page + 1) * pageSize, total)

  return (
    <div className="mt-3 flex flex-wrap items-center justify-end gap-2">
      <span className="text-sm text-muted-foreground">
        <span className="num">{total}</span> tadan{" "}
        <span className="num">
          {from}–{to}
        </span>
      </span>
      <Button
        size="sm"
        variant="outline"
        disabled={page === 0}
        onClick={() => onPage(page - 1)}
      >
        Oldingi
      </Button>
      <span className="num text-sm text-muted-foreground">
        {page + 1} / {pages}
      </span>
      <Button
        size="sm"
        variant="outline"
        disabled={page + 1 >= pages}
        onClick={() => onPage(page + 1)}
      >
        Keyingi
      </Button>
    </div>
  )
}
