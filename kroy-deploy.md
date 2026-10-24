# kroy.mebelix.uz — alohida dasturni shu serverga qo'yish

**Bu MES hujjati EMAS.** `docs/` MES tizimini tasvirlaydi; bu fayl esa BOSHQA dasturni
(`kroy`) o'sha serverga qo'yish tartibi. Ikkisi faqat bitta narsani bo'lishadi: server va
443-portdagi sertifikat. Kod, baza va deploy — alohida.

Sana: 2026-10-24.

---

## 1. Hozirgi holat

| | |
| --- | --- |
| Server | `164.92.227.91` (DigitalOcean droplet, Ubuntu 24.04) |
| Resurs | 2 vCPU · 3.8 GB RAM (MES ~1.5 GB oladi) · 77 GB diskdan 70 GB bo'sh |
| Docker | 29.1.3 · Compose 2.40.3 |
| MES | `/opt/mebelix-mes`, tarmoq `mebelix-mes_default` |
| 80/443 | **MES ning Caddy konteyneri** (`mebelix-mes-caddy-1`) ushlab turadi |
| DNS | `kroy.mebelix.uz` → `164.92.227.91` (A, TTL 3600) — 2026-10-24 da aHOST'da qo'shildi, tarqalgan |

Ya'ni sertifikatni ham, 443-portni ham MES'ning Caddy'si boshqaradi. Yangi dastur 80/443 ni
**ololmaydi** — ikkinchi dastur o'sha portni egallay olmaydi. Shuning uchun quyidagi tartib:
dastur o'zining konteynerida, o'zining katalogida yashaydi, tashqariga esa Caddy orqali chiqadi.

---

## 2. Qaror: dastur qayerda yashaydi

```
/opt/kroy/                 ← YANGI, MES'ga tegmaydi
  docker-compose.yml       ← dasturning o'zi
  .env                     ← sirlari (git'ga tushmaydi)
  data/                    ← bazasi/fayllari
```

MES tomonida o'zgaradigan yagona narsa — `caddy/Caddyfile` ga bitta blok (4-bo'lim).

**⚠️ Serverda qo'lda fayl yaratib qo'yish MUMKIN EMAS (MES katalogi ichida).** MES deployi
`rsync -az --delete` bilan butun `/opt/mebelix-mes/` ni repodan qayta yozadi: o'sha katalog
ichiga qo'yilgan har qanday begona fayl keyingi deployda O'CHADI. Shuning uchun:

- dastur fayllari — `/opt/kroy/` da (rsync u yerga tegmaydi);
- Caddy bloki — repodagi `caddy/Caddyfile` da, commit bilan.

---

## 3. Dasturni ko'tarish

Dastur konteyner ichida ishlashi va **porti tashqariga chiqmasligi** kerak: Caddy unga
Docker tarmog'i ichidan nom bo'yicha boradi. Serverda `ufw` o'chiq, ya'ni `ports:` bilan
ochilgan port butun internetga ochiladi — shuning uchun `ports:` yozilmaydi.

`/opt/kroy/docker-compose.yml`:

```yaml
services:
  kroy:
    image: <dastur-image>:<tag>        # yoki build: .
    container_name: kroy
    restart: always
    env_file: .env
    volumes:
      - ./data:/data                   # dastur fayllari/bazasi
    networks:
      - mes                            # Caddy shu tarmoqdan topadi
    # ports: YO'Q — tashqariga faqat Caddy orqali chiqadi
    logging:                           # log disk yemasin
      driver: json-file
      options: { max-size: "10m", max-file: "3" }

networks:
  mes:
    external: true
    name: mebelix-mes_default
```

Ko'tarish:

```bash
ssh root@164.92.227.91
mkdir -p /opt/kroy/data && cd /opt/kroy
# docker-compose.yml va .env ni shu yerga qo'ying
docker compose up -d
docker compose ps          # healthy/Up bo'lsin
docker compose logs -f     # xatosiz ko'tarilganini ko'ring
```

Konteyner ichidan tekshirish (hali tashqarida ochilmaydi):

```bash
docker run --rm --network mebelix-mes_default curlimages/curl -sS -o /dev/null -w '%{http_code}\n' http://kroy:<PORT>/
```

`200` (yoki dastur beradigan kutilgan kod) kelsa — dastur tirik, endi uni tashqariga chiqarish mumkin.

---

## 4. Sub domenni ulash (MES repo'sida bitta commit)

`caddy/Caddyfile` OXIRIGA qo'shiladi — mavjud blokka TEGILMAYDI:

