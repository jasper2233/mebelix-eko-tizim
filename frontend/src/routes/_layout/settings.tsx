import { createFileRoute } from "@tanstack/react-router"

import { PageHeader } from "@/components/Common/PageHeader"
import { ChangePassword } from "@/components/UserSettings/ChangePassword"
import { UserInformation } from "@/components/UserSettings/UserInformation"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { useCurrentUser } from "@/hooks/useCurrentUser"

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
          <TabsTrigger value="my-profile">Profilim</TabsTrigger>
          <TabsTrigger value="password">Parol</TabsTrigger>
        </TabsList>
        <TabsContent value="my-profile">
          <UserInformation />
        </TabsContent>
        <TabsContent value="password">
          <ChangePassword />
        </TabsContent>
      </Tabs>
    </div>
  )
}
