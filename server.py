"""
server.py — FastAPI бэкенд для WB SpyGlass
Фронтенд вызывает:
  GET  /api/analyze/{sku}   — анализ конкурентов
  POST /api/ai-report       — SEO рекомендации через Claude API
"""

import os
import logging
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
import anthropic

load_dotenv()

from wb_api import WBClient

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

app = FastAPI(title="WB SpyGlass API")

# CORS — разрешаем фронтенду обращаться к бэкенду
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

API_KEY = os.getenv("API_KEY", "super_secret_wb_key_123")
WB_TOKEN = os.getenv("WB_TOKEN", "")
ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY", "")


def check_api_key(request: Request):
    key = request.headers.get("X-API-Key", "")
    if key != API_KEY:
        raise HTTPException(status_code=403, detail="Неверный API ключ")


# ─── /api/analyze/{sku} ───────────────────────────────────────────────────────

@app.get("/api/analyze/{sku}")
async def analyze(sku: str, request: Request):
    check_api_key(request)

    if not sku.isdigit():
        raise HTTPException(status_code=400, detail="Артикул должен быть числом")

    article_id = int(sku)
    log.info(f"Анализ артикула: {article_id}")

    client = WBClient(token=WB_TOKEN)
    main, competitors = client.find_competitors(article_id, top_n=5)

    if not main:
        raise HTTPException(
            status_code=404,
            detail="Товар не найден. Проверьте артикул или обновите WB_TOKEN в .env"
        )

    def fmt_price(p: float) -> str:
        return f"{p:,.0f} ₽".replace(",", " ")

    return {
        "target_product": {
            "sku": str(article_id),
            "name": main.name,
            "brand": main.brand,
            "price": fmt_price(main.price),
            "rating": main.rating,
            "feedbacks": main.feedbacks,
            "demand_score": main.demand_score,
            "url": main.url,
        },
        "competitors": [
            {
                "name": c.name,
                "brand": c.brand,
                "price": fmt_price(c.price),
                "price_raw": c.price,
                "rating": c.rating,
                "feedbacks": c.feedbacks,
                "demand_score": c.demand_score,
                "url": c.url,
            }
            for c in competitors
        ],
        "market": {
            "avg_price": fmt_price(
                sum(c.price for c in competitors) / len(competitors)
            ) if competitors else "—",
            "avg_rating": round(
                sum(c.rating for c in competitors) / len(competitors), 2
            ) if competitors else 0,
            "avg_demand": round(
                sum(c.demand_score for c in competitors) / len(competitors), 1
            ) if competitors else 0,
        }
    }


# ─── /api/ai-report ───────────────────────────────────────────────────────────

@app.post("/api/ai-report")
async def ai_report(request: Request):
    check_api_key(request)

    if not ANTHROPIC_KEY:
        raise HTTPException(
            status_code=503,
            detail="ANTHROPIC_API_KEY не задан в .env"
        )

    data = await request.json()
    target = data.get("target_product", {})
    competitors = data.get("competitors", [])

    if not target or not competitors:
        raise HTTPException(status_code=400, detail="Нет данных для анализа")

    # Формируем промпт
    comp_list = "\n".join(
        f"- {c['name']} | {c['price']} | ⭐{c['rating']} | {c['feedbacks']} отз."
        for c in competitors[:5]
    )

    prompt = f"""Ты — эксперт по SEO на маркетплейсе Wildberries.

Наш товар:
Название: {target['name']}
Бренд: {target['brand']}
Цена: {target['price']}
Рейтинг: {target['rating']}
Отзывов: {target['feedbacks']}

Топ-5 конкурентов:
{comp_list}

Проанализируй и верни JSON (только JSON, без markdown):
{{
  "optimized_title": "улучшенное название товара для WB (до 100 символов)",
  "missing_keywords": ["ключ1", "ключ2", "ключ3"],
  "recommendations": "3-4 конкретных совета по улучшению карточки"
}}"""

    try:
        client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)
        message = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}]
        )
        import json
        text = message.content[0].text.strip()
        # Убираем markdown если есть
        text = text.replace("```json", "").replace("```", "").strip()
        result = json.loads(text)
        return result
    except Exception as e:
        log.error(f"AI ошибка: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ─── Health check ─────────────────────────────────────────────────────────────

@app.get("/")
async def root():
    return {"status": "ok", "service": "WB SpyGlass API"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
