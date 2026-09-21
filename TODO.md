# TODO — audit natijalari

Audit bazasi: **`e234cf2`** (hisobot yozilganda HEAD `a41f76b`).
Har bir band adversarial tekshiruvdan o'tgan: mustaqil rad etuvchilar uni
yo'qqa chiqarishga urinib, uddalay olmagan. Xulq haqidagi da'volar bajarib
tasdiqlangan — dalil qatorida aynan nima yugurtirilgani turibdi.

Tuzatishlar branch + PR orqali boradi; `main` prodga avto-deploy qiladi.

| Og'irlik | Soni |   | Kategoriya | Soni |
| --- | ---: | --- | --- | ---: |
| yuqori | 1 |   | Hujjat kod bilan mos emas | 48 |
| o'rta | 30 |   | Xatolik | 14 |
| past | 50 |   | Keraksiz/yolg'on izoh | 7 |
|  |  |   | O'lik kod | 4 |
|  |  |   | Takrorlanish (DRY) | 4 |
|  |  |   | API kontrakti mos emas | 2 |
|  |  |   | O'zbekcha bo'lmagan matn | 1 |
|  |  |   | Infratuzilma (server) | 1 |

Jami: **81 ta band** (81-band audit doirasidan tashqari, 2026-09-21 da o'lchov bilan qo'shildi). Rad etilgan 11 ta topilma oxirgi bo'limda.

## Yuqori (1)

### 1. Editing the PARENT part's route never re-validates its attached children - the assembly join point silently disappears and the small part hangs forever

- **Joy:** `backend/app/api/routes/orders/matrix.py:155`
- **Turi:** Xatolik
- **Kod:** `if part.assembly_parent_id is not None and (parent_changed or edit.route_codes is not None):`

**Nega tuzatish kerak**

_check_assembly_match enforces the invariant "mayda detalning OXIRGI amali asosiy detal marshrutida ham bo'lishi shart" ONLY from the child's side: a part lands in to_check only when the part ITSELF has a parent. When the texnolog opens the Nostandart detallar tab and re-draws the route of a part that ALREADY HAS CHILDREN, nothing complains - CustomRoutes.tsx renders the 14 process buttons for such a part unconditionally (lines 219-266); only the parent SELECT is replaced by the 'Asosiy detal - ... biriktirilgan' line (lines 280-292). At scan time _close_assembly_children does "if not steps or steps[-1].post_id != post.id: continue" (backend/app/services/scanning.py:463), so the child is skipped forever; and because a joined child gets NO tail (no UPAKOVKA/TMO) it is never scanned on its o
… (qisqartirildi)

**Tekshiruv**

```
Ran the real endpoint against a throwaway Postgres 15 (docker + alembic upgrade head), calling edit_order_matrix directly (script: scratchpad/l047/scen.py). Parts A and B both custom, route [7, 11] (Rover -> G petlya o'ngdan), B attached to A; then a SECOND PATCH touching ONLY A with route_codes=[7, 8]:

$ uv run python scen.py
step1 ok; A codes: [7, 11] B codes: [7, 11] B.parent: 1
step2 ACCEPTED (no error raised)
after: A codes: [7, 8] B codes: [7, 11] B.parent_id: 1
JOIN OP 11 in A's route? False

Step 1 shows the validator does work on the child side (it accepted a matching pair); step 2 shows the same invariant is violated silently when only the parent is edited. grep -rn _check_assembl
… (qisqartirildi)
```

**Taklif**

In edit_order_matrix, when a part's own route is rebuilt (edit.route_codes is not None, plus the rebuild branch at line 151), also queue that part's live children for _check_assembly_match: select Part rows with assembly_parent_id == part.id and is_deleted == False and add them to to_check. Since to_check is already drained at the END of the batch, a PATCH that re-draws parent and child together still passes. Optionally add a warning in CustomRoutes.tsx beside the 'Asosiy detal - ... biriktirilgan' line.

**Bog'liq fayllar:** `frontend/src/components/Orders/CustomRoutes.tsx`, `backend/app/services/scanning.py`, `docs/03-backend-api.md`

<sub>ID `L047:0` · ovoz 3 · rad 0</sub>

## O'rta (29)

### 2. deploy job's 'Public smoke' curl has no --max-time: a connected-but-silent prod endpoint hangs the job and blocks the prod-deploy concurrency group

- **Joy:** `.github/workflows/ci.yml:248`
- **Turi:** Xatolik
- **Kod:** `code=$(curl -s -o /dev/null -w '%{http_code}' https://mes.mebelix.uz/api/v1/ready)`

**Nega tuzatish kerak**

This is the exact failure mode scripts/deploy.sh:60 already documents as mandatory to guard against: `# `--max-time` MAJBURIY: usiz osilgan API (TCP qabul qiladi, javob bermaydi —`. Every other curl in the repo carries a timeout (scripts/deploy.sh:66 `--connect-timeout 5 --max-time 10`, scripts/backup.sh:74 `--connect-timeout 10 --max-time 300`, .github/workflows/uptime.yml:38 `--max-time 20`). ci.yml:248 and ci.yml:250 are the only two without one. curl has no default total-transfer timeout, so a peer that completes the TCP/TLS handshake and then never sends a response (host nginx holding the connection, stalled upstream) makes curl wait forever. deploy.sh's own smoke runs against 127.0.0.1 and can pass while the public nginx/TLS path stalls, so this step is reachable. The deploy job carr
… (qisqartirildi)

**Tekshiruv**

```
Ran a Python TCP listener that accepts and never replies, then both curl forms against it:

$ python hang.py &  # listens 127.0.0.1:18771, accept() then sleep(600)
listening 18771
--- CI-style curl (ci.yml line 248, no timeouts) ---
accepted, never replying
exit=124 elapsed=15s   (124 = killed by outer timeout, i.e. curl was still hanging)
--- deploy.sh-style curl (--connect-timeout 5 --max-time 10) ---
accepted, never replying
000
exit=28 elapsed=10s   (28 = curl's own timeout)

So the CI form never returns on its own; the deploy.sh form bails at 10s.

Repo-wide curl inventory (grep -rn 'curl ' --include=*.yml --include=*.sh .):
./.github/workflows/ci.yml:248:          code=$(curl -s -o /de
… (qisqartirildi)
```

**Taklif**

Add the same guard deploy.sh uses to ci.yml:248 and :250 — `--connect-timeout 5 --max-time 15` (a healthy /ready answers far faster), and `--max-time 20` to the notify curl at ci.yml:282. Keep the `[ "$code" = "200" ]` check as is: on timeout curl prints `000`, which already fails the comparison.

**Bog'liq fayllar:** `scripts/deploy.sh`, `scripts/backup.sh`, `.github/workflows/uptime.yml`

<sub>ID `L055:0` · ovoz 3 · rad 0</sub>

### 3. edit_order_matrix: re-ticking is_custom blanket-restores ALL soft-deleted MANUAL routes and violates ix_part_route_part_seq (500, part stuck)

- **Joy:** `backend/app/api/routes/orders/matrix.py:135`
- **Turi:** Xatolik
- **Kod:** `.where(PartRoute.part_id == part.id, PartRoute.source == restore, PartRoute.is_deleted == True) # noqa: E712`

**Nega tuzatish kerak**

The is_custom toggle restores every soft-deleted PartRoute of the other source with one UPDATE. Soft-deleted MANUAL rows accumulate in two ways: (a) `_set_custom_route` soft-deletes MANUAL rows referenced by a Scan (lines 350-360) and then rebuilds new MANUAL rows starting at seq=1 (`build_manual_route(start_seq=1)`), so after a redraw/parent change two MANUAL generations share the same seq values; (b) while the part is standard, a stage toggle inserts a LIVE `source=RouteSource.MANUAL` row (line 200-211) at seq=max+1. In either case, un-ticking then re-ticking is_custom makes the restore UPDATE bring two rows with the same (part_id, seq) to `is_deleted=False`, which the partial unique index `ix_part_route_part_seq` (models/order.py:167, `postgresql_where=text("NOT is_deleted")`) rejects -
… (qisqartirildi)

**Tekshiruv**

```
sqlite simulation with the same partial unique index, replaying the statements of matrix.py verbatim.
Path A (scanned row + redraw, then flip-flop):
  after redraw: [(1, 1, 'MANUAL', 1), (2, 1, 'MANUAL', 0), (3, 2, 'MANUAL', 0), (4, 3, 'MANUAL', 0)]
  after untick custom: [(1, 1, 'MANUAL', 1), (2, 1, 'MANUAL', 1), (3, 2, 'MANUAL', 1), (4, 3, 'MANUAL', 1)]
  re-tick custom -> IntegrityError: UNIQUE constraint failed: part_route.part_id, part_route.seq
Path B (no scans: tick+draw [1,3], untick, stage-toggle adds MANUAL seq 3, re-tick):
  3 stage toggle on: [(1,1,'AUTO',1,0),(2,2,'AUTO',3,0),(3,4,'AUTO',16,0),(4,1,'MANUAL',1,1),(5,2,'MANUAL',3,1),(6,3,'MANUAL',16,1),(7,3,'MANUAL',5,0)]
  4 re-t
… (qisqartirildi)
```

**Taklif**

Do not blanket-restore. In the is_custom branch restore only the latest MANUAL generation (e.g. rows whose deleted_at equals max(deleted_at) for part_id+source) and, before restoring, hard-delete live scan-free MANUAL rows added by stage toggles (they are being replaced, like `_set_custom_route` already does); alternatively, when re-ticking is_custom, skip the restore and require/derive route_codes and rebuild through `_set_custom_route`, which already handles the scanned-row case. Whatever the choice, catch IntegrityError around the restore and return a 409/422 in Uzbek instead of 500.

**Bog'liq fayllar:** `backend/app/services/giblab/routes.py`, `backend/app/services/giblab/ingest.py`, `backend/app/models/order.py`, `backend/app/models/scan.py`

<sub>ID `L002:0` · ovoz 3 · rad 0</sub>

### 4. Parser warning tells the technologist har operatsiya bir skan talab qiladi but prisadka_passes() returns at most 1 scan regardless of XNC op count

- **Joy:** `backend/app/services/giblab/parser.py:240`
- **Turi:** Xatolik
- **Kod:** `f"skan sonini texnolog tekshirishi kerak (har operatsiya bir skan talab qiladi)."`

**Nega tuzatish kerak**

Since b26c619 (2026-09-03, one scan per instance for two-sided parts) ParsedPart.prisadka_passes() is int(any(...)) (models.py:376), i.e. 0 or 1, and ingest uses it as per_instance (ingest.py:649). The user-facing advisory for parts with more than 2 XNC ops still claims each operation requires its own scan, so the technologist is told to expect N scans where the route requires exactly one. The comment at parser.py:235 (prisadka_passes har operatsiyaga +1 beradi) and the xnc.py:336 docstring (har biri +1 skan) repeat the stale rule.

**Tekshiruv**

