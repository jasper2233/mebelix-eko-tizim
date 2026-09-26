// Kesish xaritasi belgisi — lucide'da mosi yo'q. `Grid2x2` teng to'rt katak: odatda «katak
// ko'rinishi» (Fluent `Grid`, Drive, Finder) yoki «oyna» (Material `window`, lucide teglari:
// window, skylight). `Map` esa geografik xarita. Haqiqiy kesish xaritasi — BITTA list, uni tekis
// kesimlar TENG BO'LMAGAN bo'laklarga ajratadi. Tsex ishlatadigan GibLab «Раскроить» tugmasini
// aynan shunday chizadi (giblab.com/images/icons/cuttingsheet.gif): yotiq list, bo'ylama kesim,
// ikki tomonida turli ko'ndalang kesimlar. Shu shakl lucide uslubida (24 katak, chiziq 2).
// Ishlatiladi: terminal «Xarita», buyurtma «Kesish xaritalari», «Kesish xaritasida ko'rsatish».

import { createLucideIcon } from "lucide-react"

export const CutMap = createLucideIcon("cut-map", [
  [
    "rect",
    { x: "2", y: "5", width: "20", height: "14", rx: "2", key: "sheet" },
  ],
  ["path", { d: "M10 5v14", key: "rip" }],
  ["path", { d: "M2 13h8", key: "left" }],
  ["path", { d: "M10 10h12", key: "right" }],
  ["path", { d: "M16 10v9", key: "cross" }],
])
