// Kirish sahifasining asosiy chaqirig'i: beyjikni skanerlang.
//
// Nega TUGMA emas: skaner tugmasiz ishlaydi (klaviatura kabi yozadi). Bosilganda
// hech nima qilmaydigan tugma — yolg'on afforadans. Punktir ramka ham shunday
// edi: bu loyihada punktir "faylni shu yerga tashlang" degani (Buyurtmalardagi
// drag&drop zonasi), ya'ni bosiladigan narsa bo'lib ko'rinardi.
//
// O'rniga — beyjikning O'ZI chizilgan: lentali karta va ichida QR. Operator
// ekranga qaraganda qo'lidagi narsani ko'radi, hech nima o'qimasdan tushunadi.
// Chiziq tili chap paneldagi kesish xaritasi bilan bir xil (ingichka kontur +
// `mx-draw` bilan chizilib chiqishi), shuning uchun yangi bezak qo'shilmaydi.

const NAVY = "var(--brand-navy-deep)"
const GOLD = "var(--brand-gold-deep)"

export function BadgePrompt({
  pending,
}: {
  /** Skan yuborildi — javob kutilmoqda */
  pending: boolean
}) {
  return (
    <div className="flex flex-col items-center gap-4 py-2">
      <BadgeCard pending={pending} />
      <div className="text-center">
        <p className="text-2xl font-bold tracking-tight lg:text-3xl">
          {pending ? "Tekshirilmoqda..." : "Beyjikni skanerlang"}
        </p>
        <p className="mt-1 text-sm text-muted-foreground lg:text-base">
          Smena avtomatik ochiladi
        </p>
      </div>
    </div>
  )
}

function BadgeCard({ pending }: { pending: boolean }) {
  /** QR burchak belgisi — qalin halqa, ichida nuqta. Ingichka kontur bu
   *  o'lchamda QR emas, kichkina ikonka bo'lib ko'rinardi. */
  const finder = (x: number, y: number) => (
    <>
      <rect
        x={x}
        y={y}
        width="19"
        height="19"
        rx="2"
        fill="none"
        stroke="currentColor"
        strokeWidth="4"
      />
      <rect x={x + 6.5} y={y + 6.5} width="6" height="6" fill="currentColor" />
    </>
  )
  return (
    <svg
      viewBox="0 0 120 148"
      width="120"
      height="148"
      aria-hidden="true"
      className="shrink-0"
    >
      {/* Karta va lenta teshigi. Bo'yin lentasi ATAYLAB chizilmagan: ikki
          diagonal chiziq kartani beyjik emas, mo'ylovli narsaga o'xshatardi.
          Teshikning o'zi "bu — beyjik" deyish uchun yetarli. */}
      <g
        stroke={NAVY}
        strokeOpacity="0.45"
        strokeWidth="1.5"
        fill="none"
        className="mx-draw"
      >
        {/* pathLength <g> da emas, har bir shaklda: `mx-draw` dagi
            stroke-dasharray:1 aynan shu normallashtirishga tayanadi. */}
        <rect x="5" y="5" width="110" height="138" rx="10" pathLength={1} />
        <rect x="46" y="17" width="28" height="6" rx="3" pathLength={1} />
      </g>
      {/* QR: uchta burchak belgisi + o'ng-pastdagi modul to'plami. Tarqoq
          nuqta emas — QR grammatikasi: burchaklar tanish, o'ng-past to'la.
          Ataylab TO'LIQ EMAS, ekrandagi kod skanerlanmasin. */}
      <g
        className="mx-fade"
        style={{ animationDelay: "0.45s" }}
        color={pending ? NAVY : GOLD}
      >
        {finder(30, 40)}
        {finder(71, 40)}
        {finder(30, 81)}
        <g fill="currentColor">
          <rect x="71" y="81" width="6" height="6" />
          <rect x="84" y="81" width="6" height="6" />
          <rect x="77" y="88" width="6" height="6" />
          <rect x="71" y="94" width="6" height="6" />
          <rect x="84" y="94" width="6" height="6" />
        </g>
      </g>
      {/* Skan-chizig'i: QR ustidan har 2.8 s da bir marta o'tadi — "ekran
          kutmoqda, kartani tuting" degani, matnsiz. Yumshoq (1.5 px, ≤0.35
          xiralik): kioskda doimiy yaltirash bezovta qiladi. `pending` da
          yo'q (QR navy'ga o'tgan — javob kutilmoqda), reduced-motion'da CSS
          o'chiradi. */}
      {!pending && (
        <rect
          x="26"
          y="38"
          width="68"
          height="1.5"
          rx="0.75"
          fill={GOLD}
          className="mx-scan"
        />
      )}
      {/* Kodning tagidagi bosilgan ism — haqiqiy beyjikda ham shunday turadi */}
      <g fill={NAVY} fillOpacity="0.16" className="mx-fade">
        <rect x="30" y="115" width="60" height="5" rx="2.5" />
        <rect x="30" y="126" width="38" height="5" rx="2.5" />
      </g>
    </svg>
  )
}
