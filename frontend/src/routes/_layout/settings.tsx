import { createFileRoute } from "@tanstack/react-router"

import { PageHeader } from "@/components/Common/PageHeader"
import { ChangePassword } from "@/components/UserSettings/ChangePassword"
import { UserInformation } from "@/components/UserSettings/UserInformation"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { useCurrentUser } from "@/hooks/useCurrentUser"

const tabsConfig = [
  { value: "my-profile", title: "Profilim", component: UserInformation },
  { value: "password", title: "Parol", component: ChangePassword },
]

export const Route = createFileRoute("/_layout/settings")({
  component: UserSettings,
  head: () => ({
    meta: [
      {
        title: "Sozlamalar | MebeliX",
      },
    ],
  }),
})

function UserSettings() {
  const { currentUser } = useCurrentUser()

  if (!currentUser) {
    return null
  }

  return (
    <div>
      <PageHeader
        title="Foydalanuvchi sozlamalari"
        description="Hisobingiz sozlamalari va parametrlarini boshqaring"
      />

      <Tabs defaultValue="my-profile">
        <TabsList>
          {tabsConfig.map((tab) => (
            <TabsTrigger key={tab.value} value={tab.value}>
              {tab.title}
            </TabsTrigger>
          ))}
        </TabsList>
        {tabsConfig.map((tab) => (
          <TabsContent key={tab.value} value={tab.value}>
            <tab.component />
          </TabsContent>
        ))}
      </Tabs>
    </div>
  )
}
