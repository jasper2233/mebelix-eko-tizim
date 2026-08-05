import { partOperations } from "@/lib/mes"

/**
 * Noodatiy detalning SHU POSTDAGI amali: "eshik {7;11;8}" → "G petlya o'ngdan".
 *
 * Kodlar postga ko'pdan-birga tushadi (stolyarkada oltita amal, arrada oddiy va
 * 45° kesish) — chipsiz operator raqamni yoddan tarjima qilishi kerak edi, va
 * noto'g'ri petlya eshikni brak qiladi. Bitta amalli postda (rover, bo'yoq)
 * hech narsa chizilmaydi: post nomi ekran sarlavhasida turibdi.
 */
export function OperationChips({
  name,
  postCode,
}: {
  name: string
  postCode: string | null | undefined
}) {
  const ops = postCode ? partOperations(name, postCode) : []
  if (!ops.length) return null
  return (
    <div className="mt-1 flex flex-wrap gap-1">
      {ops.map((op) => (
        <span
          key={op}
          className="rounded-sm bg-amber-100 px-1.5 py-0.5 text-sm font-bold text-amber-900"
        >
          {op}
        </span>
      ))}
    </div>
  )
}
