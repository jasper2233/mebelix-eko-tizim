/** Moliya, Soliq va Buxgalteriya sahifalarining bo'limlari (`?b=`). Sahifa tablari va Ctrl+K qidiruvi
 *  (`Common/CommandPalette`) shu ro'yxatdan — bo'lim nomi bir joyda. */

export const MOLIYA_BOLIMLAR = [
  { v: "bosh", l: "Bosh sahifa" },
  { v: "debitorlar", l: "Mijozlar qarzi" },
  { v: "kreditorlar", l: "Bizning qarz" },
  { v: "kalendar", l: "To'lov kalendari" },
  { v: "jurnal", l: "Orderlar jurnali" },
  { v: "smenalar", l: "Smenalar" },
  { v: "hisobotlar", l: "Hisobotlar" },
  { v: "ishhaqi", l: "Ish haqi" },
  { v: "tannarx", l: "Tannarx" },
  { v: "davrlar", l: "Davr yopish" },
  { v: "sozlamalar", l: "Sozlamalar" },
] as const

export const SOLIQ_BOLIMLAR = [
  { v: "esf", l: "ESF — sotuv" },
  { v: "kiruvchi", l: "Kiruvchi ESF" },
  { v: "hisobot", l: "Soliq va QQS kitobi" },
  { v: "sozlamalar", l: "Sozlamalar" },
] as const

export const BUX_BOLIMLAR = [
  { v: "saldo", l: "Aylanma-saldo" },
  { v: "kartochka", l: "Schyot kartochkasi" },
  { v: "provodkalar", l: "Provodkalar" },
  { v: "nazorat", l: "Nazorat" },
  { v: "sozlamalar", l: "Schyotlar va qoidalar" },
] as const