```
Ran: ParsedPart with 3 XncOps each having a bore -> `xnc_ops: 3 prisadka_passes(): 1`. git show b26c619 models.py: `-        return sum(1 for op in self.xnc_ops if ...)` / `+        return int(any(op.bores or op.edge_bores or op.grooves or any(op.mills) for op in self.xnc_ops))`. parser.py:235 `# bo'lishi mumkin (prisadka_passes har operatsiyaga +1 beradi), shuning uchun aytamiz.`; xnc.py:336 `prisadka_passes() N ta operatsiyani baribir to'g'ri sanaydi (har biri +1 skan).`
```

**Taklif**

Reword the advisory to the current rule, e.g. Hammasi saqlandi va bitta SCX ga birlashtirildi; PRISADKA qadami baribir bitta skan. Fix the parser.py:235 comment and the xnc.py:336 docstring to say prisadka_passes() returns 0/1.

**Bog'liq fayllar:** `backend/app/services/giblab/models.py`, `backend/app/services/giblab/xnc.py`, `backend/app/services/giblab/ingest.py`

<sub>ID `L086:1` · ovoz 3 · rad 0</sub>

### 5. ClientCombobox shows "mijoz topilmadi" when the clients request FAILS — no error state, no toast

- **Joy:** `frontend/src/components/Clients/ClientCombobox.tsx:44`
- **Turi:** Xatolik
- **Kod:** `const { data, isFetching } = useQuery({`

**Nega tuzatish kerak**

The query result is destructured without `isError`. On a failed request `data` is undefined, so `items = data?.data ?? []` is empty and `isFetching` is false, which makes the branch at line 156 render the empty state — with a search term typed it reads `"<term>" bo'yicha mijoz topilmadi`. Nothing else surfaces the failure either: the global handler `handleApiError` in frontend/src/lib/queryClient.ts:6 only reacts to HTTP 401, so a 500/timeout produces no toast at all. In the order-entry flow (AddOrder.tsx:106) the operator is told the client does not exist and is offered "Yangi mijoz qo'shish" right below — i.e. the UI actively invites creating a duplicate client on a transient backend failure. Sibling surfaces do handle this: clients.tsx:99-100 renders `<QueryError onRetry={...} />`.

**Tekshiruv**

```
Ran the real @tanstack/react-query observer with the project's own defaults (retry: 1) and a throwing queryFn, then applied the component's exact render condition:

  cd frontend && printf '...QueryObserver with queryFn that throws...' | npx esbuild --bundle --format=cjs --platform=node --outfile=.../rq.cjs && node .../rq.cjs
  {"status":"error","isFetching":false,"isError":true,"items_len":0,"empty_state_shown":true}

`empty_state_shown` is literally `items.length === 0 && !isFetching`, the condition on ClientCombobox.tsx:156. Confirmed no global toast: grep -n "onError" frontend/src/lib/queryClient.ts -> queryCache/mutationCache both use `handleApiError`, whose body is guarded by `error.re
… (qisqartirildi)
```

**Taklif**

Pull `isError` out of the useQuery result and render a distinct error line (plus a retry) before the empty-state branch, e.g. `{isError && <p ...>Mijozlar ro'yxatini yuklab bo'lmadi</p>}` and gate the `mijoz topilmadi` / `Mijozlar yo'q` texts on `!isError`.

**Bog'liq fayllar:** `frontend/src/lib/queryClient.ts`, `frontend/src/components/Orders/AddOrder.tsx`, `frontend/src/routes/_layout/clients.tsx`, `frontend/src/components/Common/QueryError.tsx`

<sub>ID `L023:0` · ovoz 3 · rad 0</sub>

### 6. Hodim yozuvi hisobdan OLDIN yaratiladi, parol kuchi esa klientda tekshirilmaydi — serverdagi 422 yetim hodim qoldiradi, qayta bosish uni IKKILANTIRADI

- **Joy:** `frontend/src/components/People/PersonDialog.tsx:226`
- **Turi:** Xatolik
- **Kod:** `const created = await EmployeesService.createEmployee({ body })`

**Nega tuzatish kerak**

Yangi tsex xodimiga shaxsiy login ochilganda mutatsiya avval `createEmployee` (commit bo'ladi, badge_id serverda generatsiya qilinadi), keyin `createUser` chaqiradi. Klient tomonda paroldan faqat `form.password.length === 0` talab qilinadi (PersonDialog.tsx:278) — kuch qoidalari (`passwordSchema`, lib/validation.ts) bu dialogda UMUMAN ishlatilmaydi, ular faqat ChangePassword.tsx da. Ya'ni admin '12345678' yozsa 'Saqlash' ochiq, `createEmployee` o'tadi, `createUser` 422 beradi. Toast esa pydantic massivini yutib yuboradi — admin nima noto'g'ri ekanini bilmaydi. Dialog ochiq qoladi, `person` prop hamon null, shuning uchun parolni tuzatib qayta bosilganda `employeeId` yana null bo'lib `createEmployee` IKKINCHI marta chaqiriladi: ro'yxatda ikkita bir xil hodim, birinchisi hisobsiz, lekin beyji
… (qisqartirildi)

**Tekshiruv**

```
1) Klient darvozasi: `grep -n 'form.password.length === 0' frontend/src/components/People/PersonDialog.tsx` -> 278; `grep -rn 'passwordSchema' frontend/src` -> faqat ChangePassword.tsx:18,26 va validation.ts:17 (PersonDialog YO'Q).
2) Server rad etadi (bajarildi):
   $ uv run --project backend python -c "from app.schemas.users import UserCreate; ...UserCreate(...password='12345678', role='arrachi')"
   createUser 422: ["Value error, Parolda kamida bitta kichik harf bo'lsin"]
3) Toast matni: frontend/src/utils.ts:75-79 — `if (Array.isArray(detail) && detail.length > 0) return plain("XATO", "Kiritilgan ma'lumot noto'g'ri — tekshirib qayta yuboring")`.
4) Qayta urinish oqibati — mutationFn (196
… (qisqartirildi)
```

**Taklif**

(a) `missing` zanjiriga parol kuchini qo'sh: `(kind === "ofis" || withLogin) && !person?.user` holatida `passwordSchema.safeParse(form.password)` xatosini ko'rsat — mirror allaqachon `lib/validation.ts` da bor, server bilan bir xil. Shunda 422 ning asosiy sababi umuman serverga bormaydi. (b) Yaratilgan hodim id'sini `useRef` da saqla va mutationFn boshida `person?.employee ?? createdRef.current` dan ol — qisman bajarilgan urinishdan keyin qayta bosish `createEmployee` emas, `updateEmployee` qilsin.

**Bog'liq fayllar:** `frontend/src/lib/validation.ts`, `frontend/src/utils.ts`, `backend/app/schemas/users.py`, `backend/app/api/routes/employees.py`

<sub>ID `L026:0` · ovoz 3 · rad 0</sub>

### 7. "Boshqa" lavozimidagi hodimni tahrirlash postlarini o'chiradi — `postsFor` saqlagan postlarni payload tashlab yuboradi

- **Joy:** `frontend/src/components/People/PersonDialog.tsx:216`
- **Turi:** Xatolik
- **Kod:** `assigned_post_ids: kind === "boshqa" ? [] : form.posts,`

**Nega tuzatish kerak**

`postsFor` (PersonDialog.tsx:87) ataylab mavjud postlarni qaytaradi — izohi: "Katalogda yo'q lavozim (\"Boshqa\", eski erkin matn) — mavjud postlar SAQLANADI: aks holda shunday odamni tahrirlash uni postsiz qoldirardi." Bu branch e3fcaf3 ("undo the five cleanups that changed behaviour") da ataylab QAYTARILGAN, va docs/06-frontend-components.md:38 ham shu qoidani yozadi. Lekin mutationFn body'si kind==='boshqa' bo'lganda form.posts ni butunlay e'tiborsiz qoldirib [] yuboradi. Natija: `position` matni katalog yorlig'iga mos kelmaydigan (eski erkin matnli) va posti bor hodimni tahrirlaganda — hatto faqat telefonini to'g'rilaganda ham — `assigned_post_ids` bo'shaydi. Shundan keyin uning beyjigi ishlamaydi: backend/app/services/scanning.py:196 `if post.id not in employee.assigned_post_ids:` ->
… (qisqartirildi)

**Tekshiruv**

```
PersonDialog.tsx dagi HAQIQIY `positionOf`/`postsFor` funksiyalari esbuild bilan bundle qilinib node'da ishga tushirildi (faqat `function` -> `export function` qilingan nusxa; tanalari so'zma-so'z):
  eski erkin matnli hodim: position="Haydovchi", posts=[7] (ARRA)
  $ npx esbuild src/_probe_entry.tsx --bundle --format=esm --packages=external --alias:@=./src ... && node _probe_out.mjs
  initialPosition = "Boshqa"
  form.posts (postsFor fallback) = [7]
  payload assigned_post_ids = []
Ya'ni postsFor postni saqlaydi, payload esa uni tashlaydi.

Quote'lar grep -F bilan tasdiqlangan:
  PersonDialog.tsx:216: `        assigned_post_ids: kind === "boshqa" ? [] : form.posts,`
  PersonDialog.tsx:87:
… (qisqartirildi)
```

**Taklif**

Saqlash faqat ochilishdagi lavozim "Boshqa" bo'lganda bo'lishi kerak — chunki tsex lavozimidan "Boshqa" ga QO'LDA o'tilganda form.posts da eski tsex posti qolib ketadi (line 216 aynan shundan himoya qilyapti). Bitta joyda hal qilinsin, ikki joyda emas: `pickPosition` da "Boshqa" tanlansa postlarni tozalash (`postsFor(label, posts, label === initialPosition ? (person?.posts ?? []) : [])`), payload esa shartsiz `assigned_post_ids: form.posts` yuborsin. Aks holda (agar "Boshqa" hodimda post BO'LMASLIGI kerak deb qaror qilinsa) — postsFor:85-87 dagi fallback branch va izohi hamda docs/06-frontend-
… (qisqartirildi)

**Bog'liq fayllar:** `docs/06-frontend-components.md`, `backend/app/services/scanning.py`, `frontend/src/routes/_layout/employees.tsx`

<sub>ID `L048:0` · ovoz 3 · rad 0</sub>

### 8. Faollik ping'i xato bo'lsa 60 s throttle butunlay yo'qoladi — har kiritish hodisasi yangi POST /users/me/activity (o'lchandi: 30 keydown -> 30 so'rov)

- **Joy:** `frontend/src/hooks/useIdleLogout.ts:86`
- **Turi:** Xatolik
- **Kod:** `lastPingRef.current = 0 // tarmoq uzildi — keyingi harakatda qayta urinamiz`

**Nega tuzatish kerak**

`lastPingRef` throttle darvozasi: `if (now - lastPingRef.current > PING_MS)`. Xatoda u 0 ga qaytariladi, ya'ni darvoza OCHIQ qoladi va KEYINGI HAR BIR kiritish hodisasi (pointerdown/keydown/wheel/touchstart) yangi so'rov yuboradi — backoff yo'q. Tez yiqiladigan xatolarda (tsex Wi-Fi uzilishi = ERR_NETWORK, 5xx, refresh'siz 401) bu kiritish tezligiga teng so'rov oqimini beradi: terminalda klaviatura/g'ildirak burchagi soniyasiga o'nlab XHR. Bu hujjatda YOZILGAN shartnomani buzadi (docs/03 va docs/05 — «ko'pi bilan 60 s da bir marta»). Muvaffaqiyatli so'rovda muammo yo'q (o'lchandi: 1 ta so'rov).

**Tekshiruv**

```
Haqiqiy `useIdleLogout.ts` fayli Node 24 ning TS type-stripping'i bilan SHU HOLICHA ishga tushirildi (react / @tanstack/react-query / @/client / @/hooks/useAuth — `node:module` resolve-hook orqali stub'larga bog'landi), soxta window+localStorage berildi, effektlar ishga tushirilib 30 ta `keydown` hodisasi yuborildi:

  $ node --import ./register.mjs harness2.mjs up
  mode=network UP  30 keydown in 412 ms -> 1 POST /users/me/activity
  $ node --import ./register.mjs harness2.mjs down
  mode=network DOWN  30 keydown in 398 ms -> 30 POST /users/me/activity

Hujjatdagi shartnoma (grep -F bilan tasdiqlangan):
  docs/03-backend-api.md:208  "frontend daqiqasiga ko'pi bilan bir marta yuboradi"
  doc
… (qisqartirildi)
```

**Taklif**

Throttle'ni nolga tushirmasdan QISQARTIR: `.catch(() => { lastPingRef.current = now - PING_MS + RETRY_MS })` (masalan `RETRY_MS = 5_000`) — tarmoq qaytganda ping 5 soniyada qayta urinadi, lekin har bosishda emas. Shunda hujjatdagi «ko'pi bilan daqiqasiga bir marta» chegarasi ham (kamida xato holatida cheklangan tezlik bilan) saqlanadi; aks holda docs/03:208 va docs/05:321 ni haqiqiy xulqqa moslash kerak.

**Bog'liq fayllar:** `docs/03-backend-api.md`, `docs/05-frontend-app.md`, `backend/app/api/routes/users.py`

<sub>ID `L031:0` · ovoz 3 · rad 0</sub>

### 9. PersonDialog creates users without running passwordSchema — the zod mirror exists but the only user-creation form bypasses it

- **Joy:** `frontend/src/components/People/PersonDialog.tsx:278`
- **Turi:** API kontrakti mos emas
- **Kod:** `form.password.length === 0`

**Nega tuzatish kerak**

validation.ts:17 exports `passwordSchema`, documented as "Mirrors `validate_password_strength` on the server", but its only consumer is ChangePassword.tsx. PersonDialog — the sole place a user account is created — checks nothing but that the password is non-empty, then posts it straight to UsersService.createUser. Any password failing validate_password_strength comes back as a 422 with a list `detail`, which utils.ts turns into the generic "Kiritilgan ma'lumot noto'g'ri — tekshirib qayta yuboring" — so the Uzbek per-rule messages the backend docstring says are mirrored on the client (users.py:24-25) never reach the admin from this form. Same aggravating factor as L092-1: in the tsex branch the employee row is already committed at line 226 before createUser throws, so each retry leaves anot
… (qisqartirildi)

**Tekshiruv**

```
Ran the real schema with a password the form happily submits:

$ cd backend && uv run python - <<'PY'
from app.schemas.users import UserCreate ...
weak password    -> 422 detail is a LIST of 1: loc=('password',) msg="Value error, Parolda kamida bitta kichik harf bo'lsin"

The mirror exists and is used exactly once:
  $ grep -rn "passwordSchema" frontend/src --include=*.ts --include=*.tsx
  frontend/src/components/UserSettings/ChangePassword.tsx:18:import { passwordSchema } from "@/lib/validation"
  frontend/src/components/UserSettings/ChangePassword.tsx:26:    new_password: passwordSchema,
  frontend/src/lib/validation.ts:17:export const passwordSchema = z
(PersonDialog.tsx:41 imports only `
… (qisqartirildi)
```

**Taklif**

In PersonDialog, replace the `form.password.length === 0` test in the `missing` chain with `passwordSchema.safeParse(form.password)` (applied only when a password is actually being set — i.e. keep the existing "bo'sh — o'zgarmaydi" edit case) and surface `error.issues[0].message`, which is already Uzbek and already matches the on-screen hint.

**Bog'liq fayllar:** `frontend/src/lib/validation.ts`, `backend/app/schemas/users.py`, `frontend/src/utils.ts`

<sub>ID `L092:1` · ovoz 3 · rad 0</sub>

### 10. Username constraints (min 2, ^[a-z0-9]+$) are enforced only by pydantic — validation.ts has no mirror, so a bad login returns a generic 422 toast

- **Joy:** `frontend/src/lib/validation.ts:5`
- **Turi:** API kontrakti mos emas
- **Kod:** `// Mirror the limits enforced by the backend (see `backend/app/schemas/users.py`).`

**Nega tuzatish kerak**

validation.ts declares itself the mirror of backend/app/schemas/users.py and mirrors exactly two limits (PASSWORD_MIN_LENGTH, NAME_MAX_LENGTH). The third write-side constraint, _USERNAME_FIELD (min_length=2, max_length=20, pattern ^[a-z0-9]+$), has no zod counterpart anywhere in hand-written frontend code. The only user-creation form, PersonDialog's "Login" field, guards nothing but maxLength={20}; its hint text says the rule in prose but nothing enforces it. Typing "Sherzod", "a" or "a.b" produces a pydantic 422 whose `detail` is a LIST, and utils.ts:75-79 collapses every list `detail` into the generic "Kiritilgan ma'lumot noto'g'ri — tekshirib qayta yuboring" — the admin is never told WHICH field or WHY. Worse, in the tsex branch createEmployee (PersonDialog.tsx:226) has already committe
… (qisqartirildi)

**Tekshiruv**

```
Ran the real schema against the exact strings the Login input accepts:

$ cd backend && uv run python - <<'PY'
from app.schemas.users import UserCreate ...

uppercase login  -> 422 detail is a LIST of 1: loc=('username',) msg="String should match pattern '^[a-z0-9]+$'"
one-char login   -> 422 detail is a LIST of 1: loc=('username',) msg='String should have at least 2 characters'
dot in login     -> 422 detail is a LIST of 1: loc=('username',) msg="String should match pattern '^[a-z0-9]+$'"

Backend rule, verbatim (backend/app/schemas/users.py:59):
  _USERNAME_FIELD = Field(min_length=2, max_length=20, pattern=r"^[a-z0-9]+$", examples=["userson"], default=None)

No mirror in the frontend:
  $
… (qisqartirildi)
```

**Taklif**

Add a `usernameSchema` to frontend/src/lib/validation.ts mirroring _USERNAME_FIELD — `z.string().trim().min(2, ...).max(20, ...).regex(/^[a-z0-9]+$/, { message: "Login faqat kichik lotin harflari va raqamlardan iborat bo'lsin" })`, made optional so the empty "derive from phone" case still works — and wire it into PersonDialog's `missing` chain so the submit button explains the problem instead of the server returning an anonymous 422.

**Bog'liq fayllar:** `backend/app/schemas/users.py`, `frontend/src/components/People/PersonDialog.tsx`, `frontend/src/utils.ts`

<sub>ID `L092:0` · ovoz 1 · rad 0</sub>

### 11. docs/01 section 1/4.2 counts stale: says 18 routers / 19 models / 12 protected MES routers, code has 20 / 23 / 14

- **Joy:** `docs/01-architecture.md:8`
- **Turi:** Hujjat kod bilan mos emas
- **Kod:** `qurilgan: `/v1` agregatorida **18 ta router** (health, login, logout, users,`

**Nega tuzatish kerak**

Since 2026-09-13/18 (commits f98fd07, 71ff637) the v1 aggregator also includes downtimes_router and settings_router (routes/__init__.py:42,44), and models/__init__.py exports AndonEvent, Downtime, DowntimeReason, SystemSetting. docs/01 line 8 says 18 routers, line 10 says 19 ORM models, line 249 says 12 MES routers behind get_current_user. Actual: 20 routers, 23 models, 14 protected MES routers. docs/03-backend-api.md (lines 108/110) already lists the two new routers, so docs/01 is the wrong side. docs/01 was last touched 2026-09-16, after the settings/andon models but before downtimes.

**Tekshiruv**

```
grep -n include_router backend/app/api/routes/__init__.py -> 20 include_router lines: health, login, logout, users, clients, employees, machines, posts, orders, pachka, tmo, audit, terminal, downtimes, scans, settings, tablo, reports, bridge_agents, ws (14 with dependencies=_protected after logout/users). grep class ...(BaseModel) backend/app/models/*.py -> 23 classes incl. AndonEvent, Downtime, DowntimeReason, SystemSetting. git log --diff-filter=A: models/andon.py+setting.py 2026-09-13 (f98fd07), routes/downtimes.py 2026-09-18 (71ff637); docs/01 last modified 2026-09-16 16:24.
```

**Taklif**

Update docs/01 lines 8-13 to 20 routers (add downtimes, settings), 23 ORM models (add AndonEvent, Downtime/DowntimeReason, SystemSetting) and line 249 to 14 protected MES routers; keep in sync with the router tree in docs/03.

**Bog'liq fayllar:** `backend/app/api/routes/__init__.py`, `backend/app/models/__init__.py`, `docs/03-backend-api.md`

<sub>ID `L077:0` · ovoz 2 · rad 0</sub>

### 12. Label route line no longer renders `Marshrut: 7/11/8`: code draws post names joined by a middle dot, tail codes dropped (stale in docs 01/07/09/10)

- **Joy:** `docs/01-architecture.md:416`
- **Turi:** Hujjat kod bilan mos emas
- **Kod:** `ikonkasi, **marshrut qatori** (`Marshrut: 7/11/8` — jarayon kodlari `seq``

**Nega tuzatish kerak**

Commit 1097dec (2026-09-04, feat(labels): shop-floor readable layout) changed render_label_png: route codes are mapped through PROCESS_POSTS to post names, TAIL_CODES (15,16) are skipped, consecutive equal posts collapse, the list is joined with a middle dot, wrapped at 43 mm and may move to y=41.0 with 3 lines. There is no Marshrut: prefix and no numeric codes. docs/01:416, docs/07:324, docs/09:300 and docs/10:350 still describe `Marshrut: 7/11/8`; the LabelData field comment at labels.py:40 (7/11/8) is stale too. docs/README claims last sync 2026-09-05, i.e. after the change.

**Tekshiruv**

```
RAN: monkeypatched PIL ImageDraw.text and called labels.render_label_png(LabelData(..., route_codes=[7,11,8,15,16])). Output: contains Marshrut: or 7/11/8? -> False ; strings drawn at y 40..48 mm: [(41.5, ROVER·STOLYARKA·BOYOQ)]. PROCESS_POSTS: {7:ROVER, 11:STOLYARKA, 8:BOYOQ, 15:UPAKOVKA, 16:TMO}; TAIL_CODES=(15,16). labels.py:321 comment: Marshrut — POST nomlari (raqamli jarayon kodlari tsexchiga ma'nosiz); labels.py:331 post = str(PROCESS_POSTS.get(code, code)). git log -1 1097dec -> 2026-09-04 15:02.
```

**Taklif**

Rewrite the route-line description in docs/01:416-418 (and docs/07:324, docs/09:300, docs/10:350): post names in seq order joined by a middle dot (e.g. ROVER·STOLYARKA·BOYOQ), tail UPAKOVKA/TMO omitted, consecutive duplicates collapsed, wraps to 2-3 lines at 43 mm (y=41.5 or 41.0). Also fix the stale comment at backend/app/services/labels.py:40.

**Bog'liq fayllar:** `backend/app/services/labels.py`, `docs/07-infra-devops.md`, `docs/09-mes-domain.md`, `docs/10-giblab-reference.md`

<sub>ID `L077:1` · ovoz 2 · rad 0</sub>

### 13. docs/02 still documents the startup probes (_retry_async, check_*_connection) under setup.py; commit 4dda538 moved them to health.py and worker.py imports from…

- **Joy:** `docs/02-backend-core.md:194`
- **Turi:** Hujjat kod bilan mos emas
- **Kod:** `- `_retry_async(label, fn)` — startup probe'lar uchun retry helper: `STARTUP_RETRY_MAX_ATTEMPTS` (5) marta urinadi, orasida `STARTUP_RETRY_DELAY_SECONDS` (2s) kutadi; `CancelledError`/`KeyboardInterr…`

**Nega tuzatish kerak**

docs/02 is the hand-maintained primary source (CLAUDE.md). Its setup.py section (lines 194-196) lists _retry_async, check_database_connection, check_redis_connection as setup.py functions; its worker.py section (line 247) says worker depends on setup.py (check_database_connection); its db.py section (line 106) says setup.py imports the engine for the startup probe; setup.py Bog'lanishlar (line 213) lists db.py. On disk all four probe functions live in backend/app/core/health.py (lines 25-103); setup.py:17 imports them from app.core.health; worker.py:8 imports check_database_connection from app.core.health; setup.py imports nothing from app.core.db. The health.py section of docs/02 (lines 126-133) describes only check_database_health/check_redis_health and omits the probes entirely, so a re
… (qisqartirildi)

**Tekshiruv**

```
grep -rnE _retry_async|check_database_connection|check_redis_connection backend/app -> only backend/app/core/health.py:54,76,90 define them; backend/app/core/setup.py:17 from app.core.health import check_database_connection, check_redis_connection; backend/app/core/worker.py:8 from app.core.health import check_database_connection. git show 4dda538 -- backend/app/core/setup.py -> +from app.core.health import ..., -async def _retry_async, -async def check_database_connection, -async def check_redis_connection (2026-08-29). git show 4dda538 --stat touches health.py/setup.py/worker.py/routes/health.py but NOT docs/02-backend-core.md. grep -nF on docs/02 confirms lines 194, 195, 196, 247 still re
… (qisqartirildi)
```

**Taklif**

In docs/02-backend-core.md: move the three bullets at lines 194-196 (and add redis_clients()) from the setup.py section into the health.py section (line 126 ff.), noting they are called by lifespan (setup.py) and by the arq startup (worker.py); change line 247 setup.py (check_database_connection) -> health.py (check_database_connection); in the db.py section (line 106) replace setup.py with health.py as the module importing the engine for the probe; drop db.py from setup.py Bog'lanishlar (line 213) and add health.py; line 360 (queue.py) health.py va setup.py ping uchun ishlatadi -> only health
… (qisqartirildi)

**Bog'liq fayllar:** `backend/app/core/health.py`, `backend/app/core/setup.py`, `backend/app/core/worker.py`, `docs/02-backend-core.md`

<sub>ID `L006:0` · ovoz 2 · rad 0</sub>

### 14. docs/02 still documents the startup probes (_retry_async, check_database_connection, check_redis_connection) as living in core/setup.py — they moved to core/he…

- **Joy:** `docs/02-backend-core.md:194`
- **Turi:** Hujjat kod bilan mos emas
- **Kod:** `- `_retry_async(label, fn)` — startup probe'lar uchun retry helper: `STARTUP_RETRY_MAX_ATTEMPTS` (5) marta urinadi, orasida `STARTUP_RETRY_DELAY_SECONDS` (2s) kutadi; `CancelledError`/`KeyboardInterr…`

**Nega tuzatish kerak**

The `## backend/app/core/setup.py` section (docs/02-backend-core.md:188-213) is the hand-maintained map of that module, and four separate claims in it are now false. (1) Lines 194-196 list `_retry_async`, `check_database_connection` and `check_redis_connection` as setup.py's "Muhim funksiyalar"; all three are defined in `backend/app/core/health.py` (:54, :75, :89) and setup.py merely imports two of them. (2) Line 190 calls setup.py "core'ning eng katta fayli" — it is 131 lines, behind config.py (174) and ws.py (133). (3) Line 213 lists `db.py` among setup.py's dependencies — setup.py has no `db` import; and it omits `health.py`, which setup.py actually imports. (4) Line 213 and line 247 both claim worker.py uses setup.py ("`main.py` va `worker.py` bu modulni ishlatadi", "`setup.py` (`check
… (qisqartirildi)

**Tekshiruv**

```
$ grep -Fn -e "**Maqsadi:** core'ning eng katta fayli" -e "- \`_retry_async(label, fn)\` — startup probe'lar uchun retry helper" -e "- \`check_database_connection()\` — engine orqali \`SELECT 1\` probe (retry bilan)." -e "\`setup.py\` (\`check_database_connection\`)" docs/02-backend-core.md
190:**Maqsadi:** core'ning eng katta fayli — application factory va startup/shutdown hayot sikli. FastAPI ilovasini metadata, middleware, metrics va env-shartli docs bilan yig'adi.
194:- `_retry_async(label, fn)` — startup probe'lar uchun retry helper: `STARTUP_RETRY_MAX_ATTEMPTS` (5) marta urinadi, orasida `STARTUP_RETRY_DELAY_SECONDS` (2s) kutadi; `CancelledError`/`KeyboardInterrupt` darhol yuqoriga uza
… (qisqartirildi)
```

**Taklif**

In docs/02-backend-core.md: move the `_retry_async` / `check_database_connection` / `check_redis_connection` bullets (194-196) out of the setup.py section into the `## backend/app/core/health.py` section (126-133), which currently documents only `check_database_health`/`check_redis_health` and omits `redis_clients()` too; drop "core'ning eng katta fayli" from line 190; on line 213 replace `db.py` with `health.py` (`check_database_connection`, `check_redis_connection`) and drop "va `worker.py`" from "`main.py` va `worker.py` bu modulni ishlatadi"; on line 247 change worker.py's dependency from
… (qisqartirildi)

**Bog'liq fayllar:** `backend/app/core/setup.py`, `backend/app/core/health.py`, `backend/app/core/worker.py`

<sub>ID `L039:0` · ovoz 2 · rad 0 · 1 ta takror topilma birlashtirildi</sub>

### 15. docs/02 says print tasks take agent_id=None and print_queue_key falls back to the shared key; code makes agent_id required and never falls back

- **Joy:** `docs/02-backend-core.md:276`
- **Turi:** Hujjat kod bilan mos emas
- **Kod:** `- `print_label(ctx, instance_id, agent_id=None)` — yorliq chiqarish vazifasi.`

**Nega tuzatish kerak**

Doc lines 276, 289, 291, 295 give every print task the signature (ctx, ID, agent_id=None), and lines 251-252 say print_queue_key(agent_id) returns the common key when agent_id is falsy. In code all four tasks declare agent_id: int with no default (tasks/__init__.py:180,196,225,253) and print_queue_key unconditionally returns the per-agent key (line 65); its docstring (lines 60-63) explicitly says the default was REMOVED so a caller that forgets the agent gets a TypeError. The doc contradicts itself: line 272 says the shared key is no longer used. A reader trusting the documented signature could enqueue print_label with two args and get a TypeError in the worker.

**Tekshiruv**

```
AST dump of backend/app/tasks/__init__.py: print_label [ctx, instance_id, agent_id] defaults: [] ; print_pachka_label defaults: [] ; print_waste_label defaults: [] ; print_badge defaults: [] ; print_queue_key body: return f'{PRINT_QUEUE_KEY}:{agent_id}'. grep -F doc line 252: manzilli kalitni beradi: agent_id bo'lsa mes:print:queue:{agent_id}, bo'lmasa umumiy kalit. ; code line 65: return f"{PRINT_QUEUE_KEY}:{agent_id}"
```

**Taklif**

Change the four task signatures in the doc to (ctx, ID, agent_id) (required) and rewrite lines 251-252: print_queue_key(agent_id) -> mes:print:queue:{agent_id}; agent_id majburiy, umumiy kalitga fallback yo'q (unutgan chaqiruvchi TypeError oladi). Also mention the shared _enqueue() helper (skip/queued/lost).

**Bog'liq fayllar:** `backend/app/tasks/__init__.py`

<sub>ID `L078:1` · ovoz 2 · rad 0</sub>

### 16. docs/07 §prestart.sh still calls `alembic upgrade head` unconditional ("shartsiz") after SKIP_MIGRATIONS made it conditional

- **Joy:** `docs/07-infra-devops.md:205`
- **Turi:** Hujjat kod bilan mos emas
- **Kod:** `Uch qadam: `python -m alembic upgrade head` (shartsiz — WORKDIR `/app/backend`, `alembic.ini` shu yerda; yo'q bo'lsa start ataylab yiqiladi)`

**Nega tuzatish kerak**

The section that documents scripts/prestart.sh states the migration step is unconditional. Since 20664eb it is guarded by SKIP_MIGRATIONS, which deploy.sh sets to 1 on every auto-rollback (scripts/deploy.sh:137) and docker-compose.prod.yml:82 passes through. The same doc file contradicts itself at line 217, which describes exactly that skip. An operator reading the prestart section during an incident concludes the stable container it just brought up has run the migrations — it has not, and the schema is deliberately left at the new revision. The word 'shartsiz' is the only part of that sentence that is false; the rest (WORKDIR/alembic.ini/hard failure) is still accurate.

**Tekshiruv**

```
Verbatim code guard: `grep -nF 'if [ "${SKIP_MIGRATIONS:-0}" = "1" ]; then' scripts/prestart.sh` -> `15:if [ "${SKIP_MIGRATIONS:-0}" = "1" ]; then`.
Ran the real script with a stubbed `python` on PATH (scratchpad/stub/python echoes its args), both modes:
$ PATH="$PWD/stub:$PATH" bash scripts/prestart.sh
Starting prestart script...
Running database migrations...
PYTHON CALLED: -m alembic upgrade head
Creating first superuser...
PYTHON CALLED: -m app.commands.create_first_superuser
Seeding defaults...
PYTHON CALLED: -m app.commands.seed_defaults
Pre-start script finished successfully.
$ PATH="$PWD/stub:$PATH" SKIP_MIGRATIONS=1 bash scripts/prestart.sh
Starting prestart script...
Running databa
… (qisqartirildi)
```

**Taklif**

In docs/07-infra-devops.md:205 replace `(shartsiz — WORKDIR ...)` with a wording that names the one exception, e.g. `(SKIP_MIGRATIONS=1 bo'lmasa — WORKDIR /app/backend, alembic.ini shu yerda; yo'q bo'lsa start ataylab yiqiladi; SKIP_MIGRATIONS ni faqat deploy.sh rollback'i beradi, ¶Rollback va DB)`, so the section agrees with line 217 and with scripts/prestart.sh:15.

**Bog'liq fayllar:** `scripts/prestart.sh`, `scripts/deploy.sh`, `docker-compose.prod.yml`

<sub>ID `L076:0` · ovoz 2 · rad 0</sub>

### 17. docs/07 says backup.sh excludes uploads/agent from the uploads tarball; the --exclude was removed in 97e7beb

- **Joy:** `docs/07-infra-devops.md:225`
- **Turi:** Hujjat kod bilan mos emas
- **Kod:** ``api` konteyneri ichidan `tar -cz -C /app/backend uploads`, `--exclude='uploads/agent'` bilan`

**Nega tuzatish kerak**

The doc describes a tar exclude (and a 19 MB / eightfold-bloat rationale) that no longer exists in scripts/backup.sh. Anyone reasoning about backup size or restore contents from the doc gets the wrong picture; the code was deliberately changed (commit message: 'the directory does not exist on the server (checked)') and the doc was not updated in that commit.

**Tekshiruv**

```
grep -n exclude scripts/backup.sh -> (no output). Actual line: scripts/backup.sh:98 `    tar -cz -C /app/backend uploads 2>/dev/null |`. git log -S"uploads/agent" -- scripts/backup.sh -> 97e7beb (2026-08-29) 'chore(infra): drop dead directives, guards and ignore rules', diff shows `-    tar -cz -C /app/backend --exclude='uploads/agent' uploads 2>/dev/null |` -> `+    tar -cz -C /app/backend uploads 2>/dev/null |`. git show 97e7beb --stat -- docs -> empty (doc not touched).
```

**Taklif**

Rewrite docs/07:225 to match the script: the uploads backup is `tar -cz -C /app/backend uploads` with no exclude; drop or move the `agent/` history note into a one-line past-tense remark (the old exe dir was removed from the server, so no exclude is needed).

**Bog'liq fayllar:** `scripts/backup.sh`

<sub>ID `L083:0` · ovoz 2 · rad 0</sub>

### 18. docs/07 documents `render_label_png(d, scale=1)` and `width=max(2, scale)`; the `scale` parameter was removed from labels.py in 4dda538

- **Joy:** `docs/07-infra-devops.md:319`
- **Turi:** Hujjat kod bilan mos emas
- **Kod:** `| `render_label_png(d, scale=1)` |`

**Nega tuzatish kerak**

The documented function signature does not exist: `render_label_png` takes only `d`, and the word `scale` does not appear anywhere in backend/app/services/labels.py. Line 326 repeats the stale detail ("barcha chiziqlar `width=max(2, scale)`") as a 'hard rule baked into the code'. docs/09-mes-domain.md carries the identical two stale statements, so the drift is in both primary docs.

**Tekshiruv**

```
grep -n scale backend/app/services/labels.py -> (no output). labels.py:218 `def render_label_png(d: LabelData) -> bytes:  # noqa: C901 — chiziqli layout kodi`. Line widths are literal: labels.py:293 `width=2`, :422 `outline="black", width=2`. git show 4dda538 -- backend/app/services/labels.py: `-def render_label_png(d: LabelData, scale: int = 1) -> bytes:`, `-    mm = 8 * scale  # px per mm`, `-            width=max(2, scale),`. Cross-file: docs/09-mes-domain.md:291 `**`render_label_png(d, scale=1)` — asosiy maket**`, :311 `Chiziqlar `width=max(2, scale)` — GDI kichraytirishda 1 px chiziq yo'qoladi.`
```

**Taklif**

In docs/07:319 write `render_label_png(d)`; in docs/07:326 replace `width=max(2, scale)` with the literal `width=2` rule. Apply the same two edits to docs/09-mes-domain.md:291 and :311.

**Bog'liq fayllar:** `backend/app/services/labels.py`, `docs/09-mes-domain.md`

<sub>ID `L083:2` · ovoz 2 · rad 0</sub>

### 19. docs/08 bridge-agent section says FIVE runtime packages and its table omits pyserial, which agent.py imports and both pip install lines include since 079993d (…

- **Joy:** `docs/08-packages.md:104`
- **Turi:** Hujjat kod bilan mos emas
- **Kod:** `Beshta runtime paket agent `mebelix-agent.exe` ichiga PyInstaller bilan yig'iladi`

**Nega tuzatish kerak**

The table at lines 106-112 lists websockets/pywin32/pillow/pynput/pystray only. `pyserial` (import serial in _andon_loop/start_andon) is a sixth optional runtime package; docs/08 itself contradicts this at line 177 (lists `pyserial`), as do docs/07:399, bridge-agent/README.md:123 and ci.yml:165. The same paragraph says versions are unpinned; the pip line now pins `pyinstaller==6.22.2` (6c63e84) — still true for the runtime packages but the CI line quoted in the doc no longer matches.

**Tekshiruv**

```
grep -nE 'import serial' bridge-agent/agent.py -> 1502:    import serial / 1503:    from serial.tools import list_ports / 1542:        import serial  # noqa: F401
.github/workflows/ci.yml:165: pip install "websockets>=14" pywin32 pillow pynput pystray pyserial "pyinstaller==6.22.2"
bridge-agent/README.md:123: (identical line)
docs/07-infra-devops.md:399: `pyserial` ham shunday — usiz andon (Pico) qismi jimgina o'chadi (`start_andon`)
docs/08-packages.md:177 already says: `websockets` (>=14) / `pywin32` / `pillow` / `pynput` / `pystray` / `pyserial`
```

**Taklif**

Change 'Beshta' to 'Oltita', add a `pyserial` row: `_andon_loop()`/`start_andon()` — Pico andon over USB COM (`serial`, `serial.tools.list_ports`); optional, ImportError silently disables andon. Note that `pyinstaller` is pinned to 6.22.2 in the pip line (6c63e84).

**Bog'liq fayllar:** `bridge-agent/agent.py`, `bridge-agent/README.md`, `.github/workflows/ci.yml`, `docs/07-infra-devops.md`

<sub>ID `L084:2` · ovoz 2 · rad 0 · 2 ta takror topilma birlashtirildi</sub>

### 20. docs/08 still documents the removed shared print-queue fallback; the code makes agent_id mandatory and docs/07 states the opposite

- **Joy:** `docs/08-packages.md:72`
- **Turi:** Hujjat kod bilan mos emas
- **Kod:** ``agent_id` berilmasa umumiy `mes:print:queue``

**Nega tuzatish kerak**

No code path can produce the un-addressed key mes:print:queue. print_queue_key(agent_id: int) has no default, all four print tasks take agent_id: int as a required parameter, and ws.py never reads the bare key. docs/08 therefore documents exactly the defect the code was changed to remove (a label queued on a shared list and pulled by whichever printer connected first, i.e. the receipt coming out at the wrong workstation), and it contradicts docs/07-infra-devops.md:267, which says the bare key is neither read nor written any more. A reader of docs/08 would believe omitting the agent is a supported, merely degraded mode.

**Tekshiruv**

```
grep -F on docs/08-packages.md for the quoted clause -> 1 hit (line 72).
docs/07-infra-devops.md:267 verbatim (grep -F, 1 hit):
  `PRINT_QUEUE_KEY = "mes:print:queue"` esa endi o'qilmaydi ham, yozilmaydi ham

RAN against the real module:
  print_queue_key sig: (agent_id: int) -> str
  print_label (ctx: dict[str, typing.Any], instance_id: int, agent_id: int) -> str
  print_pachka_label (ctx: dict[str, typing.Any], pachka_id: int, agent_id: int) -> str
  print_waste_label (ctx: dict[str, typing.Any], waste_id: int, agent_id: int) -> str
  print_badge (ctx: dict[str, typing.Any], employee_id: int, agent_id: int) -> str
  TypeError: print_queue_key() missing 1 required positional argument: 'agen
… (qisqartirildi)
```

**Taklif**

In docs/08-packages.md:72 drop the clause that starts with `agent_id` berilmasa and state that agent_id is mandatory (a caller that omits it gets a TypeError), matching docs/07-infra-devops.md:267 and the print_queue_key docstring.

**Bog'liq fayllar:** `backend/app/tasks/__init__.py`, `docs/07-infra-devops.md`, `backend/app/api/routes/ws.py`

<sub>ID `L072:1` · ovoz 2 · rad 0</sub>

### 21. docs/08 says backend/Dockerfile runs uv sync WITHOUT --no-dev and the flag is unused in the repo; Dockerfile:16 has used --no-dev since 14f60ce (2026-09-02)

- **Joy:** `docs/08-packages.md:74`
- **Turi:** Hujjat kod bilan mos emas
- **Kod:** `ya'ni `--no-dev` siz — repoda bu bayroq umuman ishlatilmaydi`

**Nega tuzatish kerak**

The paragraph's whole argument (websockets was moved to main deps as a precaution against someone adding --no-dev) is now inverted: --no-dev IS in the prod build, so websockets in main `dependencies` is load-bearing, not precautionary. docs/07-infra-devops.md:181 already documents `uv sync --frozen --no-install-project --no-dev`, so docs/07 and docs/08 contradict each other. Same line also says `uvicorn` 0.52.3 while the table (line 37) and uv.lock say 0.52.4.

**Tekshiruv**

```
grep -nF 'uv sync --frozen --no-install-project --no-dev' backend/Dockerfile -> 16:    uv sync --frozen --no-install-project --no-dev
git log -S'--no-dev' -- backend/Dockerfile -> 14f60ce 2026-09-02 fix(infra): close the .env ignore holes, slim the prod image, lint new migrations (batch b01)
grep -rn -- '--no-dev' docs/ -> docs/07-infra-devops.md:181 ... `uv sync --frozen --no-install-project --no-dev` ... 56 emas, 39 paket
uv.lock uvicorn = 0.52.4 (doc line 74 says 0.52.3)
```

**Taklif**

Rewrite the sentence: `backend/Dockerfile:16` calls `uv sync --frozen --no-install-project --no-dev` (since 14f60ce, 2026-09-02) — dev group is NOT in the prod image, which is exactly why `websockets` must live in main `dependencies`. Fix `uvicorn` 0.52.3 -> 0.52.4 on the same line.

**Bog'liq fayllar:** `backend/Dockerfile`, `docs/07-infra-devops.md`

<sub>ID `L084:0` · ovoz 2 · rad 0</sub>

### 22. docs/08 describes a shared `mes:print:queue` fallback when agent_id is omitted; code made agent_id mandatory in 4dda538 (2026-08-29) and calling without it rai…

- **Joy:** `docs/08-packages.md:72`
- **Turi:** Hujjat kod bilan mos emas
- **Kod:** ``agent_id` berilmasa umumiy `mes:print:queue``

**Nega tuzatish kerak**

The fallback the doc describes was removed precisely because jobs pushed to the bare key were never read by ws.py and were silently lost (see docstring of print_queue_key). A reader of docs/08 would believe omitting agent_id still works and routes to a common queue. The doc was edited on 2026-09-16 (011b6f3) without fixing this.

**Tekshiruv**

```
Executed: inspect.signature(print_queue_key) -> (agent_id: int) -> str; print_label -> (ctx, instance_id: int, agent_id: int) -> str; print_queue_key() -> TypeError print_queue_key() missing 1 required positional argument: 'agent_id'; print_queue_key(7) -> mes:print:queue:7
backend/app/tasks/__init__.py:38 PRINT_QUEUE_KEY = "mes:print:queue"  # kalit prefiksi; manzilsiz kalitning o'zi o'qilmaydi
backend/app/tasks/__init__.py:60 `agent_id` MAJBURIY. Ilgari `None` berilsa umumiy `PRINT_QUEUE_KEY` ga tushardi, uni esa `ws.py` umuman o'qimaydi
git log -S'MAJBURIY. Ilgari' -- backend/app/tasks/__init__.py -> 4dda538 2026-08-29
```

**Taklif**

Replace the parenthetical with: `print_queue_key(agent_id)` -> `mes:print:queue:{agent_id}`; `agent_id` is mandatory on all four tasks (no default) — the bare `mes:print:queue` key is only a prefix and is never read.

**Bog'liq fayllar:** `backend/app/tasks/__init__.py`

<sub>ID `L084:1` · ovoz 2 · rad 0</sub>

### 23. docs/09 §2 names `ParsedPart.stage_sides()`, a method deleted in 4dda538 (2026-08-29); the code is `prisadka_passes()`

- **Joy:** `docs/09-mes-domain.md:91`
- **Turi:** Hujjat kod bilan mos emas
- **Kod:** `Paz/freza uchun ROVER bosqichi **ataylab yaratilmaydi** (`ParsedPart.stage_sides()` endi FAQAT`

**Nega tuzatish kerak**

The doc sends a reader to a method that no longer exists. grep over backend/app finds stage_sides only in a frozen migration docstring (a7c419e0b3d5). The live method on ParsedPart is prisadka_passes() returning int 0/1, not a dict of stage->sides. Three docs repeat the stale name (04:172, 10:336, 10:612), so the wrong name is self-reinforcing.

**Tekshiruv**

```
git show 4dda538 -- backend/app/services/giblab/models.py | grep stage_sides:
-    def stage_sides(self) -> dict[PostCode, int]:
+    def prisadka_passes(self) -> int:
(4dda538 2026-08-29 refactor(backend): apply the audit cleanup findings)

grep -rn stage_sides backend/app --include=*.py | grep -v migrations -> (no output)
grep -nF '    def prisadka_passes(self) -> int:' backend/app/services/giblab/models.py -> 358
grep -rn stage_sides docs/ -> docs/04-backend-data.md:172, docs/09-mes-domain.md:91, docs/10-giblab-reference.md:336, docs/10-giblab-reference.md:612
```

**Taklif**

Replace ParsedPart.stage_sides() with ParsedPart.prisadka_passes() at docs/09:91 (same rename in docs/04:172, docs/10:336, docs/10:612). The surrounding sentence already describes prisadka_passes correctly.

**Bog'liq fayllar:** `backend/app/services/giblab/models.py`, `docs/04-backend-data.md`, `docs/10-giblab-reference.md`

<sub>ID `L085:0` · ovoz 2 · rad 0</sub>

### 24. docs/10 2.3 says the part name never affects the route; since a8d1662 a name suffix flags is_custom and soft-deletes the AUTO route

- **Joy:** `docs/10-giblab-reference.md:287`
- **Turi:** Hujjat kod bilan mos emas
- **Kod:** `kod qo'yiladi — `parser.py`, `_build_part`) va marshrutga **umuman ta'sir qilmaydi**.`

**Nega tuzatish kerak**

Commit a8d1662 (2026-09-13, flag a part non-standard from a marker in its name) made ingest set is_custom=nostandart(pp.name) (ingest.py:588) from the runtime setting CUSTOM_PART_SUFFIX (ingest.py:510) and then soft-delete every AUTO PartRoute of those parts (ingest.py:699-704). So a suffix in the GibLab name attribute now removes the standard ARRA/KROMKA/PRISADKA/TMO route. docs/10 lines 286-292 (Endi marshrut faqat MES ichida, ko'rinadigan joyda beriladi) and 304-305 (Texnolog detallar matritsasida detalni Nostandart deb belgilaydi) still describe the pre-a8d1662 rule that the only entry point is the matrix checkbox. a8d1662 updated docs/03, 04, 05, 06, 09 but not docs/10; git log on docs/10 shows nothing after 8d0d8c0 (2026-09-13 16:01, before a8d1662 at 17:09).

**Tekshiruv**

```
git show --stat a8d1662 -> touches ingest.py, settings_service.py, docs/03,04,05,06,09; docs/10 absent. ingest.py:510 `nostandart = _nostandart_qoidasi(await get_setting(db, CUSTOM_PART_SUFFIX))`; :588 `is_custom=nostandart(pp.name),`; :699-704 `if nostandart_ids: await db.execute(update(PartRoute).where(PartRoute.part_id.in_(nostandart_ids), ...).values(is_deleted=True, ...))`. Executed _nostandart_qoidasi("*"): bok* -> True, bok -> False; empty marker -> False.
```

**Taklif**

In docs/10 2.3 replace the name-has-no-effect paragraph with the current rule: a name ending in the CUSTOM_PART_SUFFIX runtime setting marks the part nostandart at ingest, its AUTO route is built then soft-deleted, the file wins on re-upload (restore_custom_routes: entry.is_custom or part.is_custom), and the marker stays in the stored name. Point to docs/09 for the setting.

**Bog'liq fayllar:** `backend/app/services/giblab/ingest.py`, `backend/app/services/settings_service.py`, `docs/09-mes-domain.md`

<sub>ID `L086:0` · ovoz 2 · rad 0</sub>

### 25. docs/10 3.2 says each XNC operation yields one PRISADKA scan; code gives one scan per part

- **Joy:** `docs/10-giblab-reference.md:612`
- **Turi:** Hujjat kod bilan mos emas
- **Kod:** `(`stage_sides()` ishlovi bor — teshik, paz yoki freza — har operatsiyaga bitta PRISADKA`

**Nega tuzatish kerak**

Same drift as L086-02 on the doc side: since b26c619 the PRISADKA step has per_instance = prisadka_passes() in 0..1, so a part with 3 XNC programs is scanned once, not three times. The doc's own 2.3 (lines 297-298) and the models.py:358 docstring (BITTA skan — yuzlar soni emas) describe the current rule; lines 612-613 contradict them.

**Tekshiruv**

```
Executed: 3 XncOps -> prisadka_passes(): 1. models.py:376 `return int(any(op.bores or op.edge_bores or op.grooves or any(op.mills) for op in self.xnc_ops))`. ingest.py:649 `if prisadka := pp.prisadka_passes():` then `steps.append((6, PostCode.PRISADKA, prisadka))`.
```

**Taklif**

Rewrite lines 612-613: (prisadka_passes() ishlovi bor — teshik, paz yoki freza — bo'lsa BITTA PRISADKA skani beradi, operatsiyalar soniga qaramay; 2.3).

**Bog'liq fayllar:** `backend/app/services/giblab/models.py`

<sub>ID `L086:2` · ovoz 2 · rad 0</sub>

### 26. docs/10 2.1.1 says the material report still groups by (name, kind); reports.py has grouped by (code or name, kind) since d8526ee

- **Joy:** `docs/10-giblab-reference.md:152`
- **Turi:** Hujjat kod bilan mos emas
- **Kod:** `kalit **nom emas, kod**. Material hisoboti hozir `(name, kind)` bo'yicha yig'adi — bir material`

**Nega tuzatish kerak**

Lines 152-154 present switching to code-keyed aggregation as an open decision (alohida qaror talab qiladi). It was taken on 2026-09-03 (d8526ee, material rows keyed by code): reports.py:618 keys on (item.get(code) or item[name], item[kind]). docs/03:565 already documents the new key; docs/10 contradicts it and would send a reader to re-decide a settled question.

**Tekshiruv**

```
reports.py:611 `agg: dict[tuple[str, str], MaterialUsageRow] = {}`; :618 `key = (item.get("code") or item["name"], item["kind"])`. git log -S on that line -> d8526ee 2026-09-03. docs/03-backend-api.md:565: Guruhlash kaliti — (code or name, kind).
```

**Taklif**

Replace lines 152-154 with: the report groups by (code or name, kind) since 2026-09-03 (reports.py, docs/03); old code-less exports fall back to the name, so a material loaded before and after the catalogue switch still splits into two rows.

**Bog'liq fayllar:** `backend/app/api/routes/reports.py`, `docs/03-backend-api.md`

<sub>ID `L086:4` · ovoz 2 · rad 0</sub>

### 27. docs/11 says the auto-code warning fires only when the product FIRST part lacks a code; the parser warns once per product regardless of position

- **Joy:** `docs/11-detal-id-nomlash.md:31`
- **Turi:** Hujjat kod bilan mos emas
- **Kod:** `ogohlantirish esa FAQAT mahsulotning BIRINCHI detali kodsiz bo'lganda chiqadi, o'rtadagi kodsiz detal jimgina raqamlanadi`

**Nega tuzatish kerak**

The doc describes pre-2026-09-02 behaviour. Commit b622fc4 (auto-code warning per product) replaced `if len(product.parts) == 0:` with `if product.code not in auto_coded:` and changed the message text; the doc line was written 2026-08-29 (fc76fe9) and never updated. A texnolog reading docs/11 concludes that a mid-list code-less part is numbered silently and that the absence of a warning means GibLab gave every part a real code - the opposite of what ingest now does. The auto-code decides the QR / SCX file name / Panel ID, which is exactly what this document governs.

**Tekshiruv**

```
Ran the real parser (backend/app/services/giblab/parser.py:_build_part) with the FIRST part carrying a code
and the later parts having none:
  _build_part(<part code="03_002"/>)  -> code -> 03_002
  _build_part(<part name="Kodsiz"/>)  -> code -> 002
  _build_part(<part name="Kodsiz2"/>) -> code -> 003
  warnings: ["100701: ba'zi detallarda kod yo'q - tartib raqami bo'yicha berildi (001, 002, ...). QR va SCX nomlari shu raqamga bog'lanadi."]
The warning IS emitted although the FIRST part had a code, so the doc claim 'jimgina raqamlanadi' is false.
Code site:
  backend/app/services/giblab/parser.py:111  `        if product.code not in auto_coded:`
History:
  $ git log -S auto_coded --oneline -
… (qisqartirildi)
```

**Taklif**

Rewrite the clause at docs/11:31 to match parser.py: the warning is emitted once per MAHSULOT, at the first code-less part of that product (auto_coded set), wherever it sits in the list. Quote the current message text (ba'zi detallarda kod yo'q ...) instead of the removed one.

**Bog'liq fayllar:** `backend/app/services/giblab/parser.py`

<sub>ID `L087:0` · ovoz 2 · rad 0</sub>

### 28. docs/11 table says ingest builds SCX file names from qr_texts (prefix-less); ingest passes serial_qrs(order.number), contradicting the doc own row two lines ab…

- **Joy:** `docs/11-detal-id-nomlash.md:140`
- **Turi:** Hujjat kod bilan mos emas
- **Kod:** `nomlar ingestda parser bergan `qr_texts`dan, qayta yaratishda bazadagi QR'lardan`

**Nega tuzatish kerak**

ParsedPart.qr_texts is the file-local, order-prefix-LESS key list; its single read in ingest.py is the intra-file ID-collision check. SCX names come from `qrs = pp.serial_qrs(order.number)`, i.e. the prefixed string. The doc own row at line 138 states this correctly (qr_texts faqat fayl ichidagi to'qnashuv tekshiruvi uchun), so line 140 contradicts it. Taking line 140 at face value means the SCX name is 100701_03_002_1 while chek/QR/DB hold B-2026-047_100701_03_002_1 - breaking the single invariant this document exists to state, and it is the row an engineer consults before touching scx.py.

**Tekshiruv**

```
Executed against the real dataclass and the real ingest module:
  pp = ParsedPart(product_code="100701", code="03_002", count=2, ...)
  pp.qr_texts                  -> ['100701_03_002_1', '100701_03_002_2']
  pp.serial_qrs("B-2026-047")  -> ['B-2026-047_100701_03_002_1', 'B-2026-047_100701_03_002_2']
  qr_texts occurrences in ingest.py: ['scx_dir: Path, pp: ParsedPart, qr_texts: list[str], plate_thickness: float | None', 'for filename, content in build_scx_files(pp, qr_texts, plate_thickness=plate_thickness):', 'qr_texts: list[str],', 'written = await run_in_threadpool(_build_and_write_scx, scx_dir, pp, qr_texts, plate_thickness)', 'for qr in pp.qr_texts:']
The only pp.qr_texts READ is the c
… (qisqartirildi)
```

**Taklif**

Change docs/11:140 to say names come from ParsedPart.serial_qrs(order.number) at ingest (with the order prefix) and from the DB QRs on regenerate - i.e. make it agree with the already-correct row at line 138.

**Bog'liq fayllar:** `backend/app/services/giblab/ingest.py`, `backend/app/services/giblab/models.py`, `backend/app/services/giblab/scx.py`

<sub>ID `L087:1` · ovoz 2 · rad 0</sub>

### 29. docs/11 intro still lists the UPAKOVKA open-pack list among the _n-less screens; since 2026-09-04 it renders the full qr_text, as the doc own table row says

- **Joy:** `docs/11-detal-id-nomlash.md:7`
- **Turi:** Hujjat kod bilan mos emas
- **Kod:** `UPAKOVKA dagi ochiq qadoq ro'yxati, navbatdagi yig'ma bog'lami va WS orqali`

**Nega tuzatish kerak**

The intro enumerates the screens that show the copy-less key {mahsulotKodi}_{detalKodi} and adds that its schema field is `code` on KROMKA/PRISADKA and `part_code` elsewhere. The open pack is no longer one of them: commit 693823a (2026-09-04) switched it to <Serial code={i.qr_text} /> and updated the table row at docs/11:143 in the same commit, but left the intro paragraph stale. The document now says two opposite things about the same screen and the stale one is the summary a reader hits first. The prefix-less rendering was the actual defect that commit fixed (three physical copies drew three identical rows), so the intro advertises the bug as the rule.

**Tekshiruv**

```
Code, open-pack (left) pane of UpakovkaView:
  frontend/src/components/Terminal/UpakovkaView.tsx:225  CHAP: ochiq qadoq - skan shu yerga tushadi (comment)
  frontend/src/components/Terminal/UpakovkaView.tsx:304  `                          <Serial code={i.qr_text} />`
(line 342 opens the separate 'Yakunlangan qadoqlar' block, so 304 is inside the open pack.)
$ git show 693823a -- docs/11-detal-id-nomlash.md
  -| Terminal UI (upakovka) | Ochiq qadoq ichidagi ro'yxat `part_code` ni (`pachka.py`, `_n` SIZ) ...
  +| Terminal UI (upakovka) | 2026-09-04 dan boshqa postlar bilan bir: ochiq qadoq ichida `qr_text` (`Serial`, nusxa ko'rinadi - ilgari `part_code`, uch nusxa uch bir xil qator edi) ...
Th
… (qisqartirildi)
```

**Taklif**

In docs/11:6-11 drop 'UPAKOVKA dagi ochiq qadoq ro'yxati' from the _n-less list; if the UPAKOVKA right-hand panel should stay listed, name it explicitly (o'ng paneldagi detallar ro'yxati - part_code + InstanceChip) so the intro matches the table row at line 143.

**Bog'liq fayllar:** `frontend/src/components/Terminal/UpakovkaView.tsx`

<sub>ID `L087:2` · ovoz 2 · rad 0</sub>

### 30. Import qilinmaydigan operatsiya ogohlantirishi texnologga rus tilida chiqadi (_OP_NAMES)

- **Joy:** `backend/app/services/giblab/parser.py:48`
- **Turi:** O'zbekcha bo'lmagan matn
- **Kod:** `"CN": "нестинговый раскрой (CNC nesting)",`

**Nega tuzatish kerak**

_OP_NAMES qiymatlari _advisories() (parser.py:229) orqali project.warnings ga tushadi, ingest_project summary["warnings"] ga (ingest.py:754), u yerdan esa /orders/{id}/files javobidagi Message matniga (api/routes/orders/files.py:133 — " | ".join(warnings[:3])). Ya'ni menejer/texnolog .project yuklaganda ekranda RUSCHA matn ko'radi: "CN — нестинговый раскрой (CNC nesting)". CLAUDE.md qoidasi: foydalanuvchi ko'radigan hamma matn o'zbekcha, ISTISNOSIZ. Uchta qiymatdan ikkitasi (SP, GR) qavs ichida o'zbekcha izohga ega, CN da esa izoh ham inglizcha ("CNC nesting") — ya'ni CN uchun o'zbekcha nom umuman yo'q. backend/app ichida bu uchta satr Cyrillic matn bo'lgan YAGONA foydalanuvchiga chiqadigan qator (qolgan barcha kirill uchrashuvlari izoh/docstring).

**Tekshiruv**

```
$ grep -Fn '    "CN": "нестинговый раскрой (CNC nesting)",' backend/app/services/giblab/parser.py
48:    "CN": "нестинговый раскрой (CNC nesting)",

Bajarilgan skript (backend/, uv run python):
---
from app.services.giblab.parser import parse_project
xml = b'<project project.uuid="u1" name="t"><good typeId="product" id="1" code="P1" name="Shkaf" count="1"><part id="10" code="A1" name="yon" l="500" w="300" count="1"/></good><operation typeId="CN" id="90" code="cn1"/><operation typeId="SP" id="91" code="sp1"/><operation typeId="GR" id="92" code="gr1"/><operation typeId="ZZ" id="93" code="zz1"/></project>'
for w in parse_project(xml).warnings: print('WARN:', w)
---
Chiqish:
WARN: Faylda import
… (qisqartirildi)
```

**Taklif**

_OP_NAMES qiymatlarini o'zbekchaga o'tkazish, GibLab'ning ruscha nomini kerak bo'lsa qavs ichida manba sifatida qoldirish (docs/10-giblab-reference.md:362-364 jadvalidagi nomlarga mos): "CN": "nesting kesish (GibLab: нестинговый раскрой)", "SP": "yuza ishlovi (GibLab: обработка поверхности)", "GR": "paz ochish (GibLab: пазование)". CN uchun o'zbekcha nom yo'qligi ayniqsa muhim — hozir u faqat ruscha+inglizcha.

**Bog'liq fayllar:** `backend/app/services/giblab/ingest.py`, `backend/app/api/routes/orders/files.py`, `docs/10-giblab-reference.md`

<sub>ID `L075:0` · ovoz 2 · rad 0</sub>

## Past (50)

### 31. OrderCreate/OrderUpdate money fields have no max_digits — values >= 10^12 pass Pydantic and blow up as a 500 at Numeric(14,2) INSERT

- **Joy:** `backend/app/schemas/orders.py:96`
- **Turi:** Xatolik
- **Kod:** `amount: Decimal | None = Field(default=None, ge=0)`

**Nega tuzatish kerak**

Order.amount / Order.advance_payment are `Numeric(14, 2)` (backend/app/models/order.py:28,30). The schema constrains only `ge=0`, so a body with amount=1000000000000 (13 integer digits) is accepted by Pydantic, then Postgres raises `numeric field overflow` at commit in create_order/update_order; there is no DataError handler in core/exceptions.py, so the manager gets a 500 instead of a 422 with an Uzbek message. The frontend money input caps at 12 digits (frontend/src/lib/validation.ts:60), so this is only reachable through a direct API call, hence low severity. Same gap on lines 97, 107, 108 (advance_payment and OrderUpdate). The project already treats this class as a bug elsewhere (bridge_agents.py:96 comment on prev_duration_s int4 bounds).

**Tekshiruv**

```
1) `uv run python` importing app.schemas.orders: `OrderCreate(client_id=1, amount=Decimal("1000000000000"))` -> `OrderCreate accepted amount = 1000000000000`; `OrderUpdate(advance_payment=Decimal("99999999999999999"))` -> accepted.
2) `docker exec mebelix_audit_pg psql -U postgres -tAc "select 1000000000000::numeric(14,2);"` -> `ERROR:  numeric field overflow  DETAIL:  A field with precision 14, scale 2 must round to an absolute value less than 10^12.` (999999999999.99 succeeds; 10.555 silently rounds to 10.56).
3) `grep -n "DataError\|IntegrityError\|DBAPIError\|SQLAlchemyError" backend/app/core/exceptions.py backend/app/core/setup.py backend/app/main.py` -> no matches (no translation of DB
… (qisqartirildi)
```

**Taklif**

In OrderCreate and OrderUpdate (lines 96-97 and 107-108) change both money fields to `Field(default=None, ge=0, max_digits=14, decimal_places=2)` so the schema mirrors `Numeric(14, 2)` and out-of-range input becomes a 422. Then `make frontend-gen` (schema constraint appears in openapi) and mention the bound in docs/03-backend-api.md's create/update order rows.

**Bog'liq fayllar:** `backend/app/models/order.py`, `backend/app/api/routes/orders/lifecycle.py`, `frontend/src/lib/validation.ts`, `docs/03-backend-api.md`

<sub>ID `L013:0` · ovoz 3 · rad 0</sub>

### 32. "Asl hajmda yangi oynada ochish" havolasi rasmni ochmaydi — server Content-Disposition: attachment yuboradi, brauzer faylni yuklab oladi

- **Joy:** `frontend/src/components/Anketa/RoomPhotos.tsx:224`
- **Turi:** Xatolik
- **Kod:** `Asl hajmda yangi oynada ochish`

**Nega tuzatish kerak**

Havola `target="_blank"` bilan `/api/v1/orders/{id}/files/{fileId}` ga yuqori darajali navigatsiya qiladi. O'sha endpoint `FileResponse(..., filename=row.filename, ...)` qaytaradi, starlette esa `filename` berilganda sukut bo'yicha `content-disposition: attachment; filename="..."` qo'shadi. RFC 6266 bo'yicha bunday javob yuqori darajali navigatsiyada ko'rsatilmaydi — yuklab olinadi. Ya'ni menejer "yangi oynada ochish" ni bosganda bo'sh tab ochilib yopiladi va rasm diskka tushadi; e'lon qilingan xulq hech qachon bajarilmaydi. Grid va dialogdagi `<img>` lar esa ishlaydi (subresource yuklashda Content-Disposition e'tiborga olinmaydi), shuning uchun nosozlik faqat shu havolada. docs/06 ham xuddi shu noto'g'ri xulqni hujjatlashtirgan.

**Tekshiruv**

```
Header starlette'dan haqiqiy FileResponse qurib olindi (backend/app/api/routes/orders/files.py:233 bilan bir xil chaqiruv):

$ uv run python scratchpad/fr.py
  import pathlib, tempfile
  from starlette.responses import FileResponse
  p = pathlib.Path(tempfile.gettempdir())/"x.jpg"; p.write_bytes(b"ÿØÿ")
  r = FileResponse(p, filename="mijoz_namuna.jpg", media_type="image/jpeg")
  for k, v in r.raw_headers: print(k.decode(), ":", v.decode())
->
content-type : image/jpeg
accept-ranges : bytes
content-disposition : attachment; filename="mijoz_namuna.jpg"

Manbadagi qatorlar (grep -F bilan tasdiqlangan):
  frontend/src/components/Anketa/RoomPhotos.tsx:224:            Asl hajmda yangi oynada ochi
… (qisqartirildi)
```

**Taklif**

Eng kichik tuzatish frontendda: havola matnini haqiqatga moslash (masalan "Asl hajmda yuklab olish" + `download` atributi), yoki havolani umuman olib tashlash — dialogdagi `<img>` allaqachon to'liq rasmni ko'rsatadi. Agar haqiqatan yangi oynada ochilishi kerak bo'lsa, `download_order_file` da rasm (DOCUMENT) uchun `FileResponse(..., content_disposition_type="inline")` berish kerak — ammo bu `$orderId.tsx` dagi `download` havolalariga ta'sir qilmasligi uchun faqat `row.kind == FileKind.DOCUMENT` shoxida qilinsin. Har qanday holatda `docs/06-frontend-components.md:389` ham yangilanadi.

**Bog'liq fayllar:** `backend/app/api/routes/orders/files.py`, `docs/06-frontend-components.md`, `frontend/src/routes/_layout/orders/$orderId.tsx`

<sub>ID `L022:0` · ovoz 3 · rad 0</sub>

### 33. Client edit dialog prefills the raw stored phone (+998901234567) instead of the formatted one — the only phone form in the repo that skips formatUzPhone

- **Joy:** `frontend/src/components/Clients/AddClient.tsx:71`
- **Turi:** Xatolik
- **Kod:** `phone: client?.phone ?? "",`

**Nega tuzatish kerak**

Phones are stored canonically (`String(13)`, `^\+998\d{9}$`) and every other surface renders them through `formatUzPhone`: ClientCard.tsx:94, clients.tsx:143, PersonDialog.tsx:109, UserInformation.tsx:82. AddClient's edit mode (lines 71-72) feeds the canonical string straight into the input, so the dialog opens showing `+998901234567` while the table row behind it shows `+998 90 123-45-67` and the input's own placeholder promises `+998 90 123-45-67`. As soon as the user touches the field, `formatUzPhone` reformats it, so the value visibly jumps.

**Tekshiruv**

```
Bundled the real module with esbuild and ran it:

  cd frontend && printf 'import { formatUzPhone } from "./src/lib/validation"
...' | npx esbuild --bundle --loader=ts --format=cjs --platform=node --alias:@=./src --outfile=.../out.cjs && node .../out.cjs
  {"stored":"+998901234567","shown_in_AddClient_edit":"+998901234567","shown_everywhere_else":"+998 90 123-45-67"}

Outlier confirmed with: grep -rn "formatUzPhone" frontend/src | grep -v validation.ts -> every other prefill wraps the value (PersonDialog.tsx:109 `phone: formatUzPhone(person?.phone ?? ""),`; UserInformation.tsx:82), AddClient only imports it for the onChange handlers (lines 162, 184).
```

**Taklif**

Wrap both prefills the same way PersonDialog does: `phone: formatUzPhone(client?.phone ?? "")` and `phone_alt: formatUzPhone(client?.phone_alt ?? "")` (AddClient.tsx:71-72). The submit path is unaffected — `optionalFormattedPhoneSchema` strips spaces and dashes.

**Bog'liq fayllar:** `frontend/src/components/People/PersonDialog.tsx`, `frontend/src/components/Clients/ClientCard.tsx`, `frontend/src/routes/_layout/clients.tsx`, `frontend/src/lib/validation.ts`

<sub>ID `L023:1` · ovoz 3 · rad 0</sub>

### 34. SidebarTrigger'ning ekran o'quvchi yorlig'i mobil rejimda holatga ERGASHMAYDI — sheet yopiq turganda ham "Menyuni yig'ish" deydi

- **Joy:** `frontend/src/components/ui/sidebar.tsx:262`
- **Turi:** Xatolik
- **Kod:** `const sidebarCopy = open ? "Menyuni yig'ish" : "Menyuni ochish"`

**Nega tuzatish kerak**

Yorliq FAQAT desktop holati `open` dan olinadi, mobil holat `openMobile` dan emas. `toggleSidebar` esa mobil rejimda `open` ga UMUMAN tegmaydi (sidebar.tsx:95 `return isMobile ? setOpenMobile((open) => !open) : setOpen((open) => !open)`), ya'ni telefonda `open` cookie'dagi/default qiymatida qotib qoladi. Natijada `_layout.tsx:122` dagi `md:hidden` header tugmasi (mobil rejimda yagona trigger, sheet YOPIQ holatda ko'rinadi) ekran o'quvchiga doim "Menyuni yig'ish" deb o'qiladi — ochish kerak bo'lgan tugma "yig'ish" deyapti; bosilgandan keyin (sheet ochilganda) ham matn o'zgarmaydi. Lucide svg `aria-hidden="true"` bo'lgani uchun bu sr-only span tugmaning YAGONA accessible name'i. docs/06 §5 aynan bu juftlikni ko'rsatib "ekran o'quvchi matnlari ham o'zbekchalashtirilgan" deydi — ya'ni yorliq h
… (qisqartirildi)

**Tekshiruv**

```
Vite SSR orqali haqiqiy render (`@/hooks/useMobile` stub bilan), scratchpad/l030/probe.mjs:
$ node probe.mjs
isMobile=false  openMobile=false (sheet CLOSED)  sr-only label = "Menyuni yig&#x27;ish"
isMobile=true   openMobile=false (sheet CLOSED)  sr-only label = "Menyuni yig&#x27;ish"

probe2.mjs (isMobile=true, `open` boshqariladigan prop sifatida majburlangan) — yorliq FAQAT `open` ga bog'liqligini va svg `aria-hidden` ekanini ko'rsatadi:
--- controlled open=true (isMobile=true)
<button data-slot="sidebar-trigger" ...><svg ... aria-hidden="true">...</svg><span class="sr-only">Menyuni yig&#x27;ish</span></button>
--- controlled open=false (isMobile=true)
<button data-slot="sidebar-trigger" .
… (qisqartirildi)
```

**Taklif**

`SidebarTrigger` da joriy rejimning haqiqiy holatini o'qish: `const { toggleSidebar, isMobile, open, openMobile } = useSidebar()` va `const sidebarCopy = (isMobile ? openMobile : open) ? "Menyuni yig'ish" : "Menyuni ochish"`. Shu bilan birga `aria-expanded={isMobile ? openMobile : open}` qo'shilsa tugma holati dasturiy ravishda ham e'lon qilinadi.

**Bog'liq fayllar:** `frontend/src/routes/_layout.tsx`, `frontend/src/components/Sidebar/AppSidebar.tsx`, `docs/06-frontend-components.md`

<sub>ID `L030:0` · ovoz 3 · rad 0</sub>

### 35. WS handler ichidagi HAR QANDAY xato "JSON emas" degan catch bloki tomonidan jimgina yutiladi (ishga tushirib tasdiqlandi)

- **Joy:** `frontend/src/hooks/useMesWs.ts:40`
- **Turi:** Xatolik
- **Kod:** `else if (event.type) handler.current(event)`

**Nega tuzatish kerak**

`handler.current(event)` `try` blokining ICHIDA turibdi, `catch` esa bo'sh va izohi `/* skip non-JSON frames */` — ya'ni u faqat `JSON.parse` uchun mo'ljallangan. Natijada iste'molchi callback'idagi (`_layout.tsx` toast+navigate, `terminal.tsx` ning uzun handler'i — `playSuccess()`, `setLastScan`, `queryClient.invalidateQueries`, `tablo.tsx`, `agents.tsx`, `work-centers.tsx`) har qanday istisno hech qayerda ko'rinmaydi: na konsolda, na UI'da. Jonli yangilanish o'sha xabarda jim to'xtaydi va «nega toast chiqmadi» savoli izsiz qoladi — bu aynan `ws.py` dagi logging qo'shilishiga sabab bo'lgan muammo turi.

**Tekshiruv**

```
Haqiqiy `useMesWs.ts` Node 24 da SHU HOLICHA ishga tushirildi (react va @/utils stub'langan, soxta global `WebSocket`), handler ataylab `event.payload.order_id` ni o'qiydi (`_layout.tsx:86` dagi kod bilan bir xil):

  $ node --import ./register2.mjs harness3.mjs
  ws url: ws://localhost:8000/api/v1/ws/events
  A) well-formed event:
    handler ran, order_id = 7
  B) event WITHOUT payload (handler throws TypeError):
    -> error escaped? false | handler invocations: 2

Ya'ni handler chaqirildi (2 marta), ikkinchisida TypeError tashladi va u `onmessage` dan CHIQMADI — to'liq yutildi. Blok: `useMesWs.ts:41` `        } catch {` / `useMesWs.ts:42` `          /* skip non-JSON frames */`.
Skript: C
… (qisqartirildi)
```

**Taklif**

`try` ni faqat parse atrofida qoldir: `let event; try { event = JSON.parse(e.data) } catch { return }` — keyin pong/dispatch `try` dan TASHQARIDA bajarilsin. Shunda iste'molchi xatosi brauzer konsoliga (va window.onerror'ga) chiqadi, «JSON emas» frame'lari esa avvalgidek jimgina tashlanadi.

**Bog'liq fayllar:** `frontend/src/routes/_layout.tsx`, `frontend/src/routes/terminal.tsx`, `frontend/src/routes/tablo.tsx`, `frontend/src/routes/_layout/agents.tsx`, `frontend/src/routes/_layout/work-centers.tsx`, `frontend/src/routes/_layout/index.tsx`

<sub>ID `L031:1` · ovoz 3 · rad 1</sub>

### 36. models/base.py comment says 18 `ix_*_is_deleted` indexes were dropped; migration 6a5051b7b420, docs/04 and the live DB all say 19

- **Joy:** `backend/app/models/base.py:30`
- **Turi:** Keraksiz/yolg'on izoh
- **Kod:** `# shu ishni qiladi. 18 ta `ix_*_is_deleted` migratsiyada o'chirilgan.`

**Nega tuzatish kerak**

The comment is the only place with the number 18. The migration it refers to (6a5051b7b420) drops one index per entry of its `_TABLES` tuple, which has 19 entries and whose own docstring says '* 19 ta `ix_<jadval>_is_deleted`'. docs/04-backend-data.md:23 and :470 also say 19 ('prodda 25 = 19 + 6'). A reader trusting the model comment gets a wrong count and may go hunting for a phantom 19th live table that was 'missed'.

**Tekshiruv**

```
Imported the migration module and ran `len(m._TABLES)` -> 19 (list printed: audit_log, bridge_agent, client, employee, machine, order, order_file, organization, pachka, pachka_item, part, part_instance, part_route, post, product, scan, user, waste_item, work_session). After `alembic upgrade head` on a fresh postgres:15-alpine DB, `SELECT tablename||'.'||indexname FROM pg_indexes WHERE indexname LIKE 'ix\_%\_is\_deleted'` returned exactly 6 rows, all legacy tables (machine_stop, payment, sale, stock_item, stock_move, stop_reason) - i.e. the 19 live-table indexes are gone and docs/04:470 '25 = 19 + 6' is exact. grep -F confirmed both quotes verbatim: base.py:30 '18 ta `ix_*_is_deleted` migrats
… (qisqartirildi)
```

**Taklif**

Change '18 ta' to '19 ta' in backend/app/models/base.py:30 (docs/04 and the migration are already correct; no migration or doc change needed).

**Bog'liq fayllar:** `backend/app/migrations/versions/6a5051b7b420_drop_redundant_indexes_and_updated_at_.py`, `docs/04-backend-data.md`

<sub>ID `L010:0` · ovoz 2 · rad 0 · 1 ta takror topilma birlashtirildi</sub>

### 37. Stale comment on Part.xnc_summary lists a `sides` key that ingest no longer writes and omits the six keys it does write

- **Joy:** `backend/app/models/order.py:104`
- **Turi:** Keraksiz/yolg'on izoh
- **Kod:** `# Merged XNC summary: {"bores": N, "edge_bores": N, "grooves": N, "mills": N, "sides": 1|2}`

**Nega tuzatish kerak**

The model comment is the first thing a reader sees when asking 'what is in xnc_summary'. It names `sides` (removed from ingest in 4dda538, 2026-08-29 — the only remaining reader is the 1cfd3b2182fc downgrade) and does not mention groove_sides/mill_sides/groove_paths/mill_paths, which labels.py, cutmap.py and stored_machined_sides actually consume. docs/04-backend-data.md:110 already has the correct key list and explicitly says '`sides` esa ESKI kalit ... hozirgi ingest uni yozmaydi', so the code comment contradicts the primary doc.

**Tekshiruv**

```
grep -n '"sides":' backend/app/services/giblab/ingest.py -> no match (exit 1). Keys actually written at ingest.py:588-610: bores, edge_bores, grooves, mills, groove_sides, mill_sides, groove_paths, mill_paths. git log -S'"sides"' -- ingest.py -> 4dda538 2026-08-29 removed `"sides": len(pp.xnc_ops)`. Repo-wide readers of a plain `sides` key: only migrations/versions/1cfd3b2182fc:46 `(p.xnc_summary->>'sides')::int = 2`. docs/04-backend-data.md:110 lists `{"bores", "edge_bores", "grooves", "mills", "groove_sides", "mill_sides", "groove_paths", "mill_paths"}`.
```

**Taklif**

Replace the comment with the current key list (mirroring docs/04:110 and ingest.py:593-608), e.g. `# XNC xulosa: {"bores", "edge_bores", "grooves", "mills", "groove_sides", "mill_sides", "groove_paths", "mill_paths"} — `sides` eski kalit, faqat 1cfd3b2182fc downgrade'i o'qiydi`.

**Bog'liq fayllar:** `backend/app/services/giblab/ingest.py`, `backend/app/migrations/versions/1cfd3b2182fc_prisadka_one_scan_per_instance.py`, `docs/04-backend-data.md`

<sub>ID `L011:0` · ovoz 2 · rad 0</sub>

### 38. ingest_project: the five-line rationale for `order.project_name` is glued to the nostandart-route comment and sits 8 lines above unrelated code

- **Joy:** `backend/app/services/giblab/ingest.py:690`
- **Turi:** Keraksiz/yolg'on izoh
- **Kod:** `# Nom YUKLANGAN FAYL nomidan olinadi (kengaytmasiz): "2064 alisher.project" -> "2064 alisher".`

**Nega tuzatish kerak**

Two unrelated comment blocks are concatenated with no blank line (lines 690-694 explain `order.project_name`, lines 695-698 explain the nostandart soft-delete), and the statement that immediately follows both is `if nostandart_ids:`. `order.project_name = ...` is at line 706, after the whole UPDATE block. A reader attributes the entire 9-line rationale to the nostandart UPDATE and loses the `project.name` vs filename history - which is the one thing the comment exists to preserve.

**Tekshiruv**

```
$ sed -n '689,706p' backend/app/services/giblab/ingest.py | cat -A  (truncated, '$' = EOL)
    order.project_uuid = project.uuid$
    # Nom YUKLANGAN FAYL nomidan olinadi (kengaytmasiz): "2064 alisher.project" -> "2064 alisher".$
    ... 4 more lines ...
    # ham, TABLOda ham ko'rinmasdi. Fayl nomi esa doim bor.$
    # Nomi bo'yicha nostandart bo'lgan detalning AUTO marshruti YUMSHOQ o'chiriladi —$
    ... 3 more lines ...
    if nostandart_ids:$
        await db.execute($
            ...
        )$
$
    order.project_name = Path(original_filename).stem or project.name$
No blank line separates line 694 from line 695; the first block's subject is 12 lines away.
```

**Taklif**

Move the 690-694 block down so it sits directly above `order.project_name = Path(original_filename).stem or project.name` (line 706), leaving 695-698 attached to `if nostandart_ids:`.

<sub>ID `L043:2` · ovoz 2 · rad 0</sub>

### 39. OrderMatrix.tsx header comment still claims 6 post columns; the table renders only the 3 STANDARD_MATRIX_POSTS

- **Joy:** `frontend/src/components/Orders/OrderMatrix.tsx:1`
- **Turi:** Keraksiz/yolg'on izoh
- **Kod:** `// Texnolog matritsasi: rows = parts, columns = 6 posts.`

**Nega tuzatish kerak**

The first line of the file describes a layout that has not existed since commit 313deaf: the columns come from sortedPosts, which is "(posts ?? []).filter((p) => STANDARD_MATRIX_POSTS.includes(p.code))" (OrderMatrix.tsx:88), and frontend/src/lib/mes.ts:156 defines STANDARD_MATRIX_POSTS as [ARRA, KROMKA, PRISADKA] - three posts, not six. docs/06-frontend-components.md:338 already states the correct rule, so the file header is the only stale copy, and it is the first thing a reader of the component sees.

**Tekshiruv**

```
$ git log --oneline -L1,2:frontend/src/components/Orders/OrderMatrix.tsx
15ec867 chore: drop TZ section references from code comments and docstrings
-// Texnolog matritsasi (TZ 6.3.3): rows = parts, columns = 6 posts.
+// Texnolog matritsasi: rows = parts, columns = 6 posts.
26e00af feat: implement MES core per TZ v2.2 (phases 1-9)
(the line has never been updated; the filter arrived later, in the only commit touching the constant: git log --oneline -S STANDARD_MATRIX_POSTS -- frontend/src/lib/mes.ts -> 313deaf)
$ grep -n -F "// Texnolog matritsasi: rows = parts, columns = 6 posts." frontend/src/components/Orders/OrderMatrix.tsx
1:// Texnolog matritsasi: rows = parts, columns = 6 posts.
$ gr
… (qisqartirildi)
```

**Taklif**

Rewrite the header so it says the columns are STANDARD_MATRIX_POSTS (ARRA/KROMKA/PRISADKA) plus the Nostandart and Izoh columns, matching docs/06-frontend-components.md:338.

**Bog'liq fayllar:** `frontend/src/lib/mes.ts`, `docs/06-frontend-components.md`

<sub>ID `L047:1` · ovoz 2 · rad 0</sub>

### 40. Izoh telefon serverda "+998 90 123-45-67" ko'rinishida saqlanadi deydi — zod transform bo'shliq/tirelarni olib tashlaydi, server esa bunday qiymatni RAD ETADI

- **Joy:** `frontend/src/components/People/PersonDialog.tsx:144`
- **Turi:** Keraksiz/yolg'on izoh
- **Kod:** `// ekranda ham, serverda ham "+998 90 123-45-67" bo'ladi.`

**Nega tuzatish kerak**

Izoh payload haqida yolg'on fakt aytadi. `optionalFormattedPhoneSchema` ning o'z docstring'i teskarisini yozadi (validation.ts:30: `/** Ko'rinishda "+998 90 123-45-67", submit'da kanonik "+998901234567" (transform). */`), backend esa bo'shliqli variantni 422 bilan qaytaradi (PHONE_PATTERN = r"^\+998\d{9}$"). Shu izohga ishongan dasturchi telefonni formatlangan satr bo'yicha qidirsa yoki payloadga `form.phone` ni yuborsa — jimgina yiqiladi.

**Tekshiruv**

```
Zod sxemasi bajarildi (node, validation.ts:31-34 dagi aynan transform+refine):
  "+998 90 123-45-67" -> "+998901234567"
  "901234567" -> FAIL
Backend bajarildi:
  $ uv run --project backend python -c "from app.schemas.users import validate_phone; ..."
  '+998 90 123-45-67' -> REJECTED: Telefon +998 bilan boshlanib, 9 ta raqamdan iborat bo'lsin
  '+998901234567' -> +998901234567
Manba: backend/app/schemas/users.py:15 `PHONE_PATTERN = r"^\+998\d{9}$"`; frontend/src/lib/validation.ts:30 (grep -F bilan tasdiqlandi).
```

**Taklif**

144-qatorni haqiqatga moslashtir: ekranda "+998 90 123-45-67", payloadda esa `optionalFormattedPhoneSchema` transformi bergan kanonik "+998901234567" ketadi (validation.ts:30 dagi kabi).

**Bog'liq fayllar:** `frontend/src/lib/validation.ts`, `backend/app/schemas/users.py`

<sub>ID `L026:1` · ovoz 2 · rad 0</sub>

### 41. Telefon izohi serverga formatlangan satr ketadi deydi — aslida zod kanonik `+998901234567` ga o'tkazadi, backend formatlanganini rad etadi

- **Joy:** `frontend/src/components/People/PersonDialog.tsx:144`
- **Turi:** Keraksiz/yolg'on izoh
- **Kod:** `// ekranda ham, serverda ham "+998 90 123-45-67" bo'ladi.`

**Nega tuzatish kerak**

`optionalFormattedPhoneSchema` (lib/validation.ts:31-34) `.transform((v) => v.replace(/[\s-]+/g, ""))` qiladi, ya'ni `phone` o'zgaruvchisi (PersonDialog.tsx:146-147) KANONIK satr. Serverda formatlangan variant umuman qabul qilinmaydi (`PHONE_PATTERN = r"^\+998\d{9}$"`). docs/06-frontend-components.md:61 to'g'ri yozadi: payload `+998901234567` ga o'tkaziladi. Izoh ee33705 da almashtirilganda haqiqat teskari yozilgan; unga ishonib kimdir `phone` o'rniga `form.phone` yuborsa har saqlash 422 qaytaradi.

**Tekshiruv**

```
1) Frontend (haqiqiy zod, frontend/node_modules):
   $ node ph_tmp.mjs
   form.phone (displayed) = "+998 90 123-45-67"
   safeParse.success = true  payload phone = "+998901234567"
2) Backend (haqiqiy pydantic sxemalari):
   $ uv run python -c "...UserCreate/EmployeeCreate..."
   UserCreate '+998 90 123-45-67' -> REJECT: Value error, Telefon +998 bilan boshlanib, 9 ta raqamdan iborat bo'lsin
   EmployeeCreate '+998 90 123-45-67' -> REJECT: Value error, Telefon +998 bilan boshlanib, 9 ta raqamdan iborat bo'lsin
   UserCreate '+998901234567' -> OK '+998901234567'
   EmployeeCreate '+998901234567' -> OK '+998901234567'
Quote'lar grep -F bilan tasdiqlangan: PersonDialog.tsx:144 va docs/06-fronten
… (qisqartirildi)
```

**Taklif**

Izohning ikkinchi jumlasi hujjatdagi (docs/06:59-61) to'g'ri ta'rifga moslansin: maydon `formatUzPhone` bilan maskalanadi, payload esa o'sha maskadan `optionalFormattedPhoneSchema` orqali kanonik `+998901234567` ga o'tkaziladi (backend `^\+998\d{9}$` dan boshqasini rad etadi).

**Bog'liq fayllar:** `frontend/src/lib/validation.ts`, `backend/app/schemas/users.py`, `docs/06-frontend-components.md`

<sub>ID `L048:1` · ovoz 2 · rad 0</sub>

### 42. select.tsx comment claims dropdown-menu.tsx shares align="start"; it has no align default and its only caller passes align="end"

- **Joy:** `frontend/src/components/ui/select.tsx:50`
- **Turi:** Keraksiz/yolg'on izoh
- **Kod:** `// `dropdown-menu.tsx` ham `align="start"` va `sideOffset={4}`. Ilgari select`

**Nega tuzatish kerak**

The comment justifies SelectContent's defaults by asserting a project-wide floating-layer convention shared with popover.tsx and dropdown-menu.tsx. popover.tsx does back it up (align = "start", sideOffset = 4). dropdown-menu.tsx does not: DropdownMenuContent destructures only `sideOffset = 4` and never touches `align`, so it falls through to Radix's default, and the single call site in the app passes align="end" explicitly. A reader trusting this comment would believe dropdown menus are already start-aligned and either "fix" User.tsx to match, or propagate the wrong convention to a new dropdown.

**Tekshiruv**

```
$ grep -n "align\|sideOffset" components/ui/popover.tsx components/ui/dropdown-menu.tsx
components/ui/popover.tsx:18:  align = "start",
components/ui/popover.tsx:19:  sideOffset = 4,
components/ui/popover.tsx:26:        align={align}
components/ui/popover.tsx:27:        sideOffset={sideOffset}
components/ui/dropdown-menu.tsx:25:  sideOffset = 4,
components/ui/dropdown-menu.tsx:32:        sideOffset={sideOffset}

No `align` anywhere in dropdown-menu.tsx. Every DropdownMenuContent call site in the app (exactly one):
$ grep -rn "<DropdownMenuContent" -A3 --include=*.tsx .
./components/Sidebar/User.tsx:75:          <DropdownMenuContent
./components/Sidebar/User.tsx-76-            className="w-(-
… (qisqartirildi)
```

**Taklif**

Amend the comment to name only popover.tsx as the matching default, or add `align = "start"` to DropdownMenuContent so the stated convention is actually true. Do not silently change User.tsx's explicit align="end" — that one is deliberate for a right-side sidebar menu.

**Bog'liq fayllar:** `frontend/src/components/ui/dropdown-menu.tsx`, `frontend/src/components/ui/popover.tsx`, `frontend/src/components/Sidebar/User.tsx`

<sub>ID `L068:1` · ovoz 2 · rad 0</sub>

### 43. Unused module logger in giblab/ingest.py — `logging` imported and a logger built that nothing ever calls

- **Joy:** `backend/app/services/giblab/ingest.py:26`
- **Turi:** O'lik kod
- **Kod:** `logger = logging.getLogger(__name__)`

**Nega tuzatish kerak**

Neither `logger` nor any other logging call exists anywhere in app/services/giblab, and no module imports `logger` from ingest. Ruff cannot flag it (F401 is satisfied because `logging` IS used on line 26), so it stays forever. It is actively misleading here: ingest.py is exactly the module the readers flagged for 'silently returns None / silently truncates' paths, and the presence of a logger suggests those paths are logged when none of them are.

**Tekshiruv**

```
cd backend && grep -n "logger\|logging" app/services/giblab/*.py
  app/services/giblab/ingest.py:5:import logging
  app/services/giblab/ingest.py:26:logger = logging.getLogger(__name__)
(no other hit in the whole package)

Repo-wide importer check:
  grep -rn "giblab.ingest import\|giblab import ingest\|ingest.logger" --include=*.py .
  ./backend/app/api/routes/orders/files.py:21:from app.services.giblab.ingest import (
  ./backend/app/api/routes/orders/matrix.py:21:from app.services.giblab.ingest import park_tail, purge_replaced_scx, rebuild_order_scx, unpark_tail
The files.py import block (lines 21-30) lists only drop_stale_files, ingest_project, purge_replaced_scx, rebuild_order_scx, rest
… (qisqartirildi)
```

**Taklif**

Either drop `import logging` (line 5) and the `logger = logging.getLogger(__name__)` line (line 26), or actually use it on the two silent paths in this module — `rebuild_order_scx` returning None when the stored .project is gone from disk (line 406-407) and the `material_name=...[:150]` truncation (line 727).

**Bog'liq fayllar:** `backend/app/api/routes/orders/files.py`, `backend/app/api/routes/orders/matrix.py`

<sub>ID `L015:1` · ovoz 2 · rad 0</sub>

### 44. all_tasks is assigned twice with identical contents; the line-300 assignment is a shadowed no-op

- **Joy:** `backend/app/tasks/__init__.py:300`
- **Turi:** O'lik kod
- **Kod:** `all_tasks = [print_label, print_pachka_label, print_waste_label, print_badge]`

**Nega tuzatish kerak**

Module-level `all_tasks` is defined at line 300 and again, verbatim, at line 379. Only the last binding is what `app/core/worker.py:35` (`functions = all_tasks`) sees; the first is dead. Harmless today, but the next person who adds a task to whichever copy they find first gets it silently dropped if they edit line 300 only.

**Tekshiruv**

```
AST scan: [(300, 'all_tasks = [print_label, print_pachka_label, print_waste_label, print_badge]'), (379, 'all_tasks = [print_label, print_pachka_label, print_waste_label, print_badge]')] identical: True. `uv run ruff check --no-fix app/tasks/__init__.py` -> All checks passed (ruff does not flag module-level rebinding). `git log -S` shows the duplicate entered with 31d048d (feat(auth): log out after inactivity and close idle shifts). Only consumer: backend/app/core/worker.py:10,35.
```

**Taklif**

Delete the line-300 assignment and keep the single `all_tasks = [...]` at the end of the module (line 379). No doc change needed: docs/04-backend-data.md:608 already shows a single assignment.

**Bog'liq fayllar:** `backend/app/core/worker.py`

<sub>ID `L016:0` · ovoz 2 · rad 0 · 4 ta takror topilma birlashtirildi</sub>

### 45. all_tasks is assigned twice in backend/app/tasks/__init__.py; the first list is dead and silently overridden

- **Joy:** `backend/app/tasks/__init__.py:300`
- **Turi:** O'lik kod
- **Kod:** `all_tasks = [print_label, print_pachka_label, print_waste_label, print_badge]`

**Nega tuzatish kerak**

The identical module-level assignment appears at line 300 and again at line 379. Only the line-379 binding survives import, so the line-300 list is dead. It is also a live trap: app/core/worker.py:35 does `functions = all_tasks`, and anyone registering a new ARQ task by appending to the assignment they find first (line 300, which sits directly after the task definitions) would see the task silently dropped from the worker, because line 379 rebinds the name at the bottom of the file. ruff does not flag module-level rebinding (F811 covers imports and defs only).

**Tekshiruv**

```
grep -n "^all_tasks" backend/app/tasks/__init__.py ->
300:all_tasks = [print_label, print_pachka_label, print_waste_label, print_badge]
379:all_tasks = [print_label, print_pachka_label, print_waste_label, print_badge]

RAN (uv run --project backend python, importing the real module):
  all_tasks: ['print_label', 'print_pachka_label', 'print_waste_label', 'print_badge']
  all_tasks assignments: [300, 379]   (inspect.getsource line scan)

RAN the lint gate, so this is not something ruff already covers:
  cd backend && uv run ruff check --no-fix app/tasks/__init__.py  ->  All checks passed!  exit=0

Consumer: grep -rn all_tasks backend/app  ->  backend/app/core/worker.py:10 (import), backend/ap
… (qisqartirildi)
```

**Taklif**

Delete the assignment at line 300 and keep the single one at the end of the module. docs/02-backend-core.md:247 and docs/04-backend-data.md:648 both quote the one-line list, so no doc change is needed.

**Bog'liq fayllar:** `backend/app/core/worker.py`

<sub>ID `L072:0` · ovoz 2 · rad 0</sub>

### 46. tasks/__init__.py assigns all_tasks twice (line 300 and 379); the first assignment is dead

- **Joy:** `backend/app/tasks/__init__.py:300`
- **Turi:** O'lik kod
- **Kod:** `all_tasks = [print_label, print_pachka_label, print_waste_label, print_badge]`

**Nega tuzatish kerak**

Identical module-level assignment at lines 300 and 379. The second overwrites the first, so line 300 has no effect today; but if someone appends a task to one copy and not the other, the worker silently registers the wrong list (only the LAST assignment wins). It is also the exact list docs/02 line 247 quotes, so a future divergence would not be caught by reading the doc.

**Tekshiruv**

```
AST walk of backend/app/tasks/__init__.py printed: all_tasks assigned at line 300 ; all_tasks assigned at line 379. grep -nF of the assignment line -> 300, 379.
```

**Taklif**

Delete the line-300 assignment (keep the one at the end of the module, after close_idle_sessions, since worker.py imports all_tasks alongside the cron callables).

**Bog'liq fayllar:** `backend/app/core/worker.py`, `docs/02-backend-core.md`

<sub>ID `L078:4` · ovoz 2 · rad 0</sub>

### 47. CLAUDE.md bridge-agent'ni «yorliq chop etish + skan forvard» deydi — 2026-09-13 dan uchinchi roli bor: andon (Pico/kromka/rover USB)

- **Joy:** `CLAUDE.md:10`
- **Turi:** Hujjat kod bilan mos emas
- **Kod:** `Windows'da ishlaydigan `bridge-agent` (yorliq chop etish + skan forvard).`

**Nega tuzatish kerak**

Agent v1.7.0 endi stanok signal ustunini (Pico) USB orqali o'qiydi, kromka o'lchov stansiyasi va ROVER Pico protokolini gapiradi va hodisalarni `andon_event` ga jo'natadi — bu agent kodining uchdan bir qismi (`start_andon`, `_andon_loop`, `_kromka_line`, `_rover_line`, `andon_shipper`). CLAUDE.md ning yagona agent ta'rifi bu rolni umuman ko'rsatmaydi, ya'ni loyihaga kirayotgan odam agentni faqat printer ko'prigi deb tushunadi.

**Tekshiruv**

```
$ grep -n "AGENT_VERSION = " bridge-agent/agent.py
61:AGENT_VERSION = "1.7.0"
$ grep -n "^def start_andon\|^def _kromka_line\|^def _rover_line\|^async def andon_shipper" bridge-agent/agent.py
1445:def _kromka_line(data: dict[str, Any]) -> None:
1490:def _rover_line(data: dict[str, Any]) -> None:
1860:def start_andon() -> None:
1931:async def andon_shipper() -> None:
$ git log --format="%h %ad %s" --date=short -6 -- bridge-agent/agent.py
e234cf2 2026-09-21 feat(kromka): carry the jam event their v1.16 firmware introduced
c24c814 2026-09-20 feat(agent): speak the rover Pico's protocol instead of mistaking it for kromka
f48cba1 2026-09-19 fix(andon): ask the kromka Pico where it stands instead
… (qisqartirildi)
```

**Taklif**

10-qatorni uchinchi rol bilan to'ldirish, masalan: «(yorliq chop etish + skan forvard + andon: Pico/kromka/rover USB hodisalari)».

**Bog'liq fayllar:** `bridge-agent/agent.py`, `docs/12-oee.md`, `docs/07-infra-devops.md`

<sub>ID `L056:2` · ovoz 2 · rad 0</sub>

### 48. seed_defaults docstring, Organization model docstring, README, docs/01 and docs/07 still say seed_defaults creates the organization; it does not (migration 139…

- **Joy:** `backend/app/commands/seed_defaults.py:1`
- **Turi:** Hujjat kod bilan mos emas
- **Kod:** `"""Idempotent bootstrap: tashkilot, 9 ishlab chiqarish posti va post hisoblari.`

**Nega tuzatish kerak**

The module never imports or touches `Organization` (grep -c Organization -> 0) and its own line 160 comment says the org row is inserted by migration `1393a241b793` ("Tashkilot qatorini `1393a241b793` migratsiyasi qo'yadi"). Yet the module docstring on line 1 still lists `tashkilot` as something it bootstraps; `models/organization.py:8` says "Tenant. Bitta qator (\"Mebelix\"), `seed_defaults` yaratadi."; `backend/README.md:28` says "# default tashkilot + 9 post (ARRA..TMO)"; `docs/01-architecture.md:183` says "superuser + default org/postlar seed** (`seed_defaults`)"; and `docs/07-infra-devops.md` says on lines 201 and 205 that `seed_defaults` seeds "default organizatsiya" while two lines later (207) it says "default `organization` qatorini seed emas, **`1393a241b793` migratsiyasi** qo'yad
… (qisqartirildi)

**Tekshiruv**

```
grep -c Organization backend/app/commands/seed_defaults.py -> 0. grep -nF confirmed each quote verbatim: seed_defaults.py:1 '"""Idempotent bootstrap: tashkilot, 9 ishlab chiqarish posti va post hisoblari.'; seed_defaults.py:160 'Tashkilot qatorini `1393a241b793` migratsiyasi qo'yadi'; organization.py:8 '"""Tenant. Bitta qator ("Mebelix"), `seed_defaults` yaratadi.'; backend/README.md:28 '# default tashkilot + 9 post (ARRA..TMO)'; docs/01-architecture.md:183 'superuser + default org/postlar seed** (`seed_defaults`)'; docs/07-infra-devops.md:201 '`python -m app.commands.seed_defaults` — default organizatsiya, 9 ta ishlab chiqarish posti'; docs/07-infra-devops.md:205 '`python -m app.commands.se
… (qisqartirildi)
```

**Taklif**

Code is right; fix the five stale statements. seed_defaults.py:1 -> "Idempotent bootstrap: 9 ishlab chiqarish posti va post hisoblari." (tashkilot removed). models/organization.py:8 -> "`1393a241b793` migratsiyasi yaratadi (seed emas)". backend/README.md:28 -> "# 9 post (ARRA..TMO) + post hisoblari". docs/01-architecture.md:183 -> "birinchi superuser + postlar/post hisoblari seed" (org comes from the migration). docs/07-infra-devops.md:201 and :205 -> drop "default organizatsiya" from the seed_defaults description so they agree with line 207 and with docs/04 §5.2.

**Bog'liq fayllar:** `backend/app/models/organization.py:8`, `backend/README.md:28`, `docs/01-architecture.md:183`, `docs/07-infra-devops.md:201`, `docs/07-infra-devops.md:205`, `docs/07-infra-devops.md:207`, `docs/04-backend-data.md:551`, `backend/app/migrations/versions/1393a241b793_mes_domain_org_posts_machines_employees_.py:…`

<sub>ID `L005:0` · ovoz 2 · rad 0</sub>

### 49. WasteItem.sheet_no is the GLOBAL pattern number, but model comment and docs/04 both call it the per-material sheet number

- **Joy:** `backend/app/models/order.py:236`
- **Turi:** Hujjat kod bilan mos emas
- **Kod:** `sheet_no: Mapped[int] = mapped_column(kw_only=True) # material ichidagi list raqami`

**Nega tuzatish kerak**

ingest.py writes `sheet_no=int(sh.get("no") or 0)` where `sh["no"]` is `pattern_no`, which cutmap.py increments ONCE for the whole project (initialised before the `for cut in project.cut_ops` loop), not per material. So on an order with two sheet materials the second material's sheets are numbered 3, 4 — not 1, 2. Anyone reading the model comment or the docs/04 table to build a warehouse/atxot report (the table row itself says "Ombor moduli keyin shu jadval ustiga quriladi") would group or renumber atxot labels per material and get wrong sheet references on the shop floor. The frontend happens to be correct (`w.sheet_no === sheet?.no` in CutmapView.tsx:312 compares against the same global number), so only the written contract is wrong.

**Tekshiruv**

```
Ran a script that stubs decode_cs_blob and calls build_cutmap with TWO cut operations (two materials), two patterns each:

  cd backend && uv run python - (script builds ParsedProject with cut_ops MAT-A, MAT-B)
  MAT-A sheet 'no' values: [1, 2]
  MAT-B sheet 'no' values: [3, 4]

Numbering continues across materials. Source of that number:
  grep -Fn "pattern_no: int  # 1-based, global across materials" backend/app/services/giblab/cutmap.py
  38:    pattern_no: int  # 1-based, global across materials
and cutmap.py:150 `pattern_no = 0` sits OUTSIDE `for cut in project.cut_ops:` (line 154), incremented at line 166 `pattern_no += 1`.
Writer: backend/app/services/giblab/ingest.py:728 `sheet_no=in
… (qisqartirildi)
```

**Taklif**

Fix the written contract, not the code (the frontend already relies on the global number). Change the comment on backend/app/models/order.py:236 to e.g. `# kesish xaritasidagi GLOBAL list raqami (CutmapSheet.no), materiallar bo'ylab uzluksiz` and update the same parenthetical in the `WasteItem` row of docs/04-backend-data.md:114.

**Bog'liq fayllar:** `backend/app/services/giblab/ingest.py`, `backend/app/services/giblab/cutmap.py`, `docs/04-backend-data.md`, `frontend/src/components/Terminal/CutmapView.tsx`

<sub>ID `L015:0` · ovoz 2 · rad 0</sub>

### 50. Part.xnc_summary column comment still documents the retired `sides` key and omits the six keys ingest actually writes

- **Joy:** `backend/app/models/order.py:104`
- **Turi:** Hujjat kod bilan mos emas
- **Kod:** `# Merged XNC summary: {"bores": N, "edge_bores": N, "grooves": N, "mills": N, "sides": 1|2}`

**Nega tuzatish kerak**

The only in-code description of the xnc_summary JSONB shape names a key (`sides`) that no live writer produces and hides the six keys that downstream readers depend on (`groove_sides`, `mill_sides`, `groove_paths`, `mill_paths` feed labels.py, terminal.py and cutmap machining). docs/04-backend-data.md:110 already has the correct shape and says explicitly "`sides` esa ESKI kalit ... hozirgi ingest uni yozmaydi" - so the doc is right and the comment is wrong. Anyone changing ingest by reading the model comment would think `sides` is live and `*_paths` do not exist.

**Tekshiruv**

```
grep -Fn on the comment confirms it verbatim at backend/app/models/order.py:104.

$ grep -rn '"sides"' backend/app --include=*.py
(no output - no Python code writes or reads the "sides" key; the only occurrence in the repo is SQL text in migration 1cfd3b2182fc: `(p.xnc_summary->>'sides')::int = 2`)

What ingest actually writes, backend/app/services/giblab/ingest.py:591-608 - keys: bores, edge_bores, grooves, mills, groove_sides, mill_sides, groove_paths, mill_paths. Verbatim line 600:
                    "groove_sides": merged.machined_sides(pp.length, pp.width, tur="paz") if merged else [],

docs/04-backend-data.md:110 verbatim fragment: `xnc_summary` (`{"bores", "edge_bores", "grooves", "m
… (qisqartirildi)
```

**Taklif**

Replace the comment on backend/app/models/order.py:104 with the shape ingest.py:591-608 actually writes, and keep the `sides` note as history only (e.g. "`sides` - eski kalit, faqat 1cfd3b2182fc downgrade'ida o'qiladi"), matching docs/04-backend-data.md:110.

**Bog'liq fayllar:** `backend/app/services/giblab/ingest.py`, `docs/04-backend-data.md`, `backend/app/migrations/versions/1cfd3b2182fc_prisadka_one_scan_per_instance.py`

<sub>ID `L043:0` · ovoz 2 · rad 0</sub>

### 51. Dead pachka.shipped_at / PachkaStatus.SHIPPED: the promised drop migration was never written, and docs/09 plus the enum docstring still present shipped as a li…

- **Joy:** `backend/app/models/pachka.py:33`
- **Turi:** Hujjat kod bilan mos emas
- **Kod:** `shipped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None, kw_only=True)`

**Nega tuzatish kerak**

Nothing in the repo reads or writes shipped_at or PachkaStatus.SHIPPED - only the model column, the creating migration and the enum member exist. The column comment says the column will be dropped by a migration, but no such migration exists, while the precedent for exactly this cleanup does (c7f2d84a91b3_drop_dead_columns.py). Two places still describe the state as live: docs/09-mes-domain.md:20 gives the lifecycle as open->closed->shipped with shipped_at as an ordinary column, and the PachkaStatus docstring promises the transition to it. docs/04-backend-data.md:120 says the opposite, so the two docs disagree with each other and anyone extending packing would build on a state that can never be reached.

**Tekshiruv**

```
grep -rn for shipped_at and SHIPPED over *.py *.ts *.tsx *.md  ->  only:
  backend/app/migrations/versions/7e2e0ae9f7f3_pachka_va_pachka_item_jadvallari.py:38 (column creation)
  backend/app/models/enums.py:78:    SHIPPED = "shipped"
  backend/app/models/pachka.py:32-33 (declaration plus the dead-column comment)
  docs/04-backend-data.md:120 (marks it dead)
  docs/09-mes-domain.md:20 (presents it as live)
  no assignment, no query, no endpoint anywhere

grep -F verified, 1 hit each:
  backend/app/models/enums.py:73 -> Qadoq holati: ochiq (detal qo'shiladi) -> yopiq (chek chiqadi) -> jo'natildi.
  docs/09-mes-domain.md:20 -> `status` open→closed→shipped, `closed_at`/`shipped_at`
  docs/04-bac
… (qisqartirildi)
```

**Taklif**

Make the four places agree. Cheapest: fix the docs now - mark shipped as a dead state in docs/09-mes-domain.md:20 the way docs/04-backend-data.md:120 already does, and amend the PachkaStatus docstring (backend/app/models/enums.py:73) so it stops promising the transition. If the column really is to go, ship it as a NEW migration modelled on c7f2d84a91b3_drop_dead_columns.py dropping pachka.shipped_at, and remove the now-stale comment at pachka.py:31-32.

**Bog'liq fayllar:** `backend/app/models/enums.py`, `docs/09-mes-domain.md`, `docs/04-backend-data.md`, `backend/app/migrations/versions/c7f2d84a91b3_drop_dead_columns.py`

<sub>ID `L072:2` · ovoz 2 · rad 0</sub>

### 52. docs/01 says isAdmin guards (logs, printers); /printers is a bare redirect and isAdmin actually guards agents, logs, system-settings

- **Joy:** `docs/01-architecture.md:261`
- **Turi:** Hujjat kod bilan mos emas
- **Kod:** `(work-centers), `isAdmin` (logs, printers) — sidebar (`NAV_ITEMS.show`) ham`

**Nega tuzatish kerak**

frontend/src/routes/_layout/printers.tsx has no requireAccess: its beforeLoad only throws redirect({ to: "/agents" }) (renamed 2026-09-03 per its own comment). The isAdmin guard is on agents.tsx:69, logs.tsx:54 and system-settings.tsx:41; the sidebar likewise has MES agentlar (/agents), Loglar and Tizim sozlamalari (/system-settings) under show: isAdmin. The same doc already calls the page /agents at lines 348 and 404, so line 261 is internally inconsistent and omits system-settings entirely.

**Tekshiruv**

```
grep -rn beforeLoad/requireAccess frontend/src/routes: agents.tsx:69 beforeLoad: requireAccess(isAdmin); logs.tsx:54 beforeLoad: requireAccess(isAdmin); system-settings.tsx:41 beforeLoad: requireAccess(isAdmin); printers.tsx:6-8 beforeLoad: () => { throw redirect({ to: "/agents" }) }. AppSidebar.tsx:60-73: path /agents show: isAdmin; /logs show: isAdmin; /system-settings show: isAdmin.
```

**Taklif**

Change line 261 to isAdmin (agents, logs, system-settings) and note that /printers is a legacy redirect to /agents.

**Bog'liq fayllar:** `frontend/src/routes/_layout/printers.tsx`, `frontend/src/routes/_layout/agents.tsx`, `frontend/src/routes/_layout/system-settings.tsx`, `frontend/src/components/Sidebar/AppSidebar.tsx`

<sub>ID `L077:2` · ovoz 2 · rad 0</sub>

### 53. docs/01 has no trace of the andon path: POST /bridge-agents/andon missing from both bridge-agents auth summaries, agent ANDON_* envs missing, extra short-lived…

- **Joy:** `docs/01-architecture.md:252`
- **Turi:** Hujjat kod bilan mos emas
- **Kod:** ``POST /logs` agentning Bearer tokeni bilan, `GET /latest` va `GET /download``

**Nega tuzatish kerak**

docs/01 enumerates the bridge-agents router twice (lines 250-254 auth summary; lines 365-378 endpoint list) and the agent env list (lines 324-326) as complete sets, but since f98fd07 (2026-09-13) bridge_agents.py:413 has POST /andon (agent Bearer token via authorization Header), agent.py documents ANDON / ANDON_PORT / ANDON_TAKEOVER / ANDON_QUEUE_FILE envs, and services/andon.py opens its own AsyncRedis.from_url per call (lines 38 and 60), so the Yana to'rtta qisqa umrli klient census at line 168 (which the doc says must be included in the maxclients budget) is no longer four. docs/03:589 and docs/12:35 already document /andon; docs/01 is the stale side.

**Tekshiruv**

```
grep -n @router. backend/app/api/routes/bridge_agents.py -> 116 GET /, 126 PATCH /{id}, 176 POST /, 210 POST /{id}/code, 241 DELETE /{id}, 284 POST /pair, 359 POST /logs, 388 GET /{id}/logs, 413 POST /andon, 509 POST /scan, 623 GET /latest, 633 GET /download. grep -n from_url backend/app/services/andon.py -> 38, 60. bridge-agent/agent.py:25-29 lists ANDON, ANDON_PORT, ANDON_TAKEOVER, ANDON_QUEUE_FILE. grep -n /andon docs/*.md -> only docs/03:589 and docs/12:35; none in docs/01.
```

**Taklif**

Add POST /andon (agent Bearer) to lines 250-254 and 365-378, add the ANDON_* envs to lines 324-326, and update line 168 to include the per-call clients in services/andon.py (write_live from /andon, read_live from /machines/overview) or point to docs/12.

**Bog'liq fayllar:** `backend/app/api/routes/bridge_agents.py`, `backend/app/services/andon.py`, `bridge-agent/agent.py`, `docs/03-backend-api.md`, `docs/12-oee.md`

<sub>ID `L077:3` · ovoz 2 · rad 0</sub>

### 54. docs/01 section 5 document map ends at 11-detal-id-nomlash.md; 12-oee.md exists and is listed in docs/README.md

- **Joy:** `docs/01-architecture.md:558`
- **Turi:** Hujjat kod bilan mos emas
- **Kod:** `| [11-detal-id-nomlash.md](./11-detal-id-nomlash.md) | Detal ID nomlash qoidasi`

**Nega tuzatish kerak**

docs/12-oee.md is the primary source for the andon/downtime/work-schedule features that shipped in the last five merges, and docs/README.md:18 lists it, but the Hujjatlar xaritasi table in docs/01 (lines 547-558) stops at 11. Readers starting from the architecture overview cannot find the OEE doc.

**Tekshiruv**

```
ls docs -> 01..12 + README.md. grep -n 12-oee docs/01-architecture.md -> no match. docs/README.md:18 | [12-oee.md](12-oee.md) | OEE (Prisadka): ...
```

**Taklif**

Append a 12-oee.md row to the section 5 table mirroring docs/README.md:18.

**Bog'liq fayllar:** `docs/README.md`, `docs/12-oee.md`

<sub>ID `L077:4` · ovoz 2 · rad 0</sub>

### 55. Docs still describe a `agent_id` None -> shared `mes:print:queue` fallback that print_queue_key no longer has

- **Joy:** `docs/02-backend-core.md:252`
- **Turi:** Hujjat kod bilan mos emas
- **Kod:** `manzilli kalitni beradi: `agent_id` bo'lsa `mes:print:queue:{agent_id}`, bo'lmasa umumiy kalit.`

**Nega tuzatish kerak**

Code: `def print_queue_key(agent_id: int) -> str:` (backend/app/tasks/__init__.py:50) and `return f"{PRINT_QUEUE_KEY}:{agent_id}"` (line 65) — there is no branch for a missing agent_id; the docstring on the same function says `agent_id` MAJBURIY and that the None->general-key behaviour was removed. Three doc passages (docs/02-backend-core.md:252, docs/04-backend-data.md:590, docs/01-architecture.md:304-305) still tell the reader that an address-less job lands on the shared `mes:print:queue`. Someone reading the docs to debug a lost label would look at a key that can never be written. The code is the correct side here: docs/03-backend-api.md:462 (`manzilsiz job YARATILMAYDI — 422`) and docs/02:272 (`Umumiy PRINT_QUEUE_KEY endi ISHLATILMAYDI`) already state the new rule, so the three lines a
… (qisqartirildi)

**Tekshiruv**

```
Ran: from app.tasks import print_queue_key, PRINT_QUEUE_KEY; print(inspect.signature(print_queue_key)); print(print_queue_key(None)) -> `sig: (agent_id: int) -> str`, `None -> mes:print:queue:None`, `general key ever returned for None? False`. grep -F confirmed verbatim: docs/02-backend-core.md:252 `manzilli kalitni beradi: \`agent_id\` bo'lsa \`mes:print:queue:{agent_id}\`, bo'lmasa umumiy kalit.`; docs/04-backend-data.md:590 `(\`mes:print:queue:{agent_id}\`, manzilsiz bo'lsa \`mes:print:queue\`)`; docs/01-architecture.md:305 `bo'lmasa umumiy \`mes:print:queue\` (yangi job u yerga tushmaydi)`; backend/app/tasks/__init__.py:50 `def print_queue_key(agent_id: int) -> str:`; :65 `return f"{PRIN
… (qisqartirildi)
```

**Taklif**

Update the three doc lines to match the code: `print_queue_key(agent_id)` always returns `mes:print:queue:{agent_id}`; `agent_id` is mandatory (no default), an address-less job is never created (terminal/employees endpoints answer 422 first), and the bare `mes:print:queue` key is a legacy prefix only. E.g. docs/02:252 -> "`print_queue_key(agent_id)` HAR DOIM `mes:print:queue:{agent_id}` qaytaradi — `agent_id` majburiy, manzilsiz job yaratilmaydi."; docs/04:590 drop "manzilsiz bo'lsa `mes:print:queue`"; docs/01:304-305 drop the "bo'lmasa umumiy" clause.

**Bog'liq fayllar:** `backend/app/tasks/__init__.py`, `docs/04-backend-data.md`, `docs/01-architecture.md`, `docs/03-backend-api.md`

<sub>ID `L016:1` · ovoz 2 · rad 0</sub>

### 56. docs/02 line 80 importer lists for upload_root() and TASHKENT_TZ are stale (matrix.py, machines.py, crud/orders.py, services andon/availability/excel missing)

- **Joy:** `docs/02-backend-core.md:80`
- **Turi:** Hujjat kod bilan mos emas
- **Kod:** `Uni to'rtta route moduli import qiladi: `orders/files.py`, `orders/survey.py`, `orders/lifecycle.py` (o'chirishda fayllarni unlink qiladi), `terminal.py`.`

**Nega tuzatish kerak**

The doc enumerates exactly four upload_root() importers and eight TASHKENT_TZ users. On disk orders/matrix.py:14 also imports upload_root (a fifth route module), and TASHKENT_TZ is additionally used by routes/machines.py, crud/orders.py, services/andon.py, services/availability.py, services/excel.py (the OEE/availability work from the last few commits). A wrong count invites the conclusion that the missing modules do not touch the upload dir or local timezone.

**Tekshiruv**

```
grep -rn upload_root backend/app --include=*.py | grep import -> orders/files.py:12, orders/lifecycle.py:18, orders/matrix.py:14 (from app.core.config import upload_root), orders/survey.py:12, terminal.py:13 = 5 route modules. grep -rln TASHKENT_TZ backend/app -> audit.py, machines.py, orders/_common.py, reports.py, scans.py, tablo.py, config.py, crud/orders.py, services/andon.py, services/availability.py, services/excel.py, services/labels.py, services/scanning.py, tasks/__init__.py.
```

**Taklif**

Replace to'rtta with beshta and add orders/matrix.py; extend the TASHKENT_TZ list with machines.py, crud/orders.py, services/andon.py, services/availability.py, services/excel.py — or drop the exhaustive lists so they stop rotting.

**Bog'liq fayllar:** `backend/app/api/routes/orders/matrix.py`, `backend/app/api/routes/machines.py`, `backend/app/services/availability.py`, `backend/app/services/excel.py`, `backend/app/services/andon.py`, `backend/app/crud/orders.py`

<sub>ID `L078:2` · ovoz 2 · rad 0</sub>

### 57. docs/02 verify_token signature omits the verify_exp keyword used by the WS re-auth path

- **Joy:** `docs/02-backend-core.md:179`
- **Turi:** Hujjat kod bilan mos emas
- **Kod:** `- `verify_token(token, expected_token_type) -> TokenData | None` — decode qiladi`

**Nega tuzatish kerak**

security.py:74 is def verify_token(token, expected_token_type, *, verify_exp: bool = True); the flag exists so routes/ws.py (via deps.resolve_user(..., verify_exp=False)) can re-check an open socket token for revocation without failing on the 30-minute access expiry. The doc security section describes neither the parameter nor this WS use, so the one non-default caller is invisible to a reader of the core doc.

**Tekshiruv**

```
grep -rn verify_exp backend/app -> core/security.py:74 (signature), api/deps.py:27-29 (resolve_user forwards it), api/routes/ws.py:59: return await resolve_user(db, raw_token, verify_exp=False) is not None.
```

**Taklif**

Document the signature as verify_token(token, expected_token_type, *, verify_exp=True) and add: verify_exp=False — faqat imzo/tur, muddat emas; routes/ws.py ochiq soketni bekor qilinganlik bo'yicha qayta tekshirishda ishlatadi.

**Bog'liq fayllar:** `backend/app/core/security.py`, `backend/app/api/deps.py`, `backend/app/api/routes/ws.py`

<sub>ID `L078:3` · ovoz 2 · rad 0</sub>

### 58. docs/02 rate_limit.py section omits that rate_limiter.client is the shared Redis client for refresh-jti tombstones and user activity (login.py, users.py)

- **Joy:** `docs/02-backend-core.md:366`
- **Turi:** Hujjat kod bilan mos emas
- **Kod:** `**Maqsadi:** Redis asosidagi IP-darajali rate limiting — ham client holder, ham FastAPI dependency.`

**Nega tuzatish kerak**

The RateLimiter class docstring (rate_limit.py:13-14) says it holds the app-wide Redis client used by RateLimit AND by login.py refresh-token jti tombstones. login.py:80-89 uses rate_limiter.client.set(_USED_JTI_PREFIX + jti, ..., nx=True) for one-time refresh tokens, and login.py:145/352/385 + users.py:129 pass rate_limiter.client to touch_activity/last_activity (which feeds close_idle_sessions). The doc dependencies paragraph for this module lists only the two RateLimit instances, so a reader would think replacing or closing this client affects rate limiting alone, when it also breaks refresh-token rotation and idle-session detection.

**Tekshiruv**

```
grep -rn rate_limiter backend/app | grep -v core/ -> login.py:20 import; :80-82 rate_limiter.client.set(_USED_JTI_PREFIX + jti, 1, ex=max_age, nx=True); :86-89 same for mark-used; :145,:352 touch_activity(rate_limiter.client, user.id); :385 last_activity(rate_limiter.client, user.id); users.py:129 touch_activity(rate_limiter.client, current_user.id). rate_limit.py:13 docstring: Ilovaning umumiy Redis mijozini ushlab turadi: RateLimit va login.py dagi
```

**Taklif**

Extend line 366 and the dependencies paragraph: rate_limiter.client — ilovaning umumiy Redis mijozi: routes/login.py refresh-token jti qabrtoshlari (auth:refresh:used:*) va services/activity.py touch_activity/last_activity (login.py, users.py) ham shu mijozdan foydalanadi.

**Bog'liq fayllar:** `backend/app/core/utils/rate_limit.py`, `backend/app/api/routes/login.py`, `backend/app/api/routes/users.py`

<sub>ID `L078:5` · ovoz 2 · rad 0</sub>

### 59. docs/07 'new agent version' recipe installs unpinned pyinstaller, contradicting ci.yml/README pin and docs/07's own 'QOTIRILGAN' statement

- **Joy:** `docs/07-infra-devops.md:395`
- **Turi:** Hujjat kod bilan mos emas
- **Kod:** `pip install "websockets>=14" pywin32 pillow pynput pystray pyserial pyinstaller`

**Nega tuzatish kerak**

ci.yml:165 pins `"pyinstaller==6.22.2"` and bridge-agent/README.md:123 has the identical pinned line. docs/07 line 131 itself states "**PyInstaller versiyasi CI'da qotirilgan** (`pyinstaller==6.22.2`): 6.22 bootloader'i onefile bola jarayonida OTA exe'ni tekshira boshladi ... va `.bat` orqali qayta ishga tushgan agent ... bilan yiqildi". The recipe at line 395 (section 'Agentning yangi versiyasini chiqarish') tells a developer to `pip install ... pyinstaller` with no pin, i.e. the latest release — exactly the situation the doc warns must be re-tested on the shop-floor PC before adoption. The two lines in the same doc disagree; the code (ci.yml + README) is the correct side.

**Tekshiruv**

```
grep -nF 'pyinstaller==6.22.2' .github/workflows/ci.yml bridge-agent/README.md docs/07-infra-devops.md -> ci.yml:165, README.md:123, docs/07:131 all pinned. docs/07:395 is the only build line without the pin. ci.yml:160-163 comment verbatim: "pyinstaller QOTIRILGAN: 6.22 bootloader'i bola jarayonda ota exe'ni tekshira boshladi va bat orqali qayta ishga tushgan agent yiqildi".
```

**Taklif**

Change docs/07-infra-devops.md line 395 to the same pinned line used by ci.yml:165 and README.md:123: pip install "websockets>=14" pywin32 pillow pynput pystray pyserial "pyinstaller==6.22.2"

**Bog'liq fayllar:** `.github/workflows/ci.yml`, `bridge-agent/README.md`

<sub>ID `L000:1` · ovoz 4 · rad 0</sub>

### 60. docs/07 .gitignore section claims `**/lib/` + `!frontend/src/lib/` and `.coverage` rules that were deleted in 97e7beb

- **Joy:** `docs/07-infra-devops.md:523`
- **Turi:** Hujjat kod bilan mos emas
- **Kod:** `E'tiborli nuqta: `**/lib/` ignore qilinadi, lekin `!frontend/src/lib/` istisno (shadcn util katalogi).`

**Nega tuzatish kerak**

The doc presents two ignore rules as notable facts; neither exists in .gitignore any more. Same paragraph also lists `.coverage` under 'test/lint cache' which was removed in the same commit. A reader adding a `lib/` directory would expect it to be ignored and it will not be.

**Tekshiruv**

```
grep -n lib .gitignore -> (no output); grep -n coverage .gitignore -> (no output). git show 97e7beb -- .gitignore: `-**/lib/`, `-**/lib64/`, `-!frontend/src/lib/`, `-.coverage`, `-.coverage.*`, `-htmlcov/`. Commit message: '.gitignore: the coverage entries (no coverage tool in the repo) and the `**/lib/` + `!frontend/src/lib/` pair, whose only real target lives under the already-ignored .venv.' Doc also says at the same line: "test/lint cache (`.mypy_cache`, `.ruff_cache`, `.coverage`)" -> `.coverage` absent.
```

**Taklif**

Delete the `**/lib/` / `!frontend/src/lib/` sentence and drop `.coverage` from the cache list in docs/07:523.

**Bog'liq fayllar:** `.gitignore`

<sub>ID `L083:1` · ovoz 2 · rad 0</sub>

### 61. docs/07 auth classification of bridge-agents endpoints omits `POST /andon` (agent-token endpoint)

- **Joy:** `docs/07-infra-devops.md:290`
- **Turi:** Hujjat kod bilan mos emas
- **Kod:** `Qolgan `bridge-agents` endpointlari (`GET /`, `POST /`, `PATCH /{id}`, `POST /{id}/code`, `DELETE /{id}`, `GET /{id}/logs`) `AdminUser` bilan yopiq.`

**Nega tuzatish kerak**

The paragraph partitions every bridge-agents route into open / agent-token / admin. `POST /andon` (added in 079993d) is in none of the three groups, so the 'remaining endpoints are admin-only' statement is an incomplete enumeration of the router's auth surface. The doc does mention `/andon` later (line 383, agent env table) but not in the security classification.

**Tekshiruv**

```
grep -n '@router\.' backend/app/api/routes/bridge_agents.py -> 13 routes incl. `413:@router.post("/andon", response_model=AndonPushResult, operation_id="push_andon_events")`; body at :426 `agent = await _agent_by_token(db, authorization)` (same helper as /scan and /logs). Doc line 290 lists /pair, /scan, /logs, /latest, /download and six admin routes = 12 of 13.
```

**Taklif**

Extend docs/07:290: "`POST /scan` (skan-forvard), `POST /logs` (log yuborish) va `POST /andon` (signal ustuni hodisalari) agent tokeni bilan ishlaydi".

**Bog'liq fayllar:** `backend/app/api/routes/bridge_agents.py`

<sub>ID `L083:3` · ovoz 2 · rad 0</sub>

### 62. docs/08 claims a 'complete' list of agent env vars but omits the four ANDON_* vars agent.py reads since 079993d

- **Joy:** `docs/08-packages.md:118`
- **Turi:** Hujjat kod bilan mos emas
- **Kod:** `Agent env'lari to'liq ro'yxati — `MES_URL`, `BRIDGE_TOKEN`, `PRINTER_NAME` (ixtiyoriy), `QUEUE_FILE`, `SCAN_FORWARD``

**Nega tuzatish kerak**

'to'liq ro'yxati' (complete list) is explicitly claimed. agent.py also reads ANDON, ANDON_PORT, ANDON_TAKEOVER, ANDON_QUEUE_FILE; docs/07:384-385 and bridge-agent/README.md:89-90 document them.

**Tekshiruv**

```
grep -n 'os.environ.get' bridge-agent/agent.py -> 746: ANDON = os.environ.get("ANDON", "1") != "0" / 747: ANDON_PORT = os.environ.get("ANDON_PORT", "") / 748: ANDON_TAKEOVER = os.environ.get("ANDON_TAKEOVER", "1") != "0" / 749: ANDON_QUEUE_FILE = Path(os.environ.get("ANDON_QUEUE_FILE") or (CONFIG_DIR / "andon-queue.jsonl"))
docs/07-infra-devops.md:384 | `ANDON_PORT` | ... ; :385 | `ANDON_TAKEOVER` | ...
```

**Taklif**

Either drop the word 'to'liq' and point to the env table in docs/07 / bridge-agent/README.md, or append `ANDON`, `ANDON_PORT`, `ANDON_TAKEOVER`, `ANDON_QUEUE_FILE`.

**Bog'liq fayllar:** `bridge-agent/agent.py`, `docs/07-infra-devops.md`, `bridge-agent/README.md`

<sub>ID `L084:3` · ovoz 2 · rad 0</sub>

### 63. docs/08 quotes a hatch wheel key include = ["app/"] that has never existed in backend/pyproject.toml (it is packages = ["app"])

- **Joy:** `docs/08-packages.md:135`
- **Turi:** Hujjat kod bilan mos emas
- **Kod:** `wheel'ga esa `[tool.hatch.build.targets.wheel] include = ["app/"]` orqali tushadi`

**Nega tuzatish kerak**

The quoted key is wrong; pyproject.toml line 49 reads packages = ["app"] and has since the initial commit 569fba5. Conclusion (assets ship in the wheel) still holds since hatch packages copies the whole package directory, but the doc gives a false verbatim snippet.

**Tekshiruv**

```
grep -nF 'packages = ["app"]' backend/pyproject.toml -> 49:packages = ["app"]. git log -S -- backend/pyproject.toml -> 569fba5 2026-07-05 initial (only commit touching it). grep -c 'include = ' backend/pyproject.toml -> 0
```

**Taklif**

Replace with `[tool.hatch.build.targets.wheel] packages = ["app"]`.

**Bog'liq fayllar:** `backend/pyproject.toml`

<sub>ID `L084:5` · ovoz 2 · rad 0</sub>

### 64. docs/08 lists types-openpyxl 3.1.5.20260807 as the lock version; uv.lock has 3.1.5.20260827 since the 2026-09-02 upgrade the doc itself describes

- **Joy:** `docs/08-packages.md:56`
- **Turi:** Hujjat kod bilan mos emas
- **Kod:** `dev'da `types-openpyxl` 3.1.5.20260807`

**Nega tuzatish kerak**

The sentence explicitly claims 'lock versiyalari bilan' (with lock versions). The 2026-09-02 uv lock --upgrade (85dd7c7) bumped it; the doc's 2026-09-02 entry (line 14) updated other versions but missed this one. Same commit also dropped packaging from the lock (60 -> 59 packages), which the 2026-09-02 entry does not mention.

**Tekshiruv**

```
tomllib parse of backend/uv.lock: types-openpyxl 3.1.5.20260827; uv.lock package count: 59. git log -S'3.1.5.20260827' -- backend/uv.lock -> 85dd7c7 2026-09-02 chore(deps): latest within the existing constraints. lock diff a0c506e -> HEAD: 60 59 removed: {'packaging'} added: set()
```

**Taklif**

Update to 3.1.5.20260827; optionally note in the 2026-09-02 entry that packaging left the lock (60 -> 59).

**Bog'liq fayllar:** `backend/uv.lock`

<sub>ID `L084:6` · ovoz 2 · rad 0</sub>

### 65. docs/08 says labels.py has two module-level helpers (_n, _bw); after the September label rewrites it has eight

- **Joy:** `docs/08-packages.md:72`
- **Turi:** Hujjat kod bilan mos emas
- **Kod:** `Modul darajasida ikkita yordamchi bor`

**Nega tuzatish kerak**

labels.py now has _teksturasiz, _canvas (the 80x60 mm blank and draw.fontmode = "1" moved here), _font (font search + load_default fallback), _paste_logo, _to_1bit_png, _instagram_glyph in addition to _n/_bw. The doc's account of where fontmode/fonts/logo/1-bit conversion live (lines 68-72) describes them as inline in each render function, which is no longer the structure.

**Tekshiruv**

```
grep -cE '^def _' backend/app/services/labels.py -> 8; lines 122 _n, 129 _bw, 159 _teksturasiz, 171 _canvas, 182 _font, 194 _paste_logo, 211 _to_1bit_png, 730 _instagram_glyph. labels.py:178 draw.fontmode = "1" inside _canvas(); :191 return ImageFont.load_default() inside _font(); _paste_logo called at 254, 760, 827 (not from render_badge_png at 867 — 'beyjik logosiz' still true)
```

**Taklif**

Rewrite the helper sentence: eight private module-level helpers — _n, _bw, _teksturasiz, _canvas (blank + fontmode), _font (TTF search, load_default fallback), _paste_logo, _to_1bit_png, _instagram_glyph — and point the fontmode/font/1-bit statements at those helpers.

**Bog'liq fayllar:** `backend/app/services/labels.py`

<sub>ID `L084:7` · ovoz 2 · rad 0</sub>

### 66. docs/08 refers to the admin 'Printerlar' page; the page was renamed to /agents with sidebar title 'MES agentlar' in 1e26ffb (2026-09-03)

- **Joy:** `docs/08-packages.md:177`
- **Turi:** Hujjat kod bilan mos emas
- **Kod:** `admin paneldagi Printerlar sahifasidagi`

**Nega tuzatish kerak**

No 'Printerlar' page or string exists in frontend/src any more; the route is _layout/agents.tsx and the sidebar entry is 'MES agentlar'. A reader will not find the page under the documented name.

**Tekshiruv**

```
grep -rn 'Printerlar' frontend/src --include=*.tsx -> (no matches). frontend/src/components/Sidebar/AppSidebar.tsx:63 title: "MES agentlar", :64 path: "/agents". git log -> 1e26ffb 2026-09-03 refactor(agents): rename the /printers route to /agents
```

**Taklif**

Change to: admin paneldagi «MES agentlar» (`/agents`) sahifasidagi.

**Bog'liq fayllar:** `frontend/src/routes/_layout/agents.tsx`, `frontend/src/components/Sidebar/AppSidebar.tsx`

<sub>ID `L084:8` · ovoz 2 · rad 0</sub>

### 67. docs/09 §1 says 19 jadval and 5 jadval machine_id FK; on disk there are 24 BaseModel tables and 7 machine_id FKs (andon_event, downtime, downtime_reason, syste…

- **Joy:** `docs/09-mes-domain.md:7`
- **Turi:** Hujjat kod bilan mos emas
- **Kod:** `19 jadval, hammasi `BaseModel` (ID + timestamps + soft-delete):`

**Nega tuzatish kerak**

§1 presents itself as the full data-model list. Four tables added 2026-09-13..18 (system_setting 7e6946ebd00d, andon_event, downtime, downtime_reason) are absent from the table and the count, and line 49 (5 jadval `machine_id` FK bilan bog'langan) is now 7. docs/04 and docs/12 document the new tables, so this is a stale summary rather than a missing spec. The doc was touched 2026-09-18 (ef4d6c5) without updating the counts.

**Tekshiruv**

```
grep -n '^class .*(BaseModel' backend/app/models/*.py | wc -l -> 24 (incl. User, which the doc lists separately at line 27)
New: models/andon.py:11 AndonEvent, models/downtime.py:10 DowntimeReason, :28 Downtime, models/setting.py:7 SystemSetting
grep -rn ForeignKey("machine.id") backend/app/models/*.py -> andon.py:35, bridge_agent.py:29, downtime.py:45, order.py:183, scan.py:20, scan.py:56, user.py:42 (7)
git log --diff-filter=A: setting.py/andon.py 2026-09-13 (a8d1662, f98fd07), downtime.py 2026-09-18 (71ff637)
grep -nF of the line-49 sentence -> 49
```

**Taklif**

Update line 7 to the real count and add rows for system_setting, andon_event, downtime, downtime_reason pointing at docs/04 and docs/12; change 5 jadval at line 49 to 7.

**Bog'liq fayllar:** `backend/app/models/andon.py`, `backend/app/models/downtime.py`, `backend/app/models/setting.py`, `docs/04-backend-data.md`, `docs/12-oee.md`

<sub>ID `L085:1` · ovoz 2 · rad 0</sub>

### 68. docs/09 §6 reports row lists four endpoints but GET /reports/machine-time exists (cited by the same doc at line 587); §6 has no row for the settings router, te…

- **Joy:** `docs/09-mes-domain.md:415`
- **Turi:** Hujjat kod bilan mos emas
- **Kod:** `| `reports` | `/productivity`, `/orders`, `/materials` (+`?format=xlsx`), `/dashboard` | manager/director/admin |`

**Nega tuzatish kerak**

§6 is titled API xaritasi and docs/README.md maps 09 as the owner of the API map. The reports row omits /machine-time while line 587 of the same file says GET /reports/machine-time ishlatadi. The bridge-agents row (line 417) enumerates every route except POST /andon; the settings router (GET /, GET/PUT /work-schedule, PUT /{key}) and terminal /downtime-reasons, /downtimes/pending, /downtimes/{id}/reason, /downtimes/lock are not in the map at all. docs/03 and docs/12 cover them, so this is an internally inconsistent summary, not an undocumented API.

**Tekshiruv**

```
spine contract.json backend_routes reports.py: GET /productivity, GET /machine-time, GET /orders, GET /materials, GET /dashboard
bridge_agents.py includes POST /andon -> push_andon_events
settings.py: GET /, GET /work-schedule, PUT /work-schedule, PUT /{key}
grep -n @router. backend/app/api/routes/downtimes.py -> 43 /downtime-reasons, 59 /downtimes/pending, 95 /downtimes/{downtime_id}/reason, 124 /downtimes/lock
grep -nF 'GET /reports/machine-time' docs/09-mes-domain.md -> 587
docs/README.md:15 -> | 09-mes-domain.md | ... API xaritasi, frontend tuzilishi |
```

**Taklif**

Add /machine-time to the reports row; add /andon to the bridge-agents row; add rows for settings and the terminal downtimes routes (or a one-line pointer to docs/12 §4).

**Bog'liq fayllar:** `backend/app/api/routes/reports.py`, `backend/app/api/routes/settings.py`, `backend/app/api/routes/downtimes.py`, `backend/app/api/routes/bridge_agents.py`, `docs/12-oee.md`

<sub>ID `L085:2` · ovoz 2 · rad 0</sub>

### 69. docs/09 §6 audit-logs row enumerates 13 log_action(module=...) values; code also emits downtime and settings

- **Joy:** `docs/09-mes-domain.md:416`
- **Turi:** Hujjat kod bilan mos emas
- **Kod:** `Modullar backend `log_action(module=…)` qiymatlari (scan, print, sessions, orders, pachka, tmo, bridge_agents, employees, users, clients, machines, posts, auth)`

**Nega tuzatish kerak**

The list is presented as the exhaustive set of modules the Loglar page shows as tabs (frontend builds tabs from summary), so the page will show downtime and settings tabs the doc does not mention.

**Tekshiruv**

```
grep -rhoE module="[a-z_]+" backend/app --include=*.py | sort -u -> auth, bridge_agents, clients, downtime, employees, machines, orders, pachka, posts, print, scan, scans, sessions, settings, tmo, users
grep -rn module="downtime" / module="settings" backend/app -> downtimes.py:111,151; settings.py:51,80,112,160,183
```

**Taklif**

Append downtime, settings to the list at line 416 (and confirm MODULE_LABELS has Uzbek labels for both).

**Bog'liq fayllar:** `backend/app/api/routes/downtimes.py`, `backend/app/api/routes/settings.py`

<sub>ID `L085:3` · ovoz 2 · rad 0</sub>

### 70. docs/10 cites stage_sides() twice; the method was renamed to prisadka_passes in 4dda538 and no stage_sides exists in the code

- **Joy:** `docs/10-giblab-reference.md:336`
- **Turi:** Hujjat kod bilan mos emas
- **Kod:** `kod 6 — PRISADKA qadamiga qo'shiladi (`stage_sides()`); frezer stanogi kerak bo'lsa ROVER ni`

**Nega tuzatish kerak**

A reader following the reference finds nothing. docs/04:172 (ParsedPart.stage_sides) and docs/09:91 (ParsedPart.stage_sides()) have the same stale name; migration a7c419e0b3d5 docstring also mentions it but migrations are frozen.

**Tekshiruv**

```
grep -rn stage_sides backend/app -> only migrations/versions/a7c419e0b3d5_*.py:7 (docstring). git show 4dda538 models.py: `-    def stage_sides(self) -> dict[PostCode, int]:` / `+    def prisadka_passes(self) -> int:` (2026-08-29). models.py:358 `def prisadka_passes(self) -> int:`.
```

**Taklif**

Replace stage_sides() with ParsedPart.prisadka_passes() at docs/10:336 and :612, docs/04:172, docs/09:91.

**Bog'liq fayllar:** `docs/04-backend-data.md`, `docs/09-mes-domain.md`, `backend/app/services/giblab/models.py`

<sub>ID `L086:3` · ovoz 2 · rad 0</sub>

### 71. docs/10 5 says LabelData.thickness is loaded but unused; the field was deleted in 4dda538

- **Joy:** `docs/10-giblab-reference.md:668`
- **Turi:** Hujjat kod bilan mos emas
- **Kod:** `**Qalinlik yorliqda chizilmaydi** — `LabelData.thickness` yuklanadi (`labels.py`), lekin`

**Nega tuzatish kerak**

The conclusion (thickness is not printed) is still true, but the stated mechanism is not: LabelData (labels.py:23-45) has no thickness field and load_label_data no longer reads part.thickness. The sentence describes dead code that the 2026-08-29 audit cleanup removed.

**Tekshiruv**

```
grep -n thickness backend/app/services/labels.py -> no match. git show 4dda538 -- labels.py: `-    thickness: float | None` and `-        thickness=part.thickness,`. labels.py:23 class LabelData fields: qr_text, part_code, part_name, project_name, material, length, width, count, instance_no, edges, xnc_summary, label_num, printed_at, holes, texture, route_codes, product_name.
```

**Taklif**

Rewrite: Qalinlik yorliqqa umuman yuklanmaydi (LabelData da maydon yo'q, 2026-08-29 da olib tashlandi): o'lcham qatori faqat uzunlik x kenglik = soni. Qalinlik bazada va detallar matritsasida qoladi.

**Bog'liq fayllar:** `backend/app/services/labels.py`

<sub>ID `L086:5` · ovoz 2 · rad 0</sub>

### 72. docs/10 8 attributes write_and_register_scx and park_tail/unpark_tail imports to orders/files.py; files.py imports neither

- **Joy:** `docs/10-giblab-reference.md:880`
- **Turi:** Hujjat kod bilan mos emas
- **Kod:** ``write_and_register_scx`, `snapshot_custom_routes`, `restore_custom_routes`,`

**Nega tuzatish kerak**

files.py imports drop_stale_files, ingest_project, purge_replaced_scx, rebuild_order_scx, restore_custom_routes, restore_stale_files, snapshot_custom_routes, wipe_previous_parse. park_tail/unpark_tail are imported only by orders/matrix.py; write_and_register_scx has no importer outside ingest.py (called by ingest_project and rebuild_order_scx). The list also omits restore_stale_files, rebuild_order_scx, purge_replaced_scx that files.py does import.

**Tekshiruv**

```
files.py:21-30 `from app.services.giblab.ingest import (drop_stale_files, ingest_project, purge_replaced_scx, rebuild_order_scx, restore_custom_routes, restore_stale_files, snapshot_custom_routes, wipe_previous_parse,)`. grep -rn for write_and_register_scx and park_tail across backend/app filtered to import lines -> only matrix.py:21 `from app.services.giblab.ingest import park_tail, purge_replaced_scx, rebuild_order_scx, unpark_tail`.
```

**Taklif**

List the actual files.py imports and say park_tail/unpark_tail are consumed by orders/matrix.py (and internally by restore_custom_routes), write_and_register_scx only inside ingest.py.

**Bog'liq fayllar:** `backend/app/api/routes/orders/files.py`, `backend/app/api/routes/orders/matrix.py`, `backend/app/services/giblab/ingest.py`

<sub>ID `L086:6` · ovoz 2 · rad 0</sub>

### 73. docs/11 lists a KromkaView Jarayonda panel as a place showing qr_text directly; that panel was deleted in f52da85 and the remaining chips show only the instanc…

- **Joy:** `docs/11-detal-id-nomlash.md:142`
- **Turi:** Hujjat kod bilan mos emas
- **Kod:** ``KromkaView` ning «Jarayonda» paneli va O'Z skani banneri`

**Nega tuzatish kerak**

Commit f52da85 (2026-09-03, kromka - one full-width table instead of a side panel) removed the side panel; what remains is a header badge rendering a count (Jarayonda {inProgressCount}), not a QR. The per-copy chips render the instance number with qr_text only in title= - which the doc itself states in exception (a) of the very same table cell. So the cell lists KromkaView both as a direct-qr_text place and as an exception to it. f52da85 updated docs/06 but not docs/11.

**Tekshiruv**

```
Code:
  frontend/src/components/Terminal/KromkaView.tsx:301  comment explaining the removal of the side panel
  frontend/src/components/Terminal/KromkaView.tsx:340  `              Jarayonda {inProgressCount}`   (header badge - a count, not a QR)
  frontend/src/components/Terminal/KromkaView.tsx:451  `                              title={i.qr_text}`
  frontend/src/components/Terminal/KromkaView.tsx:463  instance number chip, no QR
$ grep -n qr_text frontend/src/components/Terminal/KromkaView.tsx
  269:      const inst = p.instances.find((i) => i.qr_text === qr)
  451:                              title={i.qr_text}
(no other qr_text render in the file)
$ git log -S "Ilgari o'ng tomonda" --onel
… (qisqartirildi)
```

**Taklif**

Remove the KromkaView Jarayonda panel from the direct-qr_text list at docs/11:142; KromkaView is already correctly covered by exception (a) in the same cell.

**Bog'liq fayllar:** `frontend/src/components/Terminal/KromkaView.tsx`, `docs/06-frontend-components.md`

<sub>ID `L087:3` · ovoz 2 · rad 0</sub>

### 74. deploy.sh's root-cause comment still names the old FILE bind-mount; compose mounts the DIRECTORY since e1259f2

- **Joy:** `scripts/deploy.sh:85`
- **Turi:** Hujjat kod bilan mos emas
- **Kod:** `# Caddyfile bind-mount (`./caddy/Caddyfile:/etc/caddy/Caddyfile:ro`), ya'ni`

**Nega tuzatish kerak**

docker-compose.prod.yml:155 mounts the DIRECTORY (`- ./caddy:/etc/caddy:ro`), and that is a deliberate fix: compose lines 150-155 and docs/07-infra-devops.md:93 both state `KATALOG mount, fayl EMAS` because a file-mount pinned Caddy to a stale inode for 3 weeks in prod. deploy.sh:85 still documents the abandoned file-mount form as current. A maintainer reading deploy.sh to understand why `caddy reload` is mandatory is told the exact configuration the team removed, and could 'restore' it — reintroducing the stale-inode outage. The reload step itself is still correct; only the stated mount form is wrong.

**Tekshiruv**

```
git log --oneline -S 'caddy:/etc/caddy:ro' -- docker-compose.prod.yml  ->  e1259f2 fix(caddy): Caddyfile katalog sifatida mount qilinadi
git show e1259f2 --stat  ->  docker-compose.prod.yml | 7 ++++++-  (1 file changed; scripts/deploy.sh NOT touched)
git log --oneline -S 'Caddyfile bind-mount' -- scripts/deploy.sh  ->  0e8734c fix(deploy): Caddy konfig o'zgarishlari prodga tushmasdi  (commit body: "Sabab: Caddyfile bind-mount (`./caddy/Caddyfile:/etc/caddy/Caddyfile:ro`)")
grep -n -F './caddy:/etc/caddy:ro' docker-compose.prod.yml  ->  155:      - ./caddy:/etc/caddy:ro
grep -n -F 'Caddyfile bind-mount' scripts/deploy.sh  ->  85:# Caddyfile bind-mount (`./caddy/Caddyfile:/etc/caddy/Caddyfile:
… (qisqartirildi)
```

**Taklif**

In scripts/deploy.sh:85 replace the parenthetical with the actual mount, e.g. "# Caddyfile katalog bind-mount (`./caddy:/etc/caddy:ro`), ya'ni" — the rest of the comment (up -d only compares the service definition, not mounted content) stays valid.

**Bog'liq fayllar:** `docker-compose.prod.yml`, `docs/07-infra-devops.md`

<sub>ID `L019:0` · ovoz 2 · rad 0</sub>

### 75. scripts/deploy.sh comment still describes the Caddyfile as a FILE bind-mount, which compose deliberately stopped doing after a 3-week prod incident

- **Joy:** `scripts/deploy.sh:85`
- **Turi:** Hujjat kod bilan mos emas
- **Kod:** `# Caddyfile bind-mount (`./caddy/Caddyfile:/etc/caddy/Caddyfile:ro`), ya'ni`

**Nega tuzatish kerak**

docker-compose.prod.yml:155 mounts the DIRECTORY (`- ./caddy:/etc/caddy:ro`) and carries a six-line comment explaining that the file-mount form is exactly what broke prod ("prodda caddy 3 hafta eski Caddyfile bilan ishlagan va `caddy reload` ham o'sha eskisini qayta yuklardi"). docs/07-infra-devops.md:93 documents the directory mount as the correct, intentional form. Only scripts/deploy.sh still quotes the old file-mount path as if it were the current config. The deploy comment was written at 17:23 (0e8734c) and the mount was changed at 17:40 the same day (e1259f2) and never came back to it. The reload step's own reasoning stays valid, so nothing misbehaves today; the cost is that the one script an operator reads during a failed deploy describes a mount shape the project specifically banne
… (qisqartirildi)

**Tekshiruv**

```
$ grep -Fn "# Caddyfile bind-mount (`./caddy/Caddyfile:/etc/caddy/Caddyfile:ro`), ya'ni" scripts/deploy.sh
85:# Caddyfile bind-mount (`./caddy/Caddyfile:/etc/caddy/Caddyfile:ro`), ya'ni

$ grep -Fn "      - ./caddy:/etc/caddy:ro" docker-compose.prod.yml
155:      - ./caddy:/etc/caddy:ro

Resolved by docker itself (compose copied to a scratch dir with .env.example as .env):
$ docker compose -f docker-compose.prod.yml config
  caddy:
    volumes:
      - type: bind
        source: ...\cfgtest\caddy
        target: /etc/caddy
        read_only: true
(target is /etc/caddy, i.e. a directory bind - there is no /etc/caddy/Caddyfile file-mount)

$ git log -1 --format='%h %ad %s' -L155,155:docker-com
… (qisqartirildi)
```

**Taklif**

Update the comment at scripts/deploy.sh:85 to name the real mount (`./caddy:/etc/caddy:ro`, katalog mount) while keeping the rest of the reasoning, e.g. `# caddy/ katalog bind-mount (`./caddy:/etc/caddy:ro`), ya'ni ...`. The `--config /etc/caddy/Caddyfile` flag on line 96 is correct as-is and needs no change.

**Bog'liq fayllar:** `docker-compose.prod.yml`, `docs/07-infra-devops.md`

<sub>ID `L065:0` · ovoz 2 · rad 0</sub>

### 76. Phone rule is wired four different times with a hand-written field_validator while a reusable `_Phone` Annotated alias already exists

- **Joy:** `backend/app/schemas/employees.py:41`
- **Turi:** Takrorlanish (DRY)
- **Kod:** `def _check_phone(cls, v: str | None) -> str | None:`

**Nega tuzatish kerak**

One validation rule (`validate_phone`) is attached to six fields through three different mechanisms. `backend/app/schemas/clients.py:12` already solves it once with `_Phone = Annotated[str | None, AfterValidator(validate_phone), Field(examples=["+998901234567"], default=None)]` and uses it for four fields. `employees.py` instead re-declares a bare `_PHONE` FieldInfo (line 9) plus two 4-line `field_validator` wrappers (lines 41-44, 57-60), and `users.py` repeats the same wrapper twice more (lines 105-108, 124-127). The `"+998901234567"` example literal is written out three times in three files. I confirmed the three mechanisms produce byte-identical JSON Schema, so the extra code buys nothing; it is pure surface area that has to be kept in sync by hand (the comment at clients.py:10-11 alrea
… (qisqartirildi)

**Tekshiruv**

```
$ cd backend && grep -Fn "    def _check_phone(cls, v: str | None) -> str | None:" app/schemas/employees.py app/schemas/users.py
app/schemas/employees.py:43:    def _check_phone(cls, v: str | None) -> str | None:
app/schemas/employees.py:59:    def _check_phone(cls, v: str | None) -> str | None:
app/schemas/users.py:107:    def _check_phone(cls, v: str | None) -> str | None:
app/schemas/users.py:126:    def _check_phone(cls, v: str | None) -> str | None:

Ran, to prove the two mechanisms are behaviourally identical (so the collapse is safe):
$ cd backend && uv run python - <<'EOF'
import json
from app.schemas.employees import EmployeeCreate, EmployeeUpdate
from app.schemas.clients import Cli
… (qisqartirildi)
```

**Taklif**

Move `_Phone` from `backend/app/schemas/clients.py:12` to `backend/app/schemas/users.py`, next to the `validate_phone` function it wraps (that module is already the source both other schema modules import from). Then in `employees.py` delete `_PHONE` (line 9) and both `_check_phone` validators (lines 41-44, 57-60), and declare `phone: _Phone`; in `clients.py` import `_Phone` instead of `validate_phone`; in `users.py` replace the two `_check_phone` wrappers with the alias (note `UserCreate.phone` is required `str`, so it needs a non-optional sibling alias such as `_PhoneRequired = Annotated[str
… (qisqartirildi)

**Bog'liq fayllar:** `backend/app/schemas/clients.py`, `backend/app/schemas/users.py`

<sub>ID `L041:0` · ovoz 2 · rad 0</sub>

### 77. `all_tasks` is assigned twice at module level in app/tasks/__init__.py; the first list is dead and silently swallows any task added to it

- **Joy:** `backend/app/tasks/__init__.py:300`
- **Turi:** Takrorlanish (DRY)
- **Kod:** `all_tasks = [print_label, print_pachka_label, print_waste_label, print_badge]`

**Nega tuzatish kerak**

Lines 300 and 379 are byte-identical module-level assignments to `all_tasks`. The line-300 binding is dead: `WorkerSettings.functions = all_tasks` (backend/app/core/worker.py) always sees the line-379 value. Today both lists hold the same four print tasks so behaviour is unchanged, but it is a live trap: a developer scrolling to the first list, appending a new ARQ task there and restarting the worker gets a worker that silently does not register it — ARQ then answers `enqueue_job` for an unknown function with a job that never runs. Ruff does not catch it (F811 covers redefined imports/defs, not variable rebinding), so the green lint/type gates give no signal.

**Tekshiruv**

```
grep -n '^all_tasks' backend/app/tasks/__init__.py
300:all_tasks = [print_label, print_pachka_label, print_waste_label, print_badge]
379:all_tasks = [print_label, print_pachka_label, print_waste_label, print_badge]

Ran a script that parses the real module with ast, then patches ONLY the line-300 list to add a 5th function and re-execs the module body:
  module-level `all_tasks` assignments: 2
    line 300: all_tasks = [print_label, print_pachka_label, print_waste_label, print_badge]
    line 379: all_tasks = [print_label, print_pachka_label, print_waste_label, print_badge]
  after adding sync_downtimes to the FIRST list, len(all_tasks) = 4
  names: ['print_label', 'print_pachka_label', 'pri
… (qisqartirildi)
```

**Taklif**

Delete the line-300 assignment and keep the single definition at line 379 (after all four print tasks and both cron functions are defined), so there is exactly one list the worker registry reads.

**Bog'liq fayllar:** `backend/app/core/worker.py`

<sub>ID `L064:0` · ovoz 2 · rad 0</sub>

### 78. MachineAssign re-inlines activeFor()'s filter, making the "AKTIV markaz yo'q" placeholder unreachable

- **Joy:** `frontend/src/components/Orders/MachineAssign.tsx:81`
- **Turi:** Takrorlanish (DRY)
- **Kod:** `(m) => m.post_id === post.id && m.status === "active",`

**Nega tuzatish kerak**

activeFor() at line 66-69 and the inline filter at line 80-82 are the same predicate over the same `machines` array. The render loop only iterates `withChoice`, which is already filtered to posts where activeFor(p.id).length >= 2. So `options` recomputes a set that is guaranteed to hold >= 2 machines, and the false branch of `options.length ? "Ish markazini tanlang" : "AKTIV markaz yo'q"` (line 98) can never render. The duplicated predicate is what hides this: the guard and the consumer look independent, so the dead placeholder reads as a live case. If someone later relaxes the >= 2 threshold in one place only, the two filters silently diverge.

**Tekshiruv**

```
Transcribed lines 44-82 verbatim into a standalone JS harness and brute-forced 200000 random post/machine shapes:

$ node ma.mjs
rendered selects: 12973 | times placeholder ‘AKTIV markaz yo‘q’ shown: 0
undefined machines -> []

So across 12973 actually-rendered <SelectField>s the empty-options placeholder fired zero times. Quotes confirmed by grep -F:
68:      (m) => m.post_id === postId && m.status === "active",
81:          (m) => m.post_id === post.id && m.status === "active",
98:                options.length ? "Ish markazini tanlang" : "AKTIV markaz yo'q"
```

**Taklif**

Replace the inline filter at lines 80-82 with `const options = activeFor(post.id)`, and drop the unreachable ternary at line 98 to a plain `placeholder="Ish markazini tanlang"`. One predicate, one place, and no dead Uzbek string implying a state the guard already excluded.

<sub>ID `L068:0` · ovoz 2 · rad 0</sub>

### 79. detailMessage duplicates extractErrorMessage on every structured error and differs only by prefixing the invented "XATO"/"TARMOQ" code that docs/05 itself call…

- **Joy:** `frontend/src/utils.ts:133`
- **Turi:** Takrorlanish (DRY)
- **Kod:** `return message ? `${code}: ${message}` : code`

**Nega tuzatish kerak**

detailMessage() ignores the `structured` flag that detailParts() returns and that both sibling formatters (extractErrorMessage, toastScanError) honour. For a real MES envelope (structured=true) detailMessage and extractErrorMessage produce byte-identical output, so the helper buys nothing at its intended call site (the E009 terminal context screen). Where they differ, detailMessage is strictly worse: it glues onto the text a code the frontend invented. On the terminal context-error screen (routes/terminal.tsx:706 - the one with the WifiOff icon, i.e. exactly the screen you see when the network drops) the shop-floor operator gets bold red 'TARMOQ: Tarmoq xatosi - internet aloqasini tekshiring' or 'XATO: Serverda xatolik - qayta urining. Takrorlansa texnologga ayting'. docs/05-frontend-app.m
… (qisqartirildi)

**Tekshiruv**

```
Bundled the real module with esbuild (sonner stubbed) and ran it over 6 synthetic AxiosErrors:

$ npx esbuild ./__probe_u54.ts --bundle --platform=node --format=cjs --alias:sonner=./__sonner_u54.ts ... && node probe.cjs
--- network down (ERR_NETWORK)
  detailParts        = {"code":"TARMOQ","message":"Tarmoq xatosi — internet aloqasini tekshiring","structured":false}
  extractErrorMessage= "Tarmoq xatosi — internet aloqasini tekshiring"
  detailMessage      = "TARMOQ: Tarmoq xatosi — internet aloqasini tekshiring"
--- 500 plain text body
  extractErrorMessage= "Serverda xatolik — qayta urining. Takrorlansa texnologga ayting"
  detailMessage      = "XATO: Serverda xatolik — qayta urining. Takr
… (qisqartirildi)
```

**Taklif**

Drop detailMessage and render `extractErrorMessage(ctxError)` at routes/terminal.tsx:706. Structured E009 context errors keep the exact same text ('E009: ...'), while the network/5xx cases lose the fabricated TARMOQ:/XATO: prefix. Then remove the detailMessage bullet from docs/05-frontend-app.md:77. (Minimal alternative if the helper must stay: honour `structured` inside it - but that makes it a literal copy of extractErrorMessage.)

**Bog'liq fayllar:** `frontend/src/routes/terminal.tsx`, `frontend/src/lib/mes.ts`, `docs/05-frontend-app.md`

<sub>ID `L054:0` · ovoz 2 · rad 0</sub>

### 80. Prod serverda journald uchun hajm chegarasi yo'q — jurnal fayl tizimining 10% igacha (~7.7 GB) o'sib boraveradi

- **Joy:** `/etc/systemd/journald.conf`
- **Turi:** Infratuzilma (server)

**Nega tuzatish kerak**

mes.mebelix.uz da /var/log/journal hozir 377.6 MB — bu band diskning ~9 foizi va agent-dist (24 MB) dan 90 barobar katta, ya'ni serverdagi eng yirik o'sadigan iste'molchi. journald.conf da na SystemMaxUse, na MaxRetentionSec qo'yilgan, shuning uchun systemd default qoidasi amal qiladi: fayl tizimining 10 foizi. Disk 77 GB bo'lgani uchun jurnal ~7.7 GB gacha o'sishi mumkin. Hozir muammo emas (disk 6% band), lekin bu o'z-o'zidan to'xtamaydi va chegara faqat disk to'lganda seziladi. Taqqoslash uchun: audit tekshirgan boshqa hamma narsa o'zini tozalaydi — deploy.sh har deploydan keyin eski image'larni o'chiradi (0 ta dangling, 0 B build cache), agent-dist da aniq bitta .exe turadi, backup.sh 14 kundan eski arxivlarni o'zi o'chiradi.

**Tekshiruv**

```
ssh root@mes.mebelix.uz (faqat o'qish buyruqlari):

$ journalctl --disk-usage
Archived and active journals take up 377.6M in the file system.

$ du -sh /var/log/journal
378M	/var/log/journal

$ grep -E '^\s*SystemMaxUse|^\s*MaxRetentionSec' /etc/systemd/journald.conf
(chiqish yo'q — chegara qo'yilmagan, systemd default = fayl tizimining 10%)

$ df -h /
Filesystem      Size  Used Avail Use% Mounted on
/dev/vda1        77G  4.2G   73G   6% /

Taqqoslash (o'zini tozalaydigan joylar):
$ docker system df
Images 8 / ACTIVE 5 / Build Cache 0B
$ docker images --filter dangling=true -q | wc -l
0
$ ls /opt/mebelix-mes/agent-dist/
mebelix-agent.exe  version.json      (24 MB, bitta versiya)
$ grep -n 'm
… (qisqartirildi)
```

**Taklif**

/etc/systemd/journald.conf ga chegara qo'yish, masalan `SystemMaxUse=200M` (yoki loyihaga mos qiymat), keyin `systemctl restart systemd-journald`. Mavjud jurnalni darhol qisqartirish kerak bo'lsa: `journalctl --vacuum-size=200M`. DIQQAT: bu prod serverida holatni o'zgartiradi va jurnal tarixining bir qismini yo'qotadi — alohida tasdiqlash bilan bajarilsin. Konfiguratsiya o'zgargach docs/07-infra-devops.md ga ham yozib qo'yish kerak, chunki u hozir journald sozlamasi haqida hech nima demaydi.

**Bog'liq fayllar:** `docs/07-infra-devops.md`, `scripts/deploy.sh`, `scripts/backup.sh`

<sub>ID `SRV00:0` · ovoz main-session-direct · rad 0</sub>

## O'rta — keyin qo'shilgan (2026-09-21)

### 81. Kesish xaritasida «kesilgan / kesilmagan» YOLG'IZ rang bilan aytiladi — deuteranopiyada ikkala rang bir xil bo'lib qoladi (1.01×)

- **Joy:** `frontend/src/components/Terminal/SheetSvg.tsx:29-42,459-467`
- **Turi:** Xatolik (foydalanish qulayligi)
- **Kod:** `const PART_FILL = "#e88b00"` / `const PART_DONE = "#22c55e"`

**Nega tuzatish kerak**

Xaritada detal kataklarining holati faqat to'ldirish rangi bilan beriladi.
`allDone` render'da boshqa hech narsaga ta'sir qilmaydi: u faqat `fill` ni
tanlaydi (459-467) va ko'p nusxali detalda `doneCount/total` hisoblagichini
YASHIRADI (553) — ya'ni bajarilgan detal kamroq ma'lumot ko'rsatadi.
Galochka, shtrix yoki kontur farqi yo'q (`grep 'allDone' SheetSvg.tsx` —
uchta joy, uchalasi ham yuqorida). Bitta nusxali detalda, ya'ni ko'pchilikda,
rang YAGONA signal.

Apelsin `#e88b00` deuteranopiyada `#adad00` ga, yashil `#22c55e` esa `#aaaa63`
ga aylanadi — ikkalasi ham xira sariq, yorug'lik kontrasti **1.01×**. Bu
WCAG 2.2 SC 1.4.1 (Use of Color) buzilishi: ma'lumot faqat rang orqali
berilmasligi kerak. Qizil-yashil rang ko'rmaslik erkaklarning ~8% ida
uchraydi, arrachi esa deyarli har doim erkak. Bunday arrachi uchun kesish
xaritasi — ishning asosiy hujjati — «nima kesildi, nima qoldi» degan
savolga umuman javob bermaydi.

Qoldiq zebralarida ahvol yomonroq: uchalasi (`#c9d2de` atxot, `#f2c78d` chek
chiqmagan qoldiq, `#a3dfb8` chek chiqqan qoldiq) NORMAL ko'rishda ham
1.00–1.04× — ya'ni farq faqat tusda, yorug'likda umuman yo'q. Chiziq
geometriyasi uchalasida bir xil (36/18, 45°), matn esa katakda faqat
o'lcham (`W×H`), holat emas.

MUHIM: bu terminallar orasida YAGONA joy. Qolgan hamma terminalda rang matn
yoki belgi bilan takrorlangan va shuning uchun to'g'ri — `PrisadkaView`
«✓ Bajarildi» / «Chek chiqarilgan» / «Chek yo'q» (360-377), «✓» yoki
`done/total` (603-613), `InstanceChip` «✓» yoki «–» (30-44). Ya'ni tuzatish
kerak bo'lgan naqsh butun kodda bitta.

**Tekshiruv**

```
Vienot et al. 1999 LMS proyeksiyasi bilan simulyatsiya (skript:
scratchpad/cvd-cutmap.py, ranglar SheetSvg.tsx:29-42 dan so'zma-so'z):

$ python cvd-cutmap.py
== DETAL ==
   kesilmagan       #e88b00 -> deuter #adad00 | protan #999907
   kesilgan         #22c55e -> deuter #aaaa63 | protan #bbbb5d
   nostandart       #a78bfa -> deuter #9494fa | protan #8f8ffa
   juftlik                        normal    deuter    protan
   kesilmagan vs kesilgan          1.13x     1.01x     1.50x
   kesilmagan vs nostandart        1.05x     1.11x     1.08x
   kesilgan vs nostandart          1.19x     1.10x     1.39x

== QOLDIQ ZEBRASI ==
   qoldiq/chek yo'q vs qoldiq/chek bor    1.04x     1.02x     1.16x
   qoldiq/chek yo'q vs atxot       1.03x     1.01x     1.10x
   qoldiq/chek bor vs atxot        1.00x     1.02x     1.05x

Ikkinchi belgi yo'qligi: `grep -n 'allDone' SheetSvg.tsx` -> 435 (ta'rif),
463 (fill), 553 (hisoblagichni yashirish). Boshqa ishlatilishi yo'q.
```

**Taklif**

Rangni OLIB TASHLAMASLIK kerak — u tsex taklifi bilan tanlangan va normal
ko'rishda tez ishlaydi. Ustiga ikkinchi, rangdan mustaqil belgi qo'shish
kerak (WCAG talabi ham shu):

1. Kesilgan detal katagiga galochka yoki diagonal shtrix naqsh — eng arzoni,
   bitta `<path>`. Thumbnail'da chizilmasin (mavjud `thumbnail` bayrog'i bor).
2. Hisoblagichni `allDone` da YASHIRMASLIK: `2/2` ko'rsatilsa, bitta nusxali
   detal uchun ham `1/1` qo'yish mumkin — matn rangdan mustaqil.
3. Qoldiq zebralarida rang bilan birga chiziq QALINLIGINI yoki burchagini
   farqlash (45° / 135°), yoki katakka `✓` qo'yish.

Chop etishni ham hisobga olish kerak: xarita `renderToStaticMarkup` orqali
Tailwind'siz oynaga yoziladi (`CutmapView.tsx:107`), ya'ni yangi belgi ham
xom SVG atributlarida bo'lishi shart, `className` da emas. Qora-oq printerda
esa rang butunlay yo'qoladi — ikkinchi belgi o'sha yerda ham yutuq.

**Bog'liq fayllar:** `frontend/src/components/Terminal/CutmapView.tsx`, `docs/06-frontend-components.md`

<sub>2026-09-21 · audit doirasidan tashqari · o'lchangan</sub>

## Kechiktirilgan: OEE / kromka / brak / to'xtalish

Bu quyi tizim faol yozilmoqda (uch kunda +3511 qator), shuning uchun u
alohida raundga qoldirildi. Quyidagi fayllar bo'yicha yo'llanmalar yig'ilgan,
**lekin hukm ham, tekshiruv ham qilinmagan** — ular topilma emas:

- `backend/app/api/routes/bridge_agents.py` — 1 ta yo'llanma
- `backend/app/api/routes/machines.py` — 1 ta yo'llanma
- `backend/app/api/routes/settings.py` — 2 ta yo'llanma
- `backend/app/services/downtimes.py` — 1 ta yo'llanma
- `bridge-agent/README.md` — 3 ta yo'llanma
- `docs/03-backend-api.md` — 6 ta yo'llanma
- `docs/04-backend-data.md` — 12 ta yo'llanma
- `docs/05-frontend-app.md` — 11 ta yo'llanma
- `docs/06-frontend-components.md` — 13 ta yo'llanma
- `docs/README.md` — 2 ta yo'llanma

Jami 52 ta hukm qilinmagan yo'llanma, 10 ta fayl bo'yicha.
Quyi tizim barqarorlashgach shu raund ishga tushadi.

## Rad etilgan topilmalar

Bular ko'rib chiqilgan va **ataylab** ro'yxatga kiritilmagan. Qayta
ko'tarilmasligi uchun sababi bilan qoldirildi.

**backend/README.md states 97 HTTP endpoints; the live app has 117 (docs/README.md already says 117)**  
`backend/README.md` · 2/4 rad etdi

> The finding was computed against a pre-git-pull tree (ef4d6c5-era, 25 commits behind the stated baseline e234cf2). At e234cf2 every number it asserts is false and its cited evidence does not exist in the file. (1) Step 3 check #2 fails outright. The evidence block states: "grep -nF '117 HTTP + 2 WS' docs/README.md -> line 9". At e234cf2 that grep exits 1 - no match. docs/README.md:9 verbatim read

**request.state.request_id is set so error handlers can add the header, but no error handler exists or reads it anywhere in the backend**  
`backend/app/core/middleware.py` · 2/2 rad etdi

> The finding's raw facts check out (quote is verbatim at `D:/Projects/MebeliX-Mes-System/backend/app/core/middleware.py:23`; `state.request_id` has exactly one repo occurrence; zero `exception_handler`/`add_exception_handler` registrations). It still fails the value lens on three counts, two of which I confirmed by execution. 1. The comment is mechanically TRUE, not noise. I ran the real `RequestL

**Order.created_by_id (and Pachka.created_by_id) are write-only columns: assigned once, never read, not exposed by the API**  
`backend/app/models/order.py` · 1/2 rad etdi

> The finding's facts check out: quotes are verbatim at the stated lines, and I confirmed by building the live OpenAPI schema (not just grep) that `created_by` appears 0 times in the API surface while `cancelled_by` appears once. A whole-repo grep (incl. bridge-agent, scripts, caddy, design) finds only the 2 writes + 2 definitions + 2 doc lines. So the column really is write-only. It is refuted on

**Caddyfile header advertises `your-domain.com:8443` custom-port mode that docker-compose.prod.yml cannot expose (container ports hardcoded 80/443)**  
`caddy/Caddyfile` · 1/2 rad etdi

> Quote is verbatim at caddy/Caddyfile:4 and docs/07-infra-devops.md:145, but the finding's mechanism is measurably false. Its evidence came from `caddy adapt`, which omits the auto-HTTPS redirect server Caddy injects at provision time. I ran the real container with a host:port SITE_ADDRESS: netstat inside the container shows :80 bound (plus :8080 and :8443), and curl against the published host port

**deploy.sh comment cites the file bind-mount `./caddy/Caddyfile:/etc/caddy/Caddyfile:ro` that compose replaced with a directory mount 17 minutes later**  
`scripts/deploy.sh` · 1/2 rad etdi

> The literal facts hold: scripts/deploy.sh:85 does contain the quote verbatim, docker-compose.prod.yml:155 is a directory mount, and the two commit timestamps (0e8734c 17:23:46 -> e1259f2 17:40:08) are right. It fails the value lens anyway. (a) The comment's argument is mount-shape-independent: it exists to justify the `caddy reload` step because compose recreates a container only on service-defini

**routes.py and docs/10 claim build_manual_route is the ONLY copy of the route-step rule, but matrix.py builds a MANUAL PartRoute inline with its own c…**  
`backend/app/services/giblab/routes.py` · 1/2 rad etdi

> Quotes are verbatim at e234cf2 (routes.py:1 docstring, matrix.py:199/207, docs/10:755), but the finding's premise — that the project claims a single copy of the per_instance rule and matrix.py's stage toggle is an undocumented "third site" — is wrong in scope, and acting on it is pure churn. 1. Scope of the "YAGONA nusxa" claim. routes.py:1 says "Qo'lda chizilgan marshrutni qurish — qoidaning YAG

**SidebarProvider's controlled-mode API (open / onOpenChange / defaultOpen) has no caller — two branches are unreachable**  
`frontend/src/components/ui/sidebar.tsx` · 1/2 rad etdi

> Facts check out, verdict does not. The quote `const open = openProp ?? _open` is verbatim at D:/Projects/MebeliX-Mes-System/frontend/src/components/ui/sidebar.tsx:79, and the app's only `<SidebarProvider>` (D:/Projects/MebeliX-Mes-System/frontend/src/routes/_layout.tsx:98) passes no props, so `openProp`/`setOpenProp` really are always undefined and the `if (setOpenProp)` branch never runs. But the

**CLAUDE.md OEE'ni faqat «olib tashlangan modul» deb tilga oladi — 2026-09-18 dan jonli OEE moduli bor (services/performance.py: oee_pct)**  
`CLAUDE.md` · 2/2 rad etdi

> Quote is verbatim at D:/Projects/MebeliX-Mes-System/CLAUDE.md:88 and the timeline the finding gives is accurate (CLAUDE.md last touched e58f376 2026-09-10; the rebuilt OEE services landed 2026-09-13..19; docs/12-oee.md exists at e234cf2 and says OEE is live). But the finding is an OMISSION claim, not drift: the sentence at CLAUDE.md:87-90 is a statement about where the 6 orphan tables / 7 orphan c

**Detal-kalit formulasi `{product_code}_{part.code}` 11 joyda qo'lda takrorlangan; yagona nomlangan ta'rif (`ParsedPart.key`) faqat parser tomonda**  
`backend/app/api/routes/tablo.py` · 2/2 rad etdi

> Quote is verbatim at D:/Projects/MebeliX-Mes-System/backend/app/api/routes/tablo.py:222 and the count is right (11 identical `{product_code}_{part.code}` sites, no variant anywhere). But the finding concedes "xato YO'Q" and rests entirely on a hypothetical future formula change. On the value lens that scenario does not hold and the fix is net-negative: 1. The key is frozen by DATA, not by code. `

**docs/09 §7 says NAV_ITEMS has 9 items and lists _layout routes without agents/system-settings; sidebar has 10 items and printers.tsx is only a redire…**  
`docs/09-mes-domain.md` · 1/2 rad etdi

> The finding's central fact and its proposed fix are wrong, even though the doc is indeed stale. Verified at e234cf2: docs/09-mes-domain.md:616 does say "`Sidebar/AppSidebar.tsx: NAV_ITEMS` (9 band)" and line 606 does list "clients, employees, work-centers, reports, logs, printers, admin, settings," (both quotes verbatim). But NAV_ITEMS in frontend/src/components/Sidebar/AppSidebar.tsx at e234cf2 h

**scx.py build_scx_files docstring shows a Panel ID without the order prefix that instance_qr always adds**  
`backend/app/services/giblab/scx.py` · 1/2 rad etdi

> Quote is verbatim at backend/app/services/giblab/scx.py:243 (and the identical prefixless example also sits at scx.py:45, which the finding does not mention). But the finding's central premise — "every instance QR, and therefore every SCX filename and Panel ID, is B-2026-047_100701_02_003_1" — is false at e234cf2. `build_scx_files` is format-agnostic (`out.append((f"{qr}.scx", content))`, scx.py:2

