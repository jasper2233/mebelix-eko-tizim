/** Chap toolbar tugmasi: ikonka + kichik yozuv (sanoat HMI uslubi).
 * tone — funksiya bo'yicha rang kodi: primary (asosiy nav), warn (qulf), danger (chiqish). */
const TBTN_TONES = {
  default: "border bg-white text-primary hover:border-primary",
  primary:
    "border-transparent bg-primary text-primary-foreground hover:bg-primary/90",
  // warn to'ldirilmaydi: amber fon xarita apelsini bilan qo'shilib ketardi — faqat ikonka rangi
  warn: "border bg-white text-amber-600 hover:border-amber-500",
  danger: "border-transparent bg-red-600 text-white hover:bg-red-700",
  success: "border-transparent bg-green-600 text-white hover:bg-green-700",
} as const

export function TBtn({
  label,
  disabled = false,
  tone = "default",
  onClick,
  children,
}: {
  label: string
  disabled?: boolean
  tone?: keyof typeof TBTN_TONES
  onClick: () => void
  children: React.ReactNode
}) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      className={`flex h-16 w-full flex-col items-center justify-center gap-1 rounded-xl shadow-sm outline-none transition-all focus-visible:ring-[3px] focus-visible:ring-ring/50 active:scale-95 disabled:opacity-40 [&_svg]:size-6 ${TBTN_TONES[tone]}`}
    >
      {children}
      <span className="text-2xs font-bold leading-none">{label}</span>
    </button>
  )
}
