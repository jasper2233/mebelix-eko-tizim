import { useSuspenseQuery } from "@tanstack/react-query"
import { createFileRoute, redirect } from "@tanstack/react-router"
import { Suspense } from "react"

import { type UserRead, UsersService } from "@/client"
import AddUser from "@/components/Admin/AddUser"
import { columns, type UserTableData } from "@/components/Admin/columns"
import { DataTable } from "@/components/Common/DataTable"
import PendingUsers from "@/components/Pending/PendingUsers"
import useCurrentUser from "@/hooks/useCurrentUser"
import { getUsersQueryOptions } from "@/queries/users"

export const Route = createFileRoute("/_layout/admin")({
  component: Admin,
  beforeLoad: async () => {
    // Sahifa superuser'lar uchun — backend ham endi ro'yxatni faqat superuser'ga beradi.
    const user = await UsersService.readUserMe()
    if (!user.is_superuser) {
      throw redirect({ to: "/" })
    }
  },
  head: () => ({
    meta: [
      {
        title: "Foydalanuvchilar - MebeliX",
      },
    ],
  }),
})

function UsersTableContent() {
  const { currentUser } = useCurrentUser()
  const { data: users } = useSuspenseQuery(getUsersQueryOptions())

  const tableData: UserTableData[] = users.data.map((user: UserRead) => ({
    ...user,
    isCurrentUser: currentUser?.id === user.id,
  }))

  return <DataTable columns={columns} data={tableData} />
}

function UsersTable() {
  return (
    <Suspense fallback={<PendingUsers />}>
      <UsersTableContent />
    </Suspense>
  )
}

function Admin() {
  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">
            Foydalanuvchilar
          </h1>
          <p className="text-muted-foreground">
            Foydalanuvchi hisoblari va huquqlarini boshqaring
          </p>
        </div>
        <AddUser />
      </div>
      <UsersTable />
    </div>
  )
}
