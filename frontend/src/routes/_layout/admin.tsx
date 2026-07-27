import { useSuspenseQuery } from "@tanstack/react-query"
import { createFileRoute, redirect } from "@tanstack/react-router"
import { Suspense } from "react"

import { type UserRead, UsersService } from "@/client"
import AddUser from "@/components/Admin/AddUser"
import { UserActionsMenu } from "@/components/Admin/UserActionsMenu"
import PendingUsers from "@/components/Pending/PendingUsers"
import { Badge } from "@/components/ui/badge"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import useCurrentUser from "@/hooks/useCurrentUser"
import { ROLE_LABELS } from "@/lib/mes"
import { cn } from "@/lib/utils"
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

function UserRow({ user, isMe }: { user: UserRead; isMe: boolean }) {
  return (
    <TableRow>
      <TableCell>
        <div className="flex items-center gap-2">
          <span
            className={cn("font-medium", !user.name && "text-muted-foreground")}
          >
            {user.name || "—"}
          </span>
          {isMe && (
            <Badge variant="outline" className="text-xs">
              Siz
            </Badge>
          )}
        </div>
      </TableCell>
      <TableCell className="text-muted-foreground">{user.phone}</TableCell>
      <TableCell>
        <Badge
          variant={
            user.is_superuser || user.role === "admin" ? "default" : "secondary"
          }
        >
          {user.is_superuser ? "Admin" : (ROLE_LABELS[user.role] ?? user.role)}
        </Badge>
      </TableCell>
      <TableCell>
        <div className="flex items-center gap-2">
          <span
            className={cn(
              "size-2 rounded-full",
              user.is_active ? "bg-green-500" : "bg-gray-400",
            )}
          />
          <span className={user.is_active ? "" : "text-muted-foreground"}>
            {user.is_active ? "Faol" : "Faol emas"}
          </span>
        </div>
      </TableCell>
      <TableCell>
        <div className="flex justify-end">
          <UserActionsMenu user={user} />
        </div>
      </TableCell>
    </TableRow>
  )
}

function UsersTableContent() {
  const { currentUser } = useCurrentUser()
  const { data: users } = useSuspenseQuery(getUsersQueryOptions())

  return (
    // Sahifalash yo'q: getUsersQueryOptions barcha sahifalarni bitta ro'yxatga
    // yig'adi va zavodda foydalanuvchilar o'nlab. Boshqa registrlar ham shunday.
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>To&apos;liq ism</TableHead>
          <TableHead>Telefon</TableHead>
          <TableHead>Rol</TableHead>
          <TableHead>Holat</TableHead>
          <TableHead>
            <span className="sr-only">Amallar</span>
          </TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {users.data.length ? (
          users.data.map((user: UserRead) => (
            <UserRow
              key={user.id}
              user={user}
              isMe={currentUser?.id === user.id}
            />
          ))
        ) : (
          <TableRow>
            <TableCell
              colSpan={5}
              className="h-24 text-center text-muted-foreground"
            >
              Natija topilmadi.
            </TableCell>
          </TableRow>
        )}
      </TableBody>
    </Table>
  )
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
