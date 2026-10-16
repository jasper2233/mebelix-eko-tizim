// Eski «Sotuv listi» manzili. 2026-10-16 dan sotuv — bazadagi Sotuv (chiqim) HUJJATI (docs/14 §9):
// qoralama → tasdiq, qoldiqdan yechiladi, «Shartnoma» o'sha hujjatdan chop etiladi. Brauzerda
// saqlanadigan list (`mebelix.sotuv-listi.v1`) olib tashlandi; eski havola va xatchoplar shu yerga.

import { createFileRoute, redirect } from "@tanstack/react-router"

export const Route = createFileRoute("/_layout/sotuv")({
  beforeLoad: () => {
    throw redirect({ to: "/warehouse/doc", search: { turi: "chiqim" } })
  },
})
