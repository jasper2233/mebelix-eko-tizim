# EKO TIZIM — MES nusxasi ustidagi ish

Bu repo — MebeliX MES (`94a2f9e`) ning **nusxasi**. Asl MES ga tegilmaydi:

- remote `mes-asl` — faqat o'qish uchun, push manzili ataylab buzilgan;
- ish `eko-tizim` branchida; `main` ga push = prodga deploy, shuning uchun bu nusxadan hech qachon push qilinmaydi.

Texnik topshiriq (birlamchi manba): https://claude.ai/artifact/UENWqnKyfxz1E6jdoL422u

Qisqacha: Ombor, Kassa, Moliya, Soliq — MES ichida modulli monolit (`app/modules/*`,
alohida Postgres sxemalari, `api-sex` / `api-ofis` jarayonlari); MX Kroy — alohida servis,
ikki rejimda (mustaqil / ekotizim), API va webhook orqali ulanadi.
