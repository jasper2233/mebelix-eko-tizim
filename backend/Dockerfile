# --------- Builder Stage ---------
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim AS builder

ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy

WORKDIR /app/backend

# FAQAT bog'liqliklar — loyiha venv'ga O'RNATILMAYDI (app PYTHONPATH orqali
# ishlaydi). Shunda venv qatlami faqat uv.lock'ga bog'liq: kod o'zgarganda
# ~380MB qatlam qayta qurilmaydi va server har deployda uni qayta tortmaydi
# (1 vCPU'da aynan shu pull+extract deployni sekinlashtirardi).
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=backend/uv.lock,target=uv.lock \
    --mount=type=bind,source=backend/pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-project

# --------- Final Stage ---------
FROM python:3.13-slim-bookworm

# curl — konteyner healthcheck'i (docker-compose: `curl -f .../api/v1/health`).
# fonts-liberation: yorliq PNG'si (render_label_png) TTF shriftsiz PIL'ning mayda
# bitmap fontiga tushib qolardi — chek o'qib bo'lmas holda chiqardi
RUN apt-get update && apt-get install -y --no-install-recommends curl fonts-liberation && rm -rf /var/lib/apt/lists/*

RUN groupadd --gid 1000 app \
    && useradd --uid 1000 --gid app --shell /bin/bash --create-home app

# Venv (barqaror qatlam — faqat lock o'zgarsa yangilanadi), keyin kod (kichik,
# har deployda o'zgaradigan qatlamlar OXIRIDA tursin)
COPY --from=builder --chown=app:app /app/backend/.venv /app/backend/.venv
COPY --chown=app:app backend /app/backend
COPY --chown=app:app scripts /app/scripts

# `backend/uploads` .dockerignore'da — ya'ni image'da bunday katalog YO'Q.
# Prodda u named volume mount nuqtasi: Docker bo'sh volume'ni mount qilganda
# mavjud katalogning egaligini ko'chiradi, katalog bo'lmasa esa root:root bilan
# yaratadi — konteyner uid 1000 (`USER app`) ostida ishlagani uchun har qanday
# fayl yuklash EACCES bilan yiqilardi. Shuning uchun oldindan yaratamiz.
RUN mkdir -p /app/backend/uploads && chown app:app /app/backend/uploads

ENV PATH="/app/backend/.venv/bin:$PATH"
ENV PYTHONPATH="/app/backend"

USER app

WORKDIR /app/backend

EXPOSE 8000

# Default command (can be overridden in docker-compose)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
