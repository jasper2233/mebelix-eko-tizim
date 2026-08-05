import { Footer } from "./Footer"

interface AuthLayoutProps {
  children: React.ReactNode
}

const GOLD = "var(--brand-gold)"

// Stilizatsiya qilingan kesish xaritasi (2440×1220 laminat plita, GibSaw uslubi) —
// login sahifaning imzo elementi. Chiziqlar sahifa ochilganda chizilib paydo bo'ladi.
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
          <line x1="60" y1="48" x2="660" y2="48" {...cut(0.9)} />
          <line x1="60" y1="40" x2="60" y2="56" {...cut(0.9)} />
          <line x1="660" y1="40" x2="660" y2="56" {...cut(0.9)} />
          <line x1="28" y1="80" x2="28" y2="960" {...cut(1.0)} />
          <line x1="20" y1="80" x2="36" y2="80" {...cut(1.0)} />
          <line x1="20" y1="960" x2="36" y2="960" {...cut(1.0)} />
        </g>
        <g
          fill={GOLD}
          fillOpacity="0.55"
          fontSize="13"
          letterSpacing="0.08em"
          {...label(1.2)}
        >
          {/* 2440x1220 list tik turgan holatda: qisqa tomon tepada */}
          <text x="345" y="38" textAnchor="middle">
            1220
          </text>
          <text
            x="16"
            y="524"
            textAnchor="middle"
            transform="rotate(-90 16 524)"
          >
            2440
          </text>
        </g>

        {/* Plita konturi */}
        <rect
          x="60"
          y="80"
          width="600"
          height="880"
          fill="none"
          stroke={GOLD}
          strokeOpacity="0.45"
          strokeWidth="1.5"
          {...cut(0)}
        />

        {/* Guillotine kesimlar */}
        <g stroke={GOLD} strokeOpacity="0.3" strokeWidth="1">
          <line x1="60" y1="380" x2="660" y2="380" {...cut(0.15)} />
          <line x1="300" y1="80" x2="300" y2="380" {...cut(0.3)} />
          <line x1="470" y1="80" x2="470" y2="380" {...cut(0.4)} />
          <line x1="340" y1="380" x2="340" y2="960" {...cut(0.5)} />
          <line x1="340" y1="540" x2="660" y2="540" {...cut(0.6)} />
          <line x1="60" y1="700" x2="660" y2="700" {...cut(0.7)} />
        </g>

        {/* Ajratilgan detal — kromkali (qalin) qirralar bilan */}
        <rect
          x="60"
          y="380"
          width="280"
          height="320"
          fill={GOLD}
          fillOpacity="0.08"
          stroke="none"
          {...label(0.9)}
        />
        <g stroke={GOLD} strokeOpacity="0.75" strokeWidth="3">
          <line x1="60" y1="380" x2="340" y2="380" {...cut(0.8)} />
          <line x1="60" y1="700" x2="340" y2="700" {...cut(0.8)} />
        </g>

        {/* Detal yorliqlari */}
        <g
          fill={GOLD}
          fillOpacity="0.5"
          fontSize="13"
          letterSpacing="0.06em"
          {...label(1.35)}
        >
          <text x="76" y="106">
            KK-01 · 590×740
          </text>
          <text x="316" y="106">
            KD-04 · 420×740
          </text>
          <text x="486" y="106">
            PZ-02 · 460×740
          </text>
          <text x="356" y="406">
            KK-07 · 790×395
          </text>
          <text x="356" y="566">
            TD-03 · 790×395
          </text>
          <text x="76" y="726">
            KR-05 · 690×640
          </text>
          <text x="356" y="726">
            TSh-09 · 790×640
          </text>
        </g>
        <g {...label(1.1)}>
          <text
            x="88"
            y="416"
            fill={GOLD}
            fillOpacity="0.85"
            fontSize="15"
            fontWeight="600"
            letterSpacing="0.06em"
          >
            DR-11 · 690×790
          </text>
          <text
            x="88"
            y="438"
            fill="#ffffff"
            fillOpacity="0.45"
            fontSize="12"
            letterSpacing="0.1em"
          >
            KROMKA: 2 TOMON
          </text>
        </g>
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
          className="pointer-events-none absolute -right-14 -bottom-14 w-96 opacity-[0.05] select-none lg:hidden"
        />
        <div className="flex flex-1 items-center justify-center">
          <div className="w-full max-w-md">{children}</div>
        </div>
        <Footer />
      </div>
    </div>
  )
}
