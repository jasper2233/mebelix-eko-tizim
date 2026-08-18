import { defineConfig } from "@hey-api/openapi-ts"

export default defineConfig({
  input: "./openapi.json",
  output: "./src/client",

  // @hey-api/schemas plugini olib tashlandi: u `src/client/schemas.gen.ts`
  // (4443 qator, 105 KB) generatsiya qilardi, lekin uni na `client/index.ts`
  // re-eksport qilardi, na biror kod import qilardi — bundle'ga ham tushmasdi.
  // Kerak bo'lsa qayta qo'shish bir qatorlik ish.
  plugins: [
    {
      // `legacy/axios` 0.87.0 da olib tashlangan. Zamonaviy klient o'z axios
      // instansiyasini yaratadi — interceptorlar global `axios` ga emas,
      // `client.instance` ga ulanadi (`src/main.tsx`).
      name: "@hey-api/client-axios",
      // Xato holatida throw qiladi: TanStack Query'ning isError/onError
      // zanjiri va mavjud `handleError` shu xatti-harakatga qurilgan.
      throwOnError: true,
    },
    {
      name: "@hey-api/sdk",
      // NOTE: this doesn't allow tree-shaking
      asClass: true,
      // Metod nomi backend'dagi `operation_id` dan olinadi (`read_clients` ->
      // `readClients`) — 0.99 da bu sukutdagi xatti-harakat, avvalgi qo'lda
      // yozilgan `methodNameBuilder` kerak emas.
      operationId: true,
      classNameBuilder: "{{name}}Service",
    },
  ],
})
