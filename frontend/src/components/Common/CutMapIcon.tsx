// Kesish xaritasi belgisi: lucide'da mosi yo'q (sabablari — docs/06 «Belgilar lug'ati»).
// GibLab «Раскроить» shakli — yotiq list, teng bo'lmagan bo'laklar — lucide uslubida.

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
