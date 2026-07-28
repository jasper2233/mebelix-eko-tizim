import { defineConfig } from "@hey-api/openapi-ts"

export default defineConfig({
  input: "./openapi.json",
  output: "./src/client",

  // @hey-api/schemas plugini olib tashlandi: u `src/client/schemas.gen.ts`
  // (4443 qator, 105 KB) generatsiya qilardi, lekin uni na `client/index.ts`
  // re-eksport qilardi, na biror kod import qilardi — bundle'ga ham tushmasdi.
  // Kerak bo'lsa qayta qo'shish bir qatorlik ish.
  plugins: [
    "legacy/axios",
    {
      name: "@hey-api/sdk",
      // NOTE: this doesn't allow tree-shaking
      asClass: true,
      operationId: true,
      classNameBuilder: "{{name}}Service",
      methodNameBuilder: (operation) => {
        // @ts-expect-error
        const name: string = operation.name

        // Basic camelCase conversion if needed, though usually operationIds are already good
        return name.charAt(0).toLowerCase() + name.slice(1)
      },
    },
  ],
})
