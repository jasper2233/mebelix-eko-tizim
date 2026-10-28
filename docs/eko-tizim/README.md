# EKO TIZIM — MES nusxasi ustidagi ish

Bu repo — MebeliX MES (`94a2f9e`) ning **nusxasi**. Asl MES ga tegilmaydi:

- remote `mes-asl` — faqat o'qish uchun, push manzili ataylab buzilgan;
- ish `eko-tizim` branchida; `main` ga push = prodga deploy, shuning uchun bu nusxadan hech qachon push qilinmaydi.

Texnik topshiriq (birlamchi manba): https://claude.ai/artifact/UENWqnKyfxz1E6jdoL422u

Qisqacha: Ombor, Kassa, Moliya, Soliq — MES ichida modulli monolit (`app/modules/*`,
alohida Postgres sxemalari, `api-sex` / `api-ofis` jarayonlari); MX Kroy — alohida servis,
ikki rejimda (mustaqil / ekotizim), API va webhook orqali ulanadi. Tizim tijorat mahsuloti:
obuna (ko'p ijarachi, har obunachi alohida baza) va mijoz serverida o'rnatish.

## Bosqichlar holati

| Bosqich | Holat | Nima qilindi |
| --- | --- | --- |
| 0. Nusxa | tayyor | `9a9264c` |
| 1a. Poydevor | kod tayyor, DB/Docker bilan sinalmagan | pastda |
| 1b. Ko'p ijarachi | navbatda | TZ §2.4 |

### 1a — nima qo'shildi

- `core/config.py`: `ProcessRole` (`all`/`sex`/`ofis`/`worker`), `API_ROLE`, rol bo'yicha `STATEMENT_TIMEOUT_MS`
  (3 s / 30 s / 300 s; `all` = cheklovsiz), `DB_STATEMENT_TIMEOUT_MS` bilan qo'lda berish.
- `core/db.py`: timeout asyncpg `server_settings` bilan ulanishga qo'yiladi.
- `core/utils/queue.py` + `core/worker.py`: `QUEUE_TEZ` / `QUEUE_SEKIN`, `WorkerSekinSettings`.
- `docker-compose.prod.yml`: `api` = ofis, yangi `api-sex`, `worker-sekin`; `caddy/Caddyfile` — sex yo'llari `api-sex` ga.
- `models/enums.py`: `UserLevel` (1 jarayon, 2 o'rta, 3 ofis), `ROLE_LEVEL`; `api/deps.py`: `require_level`;
  frontend `lib/mes.ts`: `LEVEL`, `ROLE_LEVEL`, `hasLevel` (qo'lda oyna).
- `app/modules/{ombor,kassa,moliya,soliq,integratsiya,platforma}` skeleti va
  `scripts/check_module_boundaries.py` (`make lint` va CI da).

Tekshirildi: ruff, ruff format, mypy, modul chegarasi skripti (ataylab qo'yilgan 4 ta buzilishni
topdi), bir martalik orakl (rol → timeout, `require_level`, navbatlar), biome, frontend build.
**Sinalmagan:** Postgres'da timeout amalda qo'yilishi, Caddy yo'l tartibi (`caddy adapt`),
compose'ning to'liq ko'tarilishi — Docker kerak.
