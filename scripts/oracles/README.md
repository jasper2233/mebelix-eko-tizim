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
ADMIN_USERNAME=admin
ADMIN_PASSWORD=demo12345
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

Qo'shimcha talablar: `kromka_dedup_oracle.py` va `downtime_cleanup_oracle.py` SQL'ni
AYNAN `psql` orqali yurgizadi — u `PATH` da bo'lsin; `tablo_machines_oracle.py` ga
Redis kerak (qolganlari Redis'siz ham ishlaydi: jonli holat o'qilmasa «aloqa yo'q»).
Windows'da Docker'siz: EDB'ning portativ PostgreSQL 15 zip'i (`initdb -A trust`,
`pg_ctl -o "-p 5434 -c shared_preload_libraries=pg_stat_statements" start`) va
portativ Redis yetadi. Git Bash'da `PATH` ga `/c/...` ko'rinishida qo'shing —
`C:/...` dagi ikki nuqta yo'lni bo'lib yuboradi.

Oxirgi to'liq yurgizish (2026-10-16): `oee` 31/31, `rover` 25/25, `rover_oee` 19/19,
`downtime_cleanup` 14/14, `kromka_bind` 23/23, `kromka_v116` 11/11, `kromka_v122` 19/19,
`kromka_dedup` 18/18, `tablo_machines` 29/29, `catalog` 36/36, `agent_gap` 8/8, `defect` 8/8, `kromka_kirish` 4/4, `kromka_kal` 8/8.

## Nima tekshiriladi

| Skript | Da'vo |
| --- | --- |
| `oee_oracle.py` | Availability / Performance / Quality / OEE, ish jadvali va tanaffus, to'xtash chegarasi, kromkada bo'sh yurish, OEE kesim sanasi, rejaning HOZIRGACHA kesilishi (`docs/12` §4.5-4.9) |
| `kromka_bind_oracle.py` | O'lchovni detalga bog'lash: kirish vaqti (`ish_ms`), oyna, o'lcham bo'yicha juftlash, mos/nomos/ortiqcha hukmi (`docs/12` §4.10) |
| `kromka_v116_oracle.py` | Proshivka v1.16: `tiqilish`, `eski_ms`, avariya xabari holat bo'lib yozilmasligi |
| `kromka_v122_oracle.py` | Proshivka v1.19-v1.22: `xb`/`xq` kaliti, takror hodisa, `ACK` faqat server yozgach, `sig`/`yigilgan` uzatilmasligi |
| `rover_oracle.py` | CNC 2130: `hello`/`state`/`event`, `rover_type`, tasdiq (`ack`) tartibi, vaqt va sozlama yuborish; agent 1.9.0 — hodisa uchala holat (ishlov / bo'sh turish / o'chiq) o'zgarishida |
| `rover_oee_oracle.py` | Rover to'liq OEE: bo'sh turish IDLE (mikro-to'xtash qoidasi), Performance (detalga + perimetr × s/m), Quality, koeffitsiyent o'zgarsa qayta hisob, to'xtash sinxroni (tur, chegara, `idle-*` takror yo'qligi) (`docs/12` §4.15) |
| `kromka_kirish_oracle.py` | Kromka o'lchovi ↔ skan: kirish `ts − (ish_ms + d2)`, oyna −60 … +20 s, skan darajasida FIFO (stansiya repo'si tavsiyasi, `docs/12` §4.10) |
| `kromka_juft_oracle.py` | PAKET: 15 sm dan kichik detallar birga o'tkazilganda — 2–4 bo'lakli yig'indi har qirrani yopadi, yolg'iz detal + to'ldiruvchi, noaniq yig'indi va kvotasi tugagan paket hech narsani yopmaydi (`docs/12` §4.26) |
| `kromka_kal_oracle.py` | Kromka Pico'sidagi joriy kalibrlash: agent `HOLAT`/`SET` javobidan o'zgarganda yuboradi, server oxirgisini beradi (`docs/12` §4.18) |
| `defect_oracle.py` | Brak — skanning xossasi: tushlikda/ertasi kuni/begona terminaldan bosilgan brak o'z skanining kuni va stanogida sanaladi, brak tasdig'i bekor qilgan skan (boshqa postniki ham, rad etilgandan keyin ham) P va Q da qoladi, Kromka kvotasi bekor skandagi o'lchovni sanamaydi (`docs/12` §4.17) |
| `agent_gap_oracle.py` | Agent uzilgan payt: Rover holati Pico'ning `POWER_ON`/`POWER_CYCLE`/`SPINDLE_IDLE` yozuvlaridan tiklanadi va to'xtash yozuvi bo'ladi (takrorsiz), Kromka davomiyligi saqlanadi, tokdan qayta yonish kesiladi, `wdt` kesilmaydi (`docs/12` §4.16) |
| `downtime_cleanup_oracle.py` | `scripts/downtime_deleted_events.sql`: o'chirilgan hodisadan va Rover `idle-*` dan yasalgan soxta to'xtashlar tozalanadi, haqiqiylari, qulf, Kromka bo'sh yurishi va operator sababi qoladi, faqat-hisobot rejimi hech narsa o'zgartirmaydi, ikkinchi yurgizish xavfsiz |
| `tablo_machines_oracle.py` | Stanok taxtasi (`GET /tablo/machines`) — raqamlar hisobotning aynan o'zidan |
| `kromka_dedup_oracle.py` | `scripts/kromka_dedup.sql`: takrorlar o'chadi, haqiqiylari qoladi, hisobot to'g'rilanadi, ikkinchi yurgizish xavfsiz |
| `cb_rate_oracle.py` | Markaziy bank kursi: javobni o'qish, buzuq shakllar, kesh, bank javob bermagani va tiklangani (`docs/14` §8.1) |
| `ombor_hisobot_oracle.py` | Ombor hisoboti (`docs/14` §11): guruh aylanmasi, qiymat partiyalardan, ABC (eng qimmati A), harakatsiz tovarlar, yumshoq o'chirilgan harakat |
| `catalog_oracle.py` | Mahsulotlar ombori: `catalog_import.py` CSV ni bazaga yuklashi, kategoriya daraxti, filtr va qidiruv, qoldiq yozish, qayta importda qoldiqning saqlanishi (`docs/14`) |
| `demo_seed.py` | Orakl fixture'i ustiga lokal demo ma'lumot (skript emas, ko'rsatish uchun) |
