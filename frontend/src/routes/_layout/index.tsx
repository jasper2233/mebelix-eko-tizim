import { createFileRoute } from "@tanstack/react-router"

import useCurrentUser from "@/hooks/useCurrentUser"

export const Route = createFileRoute("/_layout/")({
  component: Dashboard,
  head: () => ({
    meta: [
      {
        title: "Boshqaruv paneli - FastAPI Cloud",
      },
    ],
  }),
})

function Dashboard() {
  const { currentUser } = useCurrentUser()

  return (
    <div>
      <div>
        <h1 className="text-2xl truncate max-w-sm">
          Salom, {currentUser?.name || currentUser?.phone} 👋
        </h1>
        <p className="text-muted-foreground">
          Yana ko'rishganimizdan xursandmiz!
        </p>
      </div>
    </div>
  )
}
