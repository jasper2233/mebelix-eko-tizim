import { createFileRoute } from "@tanstack/react-router"

import useCurrentUser from "@/hooks/useCurrentUser"

export const Route = createFileRoute("/_layout/")({
  component: Dashboard,
  head: () => ({
    meta: [
      {
        title: "Boshqaruv paneli - MebeliX",
      },
    ],
  }),
})

function Dashboard() {
  const { currentUser } = useCurrentUser()

  return (
    <div>
      <h1 className="text-3xl font-bold tracking-tight">
        Salom, {currentUser?.name || currentUser?.phone} 👋
      </h1>
      <p className="mt-1 text-muted-foreground">
        Yana ko'rishganimizdan xursandmiz!
      </p>
    </div>
  )
}
