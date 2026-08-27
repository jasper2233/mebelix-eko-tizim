// MX logotipli yuklanish indikatori — spinner o'rniga brend.
//
// Naqsh: kontur o'zini CHIZADI (M keyin X — dash bitta yo'l bo'ylab oqadi),
// so'ng to'ladi, so'nadi va qaytadan boshlanadi. Rang currentColor: ochiq
// fonda text-primary, tabloda oltin — komponent o'zi rang tanlamaydi.
// Vektor icon-navy.png dan potrace bilan olingan (piksel-mos tekshirilgan).
//
// QAYERDA ISHLATILADI: sahifa/route darajasidagi kutishlar. Tugma ichidagi
// 16-20px spinner (LoadingButton) va toast ikonkasi ATAYLAB o'zgarmagan —
// u masshtabda logo shovqin, spinner esa tanish konvensiya.

export const MX_VIEWBOX = "0 0 1046 760"
export const MX_PATH =
  "M259 748 C250 726 202 609 142 466 C17 165 1 124 1 123 C2 123 7 124 13 124 C107 138 331 259 411 339 C421 349 434 365 434 366 C433 366 425 361 415 356 C316 298 243 270 166 261 C149 258 104 257 104 259 C104 259 142 310 188 372 C339 573 396 652 393 654 C393 655 364 678 330 706 C295 734 266 758 265 759 C264 760 263 759 259 748 Z M688 714 C658 689 632 668 631 667 L629 665 L643 643 C684 577 731 506 775 442 C783 431 789 421 789 421 C788 420 747 370 696 310 C646 250 604 199 602 198 L600 195 L590 201 C547 231 515 265 465 333 C446 359 441 366 440 364 C440 363 453 318 463 288 C485 221 513 148 547 68 C570 15 576 1 577 1 C577 1 578 3 579 5 C585 25 607 74 623 100 C666 173 732 251 821 332 C828 339 836 346 838 347 L841 350 L861 324 C909 260 951 206 991 160 C1009 139 1022 125 1023 125 C1023 126 1003 174 939 318 C919 363 903 400 902 401 C902 402 902 404 903 404 C904 405 917 416 933 429 C960 451 1001 484 1031 507 L1046 519 L1031 540 C981 610 966 629 965 630 C965 630 940 601 911 566 L858 502 L855 507 C821 584 752 741 748 753 C747 756 745 759 745 759 C744 759 719 739 688 714 Z"

export function BrandLoader({
  size = 96,
  label,
  className = "",
}: {
  /** Logo eni px — balandlik nisbatdan (760/1046) kelib chiqadi */
  size?: number
  label?: string
  className?: string
}) {
  return (
    <div
      className={`flex flex-col items-center justify-center gap-4 ${className}`}
      role="status"
      aria-label={label ?? "Yuklanmoqda"}
    >
      <svg
        viewBox={MX_VIEWBOX}
        style={{ width: size, height: (size * 760) / 1046 }}
        aria-hidden="true"
      >
        {/* SHARPA: to'liq siluet doim xira ko'rinib turadi — yuklanish 500ms da
            tugasa ham foydalanuvchi chala chiziq emas, brendni ko'radi;
            chizish animatsiyasi ustida bezak bo'lib o'ynaydi */}
        <path d={MX_PATH} fill="currentColor" opacity={0.12} />
        <path
          d={MX_PATH}
          pathLength={1}
          className="mx-loader-path"
          fill="currentColor"
          stroke="currentColor"
          strokeWidth={14}
          strokeLinejoin="round"
        />
      </svg>
      {label && (
        <span className="text-sm font-medium tracking-wide text-muted-foreground">
          {label}
        </span>
      )}
    </div>
  )
}
