import { createFileRoute } from "@tanstack/react-router"

import ChangePassword from "@/components/UserSettings/ChangePassword"
import DeleteAccount from "@/components/UserSettings/DeleteAccount"
import UserInformation from "@/components/UserSettings/UserInformation"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import useCurrentUser from "@/hooks/useCurrentUser"

const tabsConfig = [
  { value: "my-profile", title: "Profilim", component: UserInformation },
  { value: "password", title: "Parol", component: ChangePassword },
  { value: "danger-zone", title: "Xavfli zona", component: DeleteAccount },
]

export const Route = createFileRoute("/_layout/settings")({
  component: UserSettings,
  head: () => ({
    meta: [
      {
        title: "Sozlamalar - MebeliX",
      },
    ],
  }),
})

function UserSettings() {
  const { currentUser } = useCurrentUser()
  const finalTabs = currentUser?.is_superuser
    ? tabsConfig.slice(0, 2)
    : tabsConfig

  if (!currentUser) {
    return null
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">
          Foydalanuvchi sozlamalari
        </h1>
        <p className="text-muted-foreground">
          Hisobingiz sozlamalari va parametrlarini boshqaring
        </p>
      </div>

      <Tabs defaultValue="my-profile">
        <TabsList>
          {finalTabs.map((tab) => (
            <TabsTrigger key={tab.value} value={tab.value}>
              {tab.title}
            </TabsTrigger>
          ))}
        </TabsList>
        {finalTabs.map((tab) => (
          <TabsContent key={tab.value} value={tab.value}>
            <tab.component />
          </TabsContent>
        ))}
      </Tabs>
    </div>
  )
}
