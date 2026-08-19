// Eski "Foydalanuvchilar" sahifasi — hodimlar bilan BIRLASHTIRILDI (/employees).
// Route saqlanadi: xatcho'p va eski havolalar 404 bermasin.

import { createFileRoute, redirect } from "@tanstack/react-router"

export const Route = createFileRoute("/_layout/admin")({
  beforeLoad: () => {
    throw redirect({ to: "/employees" })
  },
})
