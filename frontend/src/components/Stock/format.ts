/** Ombor raqamlarini ko'rsatish — bir joyda, chunki jadval, dialoglar va sotuv
 * ro'yxati bir xil formatda chiqishi kerak. */

/** Decimal API'dan SATR sifatida keladi (`"107.000"`) — hisob va ko'rsatish
 * uchun bir joyda raqamga o'giriladi. */
export const num = (v: string | number | null | undefined) => Number(v ?? 0)

export const uzs = (v: string | number | null | undefined) =>
  num(v).toLocaleString("ru-RU")

/** Qoldiq butun bo'lsa kasrsiz: 174 dona "174.000" bo'lib ko'rinmasin */
export const qty = (v: string | number) =>
  Number.isInteger(num(v))
    ? String(num(v))
    : num(v).toFixed(3).replace(/0+$/, "")
