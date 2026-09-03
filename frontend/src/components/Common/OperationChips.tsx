import { PROCESS_OPS } from "@/lib/mes"

/**
 * Marshrut qadamining AMAL nomi: kod 11 → "G petlya o'ngdan".
 *
 * Kodlar postga ko'pdan-birga tushadi (stolyarkada oltita amal, kromkada uchta,
 * arrada oddiy va 45° kesish) — chipsiz operator raqamni yoddan tarjima qilishi
 * kerak edi, va noto'g'ri petlya eshikni brak qiladi. Bitta amalli postda
 * (rover, bo'yoq, prisadka) hech narsa chizilmaydi: post nomi ekran
 * sarlavhasida turibdi.
 */
export function OperationChips({
  processCode,
  postCode,
  defaultCode,
}: {
  processCode: number | null | undefined
  postCode: string | null | undefined
  /** Postning ODATDAGI amali — chip chizilmaydi: «Kromka» chipi kromka
   *  postidagi har qatorda sarlavhani takrorlardi. Faqat farqli amal
   *  («Fasat kromka») ko'rinadi — ko'z aynan unga tushishi kerak. */
  defaultCode?: number
}) {
  const op = processCode == null ? undefined : PROCESS_OPS[processCode]
  // Post uchun yagona amal bo'lsa chip ortiqcha — sarlavhani takrorlaydi
  const many =
    op &&
    Object.values(PROCESS_OPS).filter((o) => o.post === op.post).length > 1
  if (!op || !many || (postCode && op.post !== postCode)) return null
  if (defaultCode != null && processCode === defaultCode) return null
  return (
    <div className="mt-1 flex flex-wrap gap-1">
      <span className="rounded-sm bg-amber-100 px-1.5 py-0.5 text-sm font-bold text-amber-900">
        {op.name}
      </span>
    </div>
  )
}
