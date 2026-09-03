import { Footer } from "./Footer"

interface AuthLayoutProps {
  children: React.ReactNode
}

const GOLD = "var(--brand-gold)"

// Stilizatsiya qilingan kesish xaritasi — login sahifaning imzo elementi.
// Haqiqiy `SheetSvg` qoidalarida chizilgan: tsexdagi 2750×1830 list tik
// turgan holda, nom markazda, ENI pastki-chapda, BO'YI o'ng qirrada (yuqoridan
// pastga), kromka harflari o'lcham yonida. Chiziqlar sahifa ochilganda
// chizilib paydo bo'ladi.
const SHEET_W = 1830
const SHEET_H = 2750
const S = 600 / SHEET_W // mm → SVG birlik
const X = (mm: number) => 60 + mm * S
const Y = (mm: number) => 80 + mm * S

type ArtPart = {
  x: number
  y: number
  w: number
  h: number
  name: string
  eW: string
  eH: string
  hi?: boolean
}
// Giyotina kesim: uch gorizontal band, har bandda o'z tik kesimlari; o'ngda
// 30 mm, pastda 450 mm qoldiq.
const PARTS: ArtPart[] = [
  // Ajratilgan detal TEPADA: pastki uchdan biri tagline bilan qoplanadi
  {
    x: 0,
    y: 0,
    w: 720,
    h: 900,
    name: "№1 eshik",
    eW: "AA",
    eH: "AA",
    hi: true,
  },
  { x: 720, y: 0, w: 720, h: 900, name: "№2 bok", eW: "AA", eH: "A" },
  { x: 1440, y: 0, w: 360, h: 900, name: "№3 tokcha", eW: "A", eH: "" },
  { x: 0, y: 900, w: 850, h: 700, name: "№4 bok", eW: "AA", eH: "A" },
  { x: 850, y: 900, w: 950, h: 350, name: "№5 polka", eW: "A", eH: "" },
  { x: 850, y: 1250, w: 950, h: 350, name: "№6 polka", eW: "A", eH: "" },
  { x: 0, y: 1600, w: 1000, h: 700, name: "№7 ustki", eW: "AA", eH: "A" },
  { x: 1000, y: 1600, w: 800, h: 700, name: "№8 pastki", eW: "AA", eH: "A" },
]
const CUTS: [number, number, number, number, number][] = [
  // x1, y1, x2, y2 (mm), kechikish
  [0, 900, SHEET_W, 900, 0.15],
  [0, 1600, SHEET_W, 1600, 0.25],
  [0, 2300, SHEET_W, 2300, 0.35],
  [1800, 0, 1800, 2300, 0.45],
  [720, 0, 720, 900, 0.5],
  [1440, 0, 1440, 900, 0.55],
  [850, 900, 850, 1600, 0.6],
  [850, 1250, 1800, 1250, 0.65],
  [1000, 1600, 1000, 2300, 0.7],
]

