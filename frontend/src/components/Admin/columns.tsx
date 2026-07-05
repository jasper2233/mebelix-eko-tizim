import type { ColumnDef } from "@tanstack/react-table"

import type { UserRead } from "@/client"
import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"
import { UserActionsMenu } from "./UserActionsMenu"

export type UserTableData = UserRead & {
  isCurrentUser: boolean
}

export const columns: ColumnDef<UserTableData>[] = [
  {
    accessorKey: "name",
    header: "To'liq ism",
    cell: ({ row }) => {
      const fullName = row.original.name
      return (
        <div className="flex items-center gap-2">
          <span
            className={cn("font-medium", !fullName && "text-muted-foreground")}
          >
            {fullName || "—"}
          </span>
          {row.original.isCurrentUser && (
            <Badge variant="outline" className="text-xs">
              Siz
            </Badge>
          )}
        </div>
      )
    },
  },
  {
    accessorKey: "phone",
    header: "Telefon",
    cell: ({ row }) => (
      <span className="text-muted-foreground">{row.original.phone}</span>
    ),
  },
  {
    accessorKey: "is_superuser",
    header: "Rol",
    cell: ({ row }) => (
      <Badge variant={row.original.is_superuser ? "default" : "secondary"}>
        {row.original.is_superuser ? "Admin" : "Foydalanuvchi"}
      </Badge>
    ),
  },
  {
    accessorKey: "is_active",
    header: "Holat",
    cell: ({ row }) => (
      <div className="flex items-center gap-2">
        <span
          className={cn(
            "size-2 rounded-full",
            row.original.is_active ? "bg-green-500" : "bg-gray-400",
          )}
        />
        <span className={row.original.is_active ? "" : "text-muted-foreground"}>
          {row.original.is_active ? "Faol" : "Faol emas"}
        </span>
      </div>
    ),
  },
  {
    id: "actions",
    header: () => <span className="sr-only">Amallar</span>,
    cell: ({ row }) => (
      <div className="flex justify-end">
        <UserActionsMenu user={row.original} />
      </div>
    ),
  },
]
