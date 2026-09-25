# Orakllar — bir martalik tekshiruv skriptlari

Bu **test to'plami EMAS** va CI uni chaqirmaydi. Loyihada test yo'q (ataylab,
`683e47e`), yagona orakl — xulq haqidagi da'voni bajarib tasdiqlaydigan skript.
Ilgari ular `/tmp` da yozilardi va macOS tozalashi ularni ikki marta yeb ketdi;
shuning uchun endi shu yerda turadi.

Har biri HAQIQIY handlerni HAQIQIY Postgres ustida yurgizadi (yoki firmware
qatorlarini HAQIQIY agent parseridan o'tkazadi), oxirida `N/N to'g'ri` deb yozadi.

## Yurgizish

Lokal SINOV bazasi kerak — **prod emas**, skript jadvallarni `TRUNCATE` qiladi:

```bash
createdb mebelix_oee_test
cd backend && uv run alembic upgrade head       # DATABASE sozlamalari env dan
```

`/tmp/oee_test.env` (namuna):

```
ENVIRONMENT=local
SECRET_KEY=test-secret-key-for-local-oracle-only
FIRST_SUPERUSER=admin
FIRST_SUPERUSER_PASSWORD=demo12345
POSTGRES_USER=<foydalanuvchi>
POSTGRES_PASSWORD=
POSTGRES_SERVER=localhost
POSTGRES_PORT=5432
POSTGRES_DB=mebelix_oee_test
REDIS_HOST=localhost
REDIS_PORT=6379
```

```bash
cd backend && set -a && . /tmp/oee_test.env && set +a \
  && uv run python ../scripts/oracles/oee_oracle.py
```

## Nima tekshiriladi

| Skript | Da'vo |
| --- | --- |
| `oee_oracle.py` | Availability / Performance / Quality / OEE, ish jadvali va tanaffus, to'xtash chegarasi, kromkada bo'sh yurish, OEE kesim sanasi, rejaning HOZIRGACHA kesilishi (`docs/12` §4.5-4.9) |
| `kromka_bind_oracle.py` | O'lchovni detalga bog'lash: kirish vaqti (`ish_ms`), oyna, o'lcham bo'yicha juftlash, mos/nomos/ortiqcha hukmi (`docs/12` §4.10) |
| `kromka_v116_oracle.py` | Proshivka v1.16: `tiqilish`, `eski_ms`, avariya xabari holat bo'lib yozilmasligi |
| `kromka_v122_oracle.py` | Proshivka v1.19-v1.22: `xb`/`xq` kaliti, takror hodisa, `ACK` faqat server yozgach, `sig`/`yigilgan` uzatilmasligi |
| `rover_oracle.py` | CNC 2130: `hello`/`state`/`event`, `rover_type`, tasdiq (`ack`) tartibi, vaqt va sozlama yuborish |
| `tablo_machines_oracle.py` | Stanok taxtasi (`GET /tablo/machines`) — raqamlar hisobotning aynan o'zidan |
| `demo_seed.py` | Orakl fixture'i ustiga lokal demo ma'lumot (skript emas, ko'rsatish uchun) |
