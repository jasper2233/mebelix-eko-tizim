// Sex xo'jaligi bo'limining tablari (dizayndagi `sexTabs`): mahsulotlar va qoldiq · sexga kirim (F3) ·
// sex sarfi. Uchala sahifa ustida bir xil turadi.

import { Link } from "@tanstack/react-router"

import { cn } from "@/lib/utils"

type Tab = "list" | "give" | "log"

export function SexTabs({ active }: { active: Tab }) {
  const cls = (t: Tab) =>
    cn(
      "-mb-px border-b-2 px-3 py-2 text-sm",
      active === t
        ? "border-primary font-semibold text-foreground"
        : "border-transparent text-muted-foreground hover:text-foreground",
    )
  return (
    <nav className="flex gap-1 border-b" aria-label="Sex xo'jaligi">
      <Link to="/warehouse" search={{ katalog: "S" }} className={cls("list")}>
        Mahsulotlar va qoldiq
      </Link>
      <Link
        to="/warehouse/doc"
        search={{ turi: "sex" }}
        className={cls("give")}
      >
        Sexga kirim{" "}
        <kbd className="ml-1 rounded border px-1 text-[10px]">F3</kbd>
      </Link>
      <Link to="/warehouse/sex-sarfi" className={cls("log")}>
        Sex sarfi
      </Link>
    </nav>
  )
}