function CutmapArt() {
  const cut = (delay: number) => ({
    className: "mx-draw",
    style: { animationDelay: `${delay}s` },
    pathLength: 1,
  })
  const label = (delay: number) => ({
    className: "mx-fade",
    style: { animationDelay: `${delay}s` },
  })
  return (
    <svg
      viewBox="0 0 720 1040"
      preserveAspectRatio="xMidYMin slice"
      aria-hidden="true"
      className="pointer-events-none absolute inset-0 h-full w-full select-none"
    >
      {/* Butun xarita logo zonasidan pastda tursin */}
      <g transform="translate(0 70)">
        {/* Plita o'lcham chizig'i */}
        <g stroke={GOLD} strokeOpacity="0.35" strokeWidth="1">
          <line x1={X(0)} y1="48" x2={X(SHEET_W)} y2="48" {...cut(0.9)} />
          <line x1={X(0)} y1="40" x2={X(0)} y2="56" {...cut(0.9)} />
          <line x1={X(SHEET_W)} y1="40" x2={X(SHEET_W)} y2="56" {...cut(0.9)} />
          <line x1="28" y1={Y(0)} x2="28" y2={Y(SHEET_H)} {...cut(1.0)} />
          <line x1="20" y1={Y(0)} x2="36" y2={Y(0)} {...cut(1.0)} />
          <line x1="20" y1={Y(SHEET_H)} x2="36" y2={Y(SHEET_H)} {...cut(1.0)} />
        </g>
        <g
          fill={GOLD}
          fillOpacity="0.55"
          fontSize="13"
          letterSpacing="0.08em"
          {...label(1.2)}
        >
          {/* List tik turgan holatda: qisqa tomon tepada */}
          <text x={X(SHEET_W / 2)} y="38" textAnchor="middle">
            {SHEET_W}
          </text>
          <text
            x="16"
            y={Y(SHEET_H / 2)}
            textAnchor="middle"
            transform={`rotate(-90 16 ${Y(SHEET_H / 2)})`}
          >
            {SHEET_H}
          </text>
        </g>

        {/* Plita konturi */}
        <rect
          x={X(0)}
          y={Y(0)}
          width={SHEET_W * S}
          height={SHEET_H * S}
          fill="none"
          stroke={GOLD}
          strokeOpacity="0.45"
          strokeWidth="1.5"
          {...cut(0)}
        />

        {/* Giyotina kesimlar */}
        <g stroke={GOLD} strokeOpacity="0.3" strokeWidth="1">
          {CUTS.map(([x1, y1, x2, y2, d]) => (
            <line
              key={`${x1}-${y1}-${x2}-${y2}`}
              x1={X(x1)}
              y1={Y(y1)}
              x2={X(x2)}
              y2={Y(y2)}
              {...cut(d)}
            />
          ))}
        </g>

        {/* Ajratilgan detal — to'rt tomoni kromkali (qalin qirralar) */}
        {PARTS.filter((p) => p.hi).map((p) => (
          <g key={`hi-${p.name}`}>
            <rect
              x={X(p.x)}
              y={Y(p.y)}
              width={p.w * S}
              height={p.h * S}
              fill={GOLD}
              fillOpacity="0.08"
              stroke="none"
              {...label(0.9)}
            />
            <rect
              x={X(p.x)}
              y={Y(p.y)}
              width={p.w * S}
              height={p.h * S}
              fill="none"
              stroke={GOLD}
              strokeOpacity="0.75"
              strokeWidth="3"
              {...cut(0.8)}
            />
          </g>
        ))}

        {/* Detal yozuvlari — xaritadagi kabi: nom markazda, eni pastki-chapda,
            bo'yi o'ng qirrada yuqoridan pastga */}
        {PARTS.map((p, i) => {
          const op = p.hi ? 0.85 : 0.45
          const rx = X(p.x + p.w) - 12
          const ty = Y(p.y) + 10
          return (
            <g
              key={p.name}
              fill={GOLD}
              fillOpacity={op}
              letterSpacing="0.06em"
              {...label(1.1 + i * 0.07)}
            >
              <text
                x={X(p.x + p.w / 2)}
                y={Y(p.y + p.h / 2)}
                textAnchor="middle"
                dominantBaseline="middle"
                fontSize={p.hi ? 16 : 13}
                fontWeight={p.hi ? 600 : 400}
              >
                {p.name}
              </text>
              <text x={X(p.x) + 10} y={Y(p.y + p.h) - 8} fontSize="11">
                {p.w}
                {p.eW ? ` ${p.eW}` : ""}
              </text>
              <text
                x={rx}
                y={ty}
                fontSize="11"
                transform={`rotate(90 ${rx} ${ty})`}
              >
                {p.h}
                {p.eH ? ` ${p.eH}` : ""}
              </text>
            </g>
          )
        })}
      </g>
    </svg>
  )
}

export function AuthLayout({ children }: AuthLayoutProps) {
  return (
    <div className="grid min-h-svh lg:grid-cols-2">
      <div className="relative hidden overflow-hidden bg-(--brand-navy-deep) lg:block">
        <CutmapArt />
        {/* Tagline o'qilishi uchun pastki qoraytirish */}
        <div
          aria-hidden="true"
          className="absolute inset-x-0 bottom-0 h-64 bg-gradient-to-t from-(--brand-navy-deep) to-transparent"
        />
        <div className="absolute inset-0 flex flex-col justify-between p-10 xl:p-16">
          <img
            src="/assets/logo/logo-gold.png"
            alt="MebeliX"
            className="h-12 w-auto self-start"
          />
          <div className="flex flex-col gap-3">
            <p className="text-2xs font-medium uppercase tracking-[0.3em] text-(--brand-gold)/80">
              Ishlab chiqarishni boshqarish tizimi
            </p>
            <p className="max-w-md text-2xl font-semibold leading-snug text-white/90 xl:text-3xl">
              Kesishdan yetkazishgacha — har bir detal nazorat ostida.
            </p>
          </div>
        </div>
      </div>
      <div className="relative flex flex-col gap-4 overflow-hidden p-6 md:p-10">
        <img
          src="/assets/logo/icon-navy.png"
          alt=""
          aria-hidden="true"
          className="pointer-events-none absolute -right-14 -bottom-14 w-96 opacity-5 select-none lg:hidden"
        />
        <div className="flex flex-1 items-center justify-center">
          <div className="w-full max-w-md">{children}</div>
        </div>
        <Footer />
      </div>
    </div>
  )
}
