# MebeliX MES

MebeliX MES — mebel ishlab chiqarish boshqaruv tizimi.

Stack: FastAPI + PostgreSQL + Redis / React + Vite / Docker Compose + Caddy.

## Boshlash

- Bir martalik: `cp .env.example .env` (`api` va `worker` uni `env_file` orqali majburiy o'qiydi)
- Backend: [backend/README.md](backend/README.md)
- Frontend: [frontend/README.md](frontend/README.md)
- Printer agenti (sexdagi, printer ulangan kompyuter): [bridge-agent/README.md](bridge-agent/README.md)
- Hammasi konteynerda: `make docker-local`

## Hujjatlar

To'liq texnik hujjatlar indeksi: [docs/README.md](docs/README.md)

## Prod

https://mes.mebelix.uz — CI yashil `main`dan avto-deploy.
