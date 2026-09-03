import { createFileRoute, redirect } from "@tanstack/react-router"

// Eski manzil: sahifa 2026-09-03 da `/agents` bo'ldi (fayl ham `agents.tsx`) —
// agent tsex kompyuteri, printer emas. Eski bookmark va yo'riqnomalar uchun redirect.
export const Route = createFileRoute("/_layout/printers")({
  beforeLoad: () => {
    throw redirect({ to: "/agents" })
  },
})