```caddy
# kroy.mebelix.uz — MESdan ALOHIDA dastur (kroy-deploy.md). Faqat sertifikat va
# 443-port bo'lishiladi: so'rov to'g'ridan-to'g'ri `kroy` konteyneriga ketadi.
kroy.mebelix.uz {
	header {
		X-Frame-Options SAMEORIGIN
		X-Content-Type-Options nosniff
	}
	encode gzip
	reverse_proxy kroy:<PORT>
}
```

Keyin odatdagi yo'l: `main` ga push → CI → `scripts/deploy.sh` serverda `caddy reload`
qiladi. Caddy `kroy.mebelix.uz` uchun Let's Encrypt sertifikatini O'ZI oladi (DNS allaqachon
shu serverga qaraydi, 80-port ochiq — HTTP-01 tekshiruvi o'tadi).

**Diqqat:** `kroy` konteyneri ko'tarilmagan bo'lsa, Caddy ishga tushganda `kroy:<PORT>` nomini
topa olmay blokni rad etishi mumkin. Shuning uchun tartib shunday: avval 3-bo'lim (dastur
ko'tariladi), keyin 4-bo'lim (Caddy bloki deploy qilinadi).

Tekshirish:

```bash
curl -I https://kroy.mebelix.uz          # 200/302 va `server: Caddy`
curl -I https://mes.mebelix.uz           # MES hamon joyida — buzilmaganini ham tekshiring
```

---

## 5. Nimaga e'tibor berish kerak

**Xotira.** Serverda 3.8 GB, MES ~1.5 GB oladi, `available` ~2.3 GB. Yangi dastur ko'p
yesa, Postgres sekinlashadi va OOM killer MES konteynerini o'ldirishi mumkin. Dastur og'ir
bo'lsa — `mem_limit` qo'ying:

```yaml
    mem_limit: 768m
```

va bir necha kun `docker stats` bilan qarab turing.

**Baza.** MES Postgres'iga TEGMANG: u MES niki, `kromka_measurement` kabi jadvallar o'sha
yerda. Dasturga baza kerak bo'lsa — o'z konteynerida (`/opt/kroy/` ichida), o'z volume'ida.

**Backup.** MES backupi (`scripts/backup.sh`) faqat MES bazasini oladi — `/opt/kroy/` ga
tegmaydi. Dastur ma'lumoti qimmat bo'lsa, unga alohida cron yozish kerak.

**Log.** `logging` bo'limisiz Docker logi cheksiz o'sadi va 70 GB bo'sh joyni yeb qo'yadi.
Yuqoridagi `max-size`/`max-file` shuning uchun turibdi.

**Port.** Hech qachon `ports: "8081:8080"` yozmang — `ufw` o'chiq bo'lgani uchun u port butun
internetga ochiladi va dastur to'g'ridan-to'g'ri, sertifikatsiz, Caddy'ning himoyasisiz
ochiq qoladi.

**MES deployi.** Har MES deployida Caddy qayta yuklanadi (~1 soniya) — `kroy` ga ta'sir
qilmaydi, uning konteyneri qayta ishga tushmaydi.

---

## 6. Agar butunlay ajratish kerak bo'lsa

Bugungi chegara: 443-port bitta — shuning uchun kroy'ning vhost bloki MES repo'sida yashaydi.
Agar keyinchalik to'liq mustaqillik kerak bo'lsa, ikki yo'l bor:

1. **Alohida server** — kroy uchun yangi droplet, `kroy.mebelix.uz` ning A yozuvi o'sha IP ga
   o'zgartiriladi (aHOST → Mening domenlarim → mebelix.uz → DNS xosting). MES bilan hech
   qanday aloqa qolmaydi.
2. **Umumiy reverse proxy** — 80/443 ni MES compose'idan chiqarib, serverda mustaqil Caddy'ga
   berish. Bu MES deployiga ham tegadi, ya'ni bitta dastur uchun arzimaydi.

Hozircha 1-yo'l arzon va toza: dastur o'sadigan bo'lsa shu tomonga qaraladi.

---

## 7. Qisqa ro'yxat

- [x] DNS: `kroy.mebelix.uz` → `164.92.227.91`
- [ ] `/opt/kroy/docker-compose.yml` + `.env` yoziladi, dastur ko'tariladi
- [ ] Konteyner ichidan `http://kroy:<PORT>/` javob berishi tekshiriladi
- [ ] `caddy/Caddyfile` ga blok qo'shiladi, `main` ga push (deploy 19:00 dan keyin)
- [ ] `https://kroy.mebelix.uz` ochiladi, `https://mes.mebelix.uz` buzilmaganini tekshiriladi
- [ ] Kerak bo'lsa: `mem_limit`, backup cron
