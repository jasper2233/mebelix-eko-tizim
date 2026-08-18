import { useQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"

import type { UserRead } from "@/client"
import { AddUser } from "@/components/Admin/AddUser"
import { UserActionsMenu } from "@/components/Admin/UserActionsMenu"
import { EmptyRow } from "@/components/Common/EmptyRow"
import { PageHeader } from "@/components/Common/PageHeader"
import { QueryError } from "@/components/Common/QueryError"
import { Badge } from "@/components/ui/badge"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { useCurrentUser } from "@/hooks/useCurrentUser"
import { requireAccess } from "@/lib/guards"
import { isSuperuser, ROLE_LABELS } from "@/lib/mes"
import { cn } from "@/lib/utils"
import { getUsersQueryOptions } from "@/queries/users"

export const Route = createFileRoute("/_layout/admin")({
  component: Admin,
  // Sahifa superuser'lar uchun — backend ham ro'yxatni faqat superuser'ga beradi.
  beforeLoad: requireAccess(isSuperuser),
  head: () => ({
    meta: [
      {
        title: "Foydalanuvchilar | MebeliX",
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
      <TableCell className="num text-muted-foreground">{user.phone}</TableCell>
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
              user.is_active ? "bg-green-500" : "bg-muted-foreground/50",
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

function UsersTable() {
  const { currentUser } = useCurrentUser()
  const {
    data: users,
    isLoading,
    isError,
    refetch,
  } = useQuery(getUsersQueryOptions())

  return isLoading ? (
    <Skeleton className="h-64 w-full" />
  ) : isError ? (
    <QueryError onRetry={() => refetch()} />
  ) : (
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
        {users?.data.length ? (
          users.data.map((user: UserRead) => (
            <UserRow
              key={user.id}
              user={user}
              isMe={currentUser?.id === user.id}
            />
          ))
        ) : (
          <EmptyRow colSpan={5}>
            Hali foydalanuvchi yo&apos;q — &quot;Foydalanuvchi
            qo&apos;shish&quot; bilan qo&apos;shing.
          </EmptyRow>
        )}
      </TableBody>
    </Table>
  )
}

function Admin() {
  return (
    <div>
      <PageHeader
        title="Foydalanuvchilar"
        description="Foydalanuvchi hisoblari va huquqlarini boshqaring"
        actions={<AddUser />}
      />
      <UsersTable />
    </div>
  )
}
