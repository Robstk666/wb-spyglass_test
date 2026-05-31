"""
wb_api.py — Клиент для открытых API Wildberries.
"""

import time
import logging
from dataclasses import dataclass, field
from typing import Optional
from curl_cffi import requests

logger = logging.getLogger(__name__)

SEARCH_URL = "https://search.wb.ru/exactmatch/ru/common/v18/search"

DEFAULT_PARAMS: dict = {
    "appType": "1",
    "curr": "rub",
    "dest": "-1257786",
    "lang": "ru",
    "resultset": "catalog",
    "sort": "popular",
    "spp": "30",
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "*/*",
    "Origin": "https://www.wildberries.ru",
    "Referer": "https://www.wildberries.ru/",
}


@dataclass
class WBProduct:
    id: int
    name: str
    brand: str
    price: float
    rating: float
    feedbacks: int
    supplier: str
    supplier_rating: float
    position: int
    volume: int
    demand_score: float = field(init=False)

    def __post_init__(self):
        rev = min(self.feedbacks / 1000, 1.0) * 100
        rat = self.rating * 20
        sal = min((self.feedbacks * 12) / 10_000, 1.0) * 100
        self.demand_score = round(rev * 0.4 + rat * 0.3 + sal * 0.3, 1)

    @property
    def url(self) -> str:
        return f"https://www.wildberries.ru/catalog/{self.id}/detail.aspx"


class WBClient:
    def __init__(self, token: Optional[str] = None, rate_delay: float = 0.8):
        self._token = token
        self._rate_delay = rate_delay
        self._session = requests.Session(impersonate="chrome")
        self._session.headers.update(HEADERS)

    def search(self, query: str, page: int = 1, limit: int = 100) -> list[WBProduct]:
        raw = self._search_raw(query, page)
        if raw is None:
            return []
        products_raw = self._extract_products(raw)
        return [
            self._parse_product(p, pos)
            for pos, p in enumerate(products_raw[:limit], start=(page - 1) * 100 + 1)
        ]

    def find_competitors(
        self, article_id: int, top_n: int = 5
    ) -> tuple[Optional[WBProduct], list[WBProduct]]:
        main = self._find_by_article(article_id)
        if not main:
            return None, []

        query_words = " ".join(main.name.split()[:3])
        logger.info(f"Ищем конкурентов по: «{query_words}»")
        all_products = self.search(query_words, limit=100)

        competitors = [
            p for p in all_products
            if p.id != article_id and self._in_price_range(main.price, p.price)
        ]
        competitors.sort(key=lambda x: x.demand_score, reverse=True)
        return main, competitors[:top_n]

    def get_rank(self, article_id: int, query: str) -> Optional[int]:
        raw = self._search_raw(query, page=1)
        if raw is None:
            return None
        for idx, p in enumerate(self._extract_products(raw), start=1):
            if p.get("id") == article_id:
                return idx
        return None

    # ── Внутренние методы ────────────────────────────────────────────────

    @staticmethod
    def _extract_products(raw: dict) -> list:
        """
        WB менял структуру ответа:
          - раньше: {"data": {"products": [...]}}
          - сейчас: {"products": [...], "total": N}
        Поддерживаем оба варианта.
        """
        # Новый формат (май 2025+)
        if "products" in raw:
            return raw["products"]
        # Старый формат
        return raw.get("data", {}).get("products", [])

    def _find_by_article(self, article_id: int) -> Optional[WBProduct]:
        raw = self._search_raw(str(article_id), page=1)
        if raw:
            for pos, p in enumerate(self._extract_products(raw), 1):
                if p.get("id") == article_id:
                    return self._parse_product(p, pos)
        # Фолбэк: карточка напрямую
        return self._fallback_card_detail(article_id)

    def _fallback_card_detail(self, article_id: int) -> Optional[WBProduct]:
        for url in [
            "https://card.wb.ru/cards/v3/detail",
            "https://card.wb.ru/cards/detail",
        ]:
            try:
                resp = self._session.get(
                    url,
                    params={"appType": "1", "curr": "rub", "dest": "-1257786", "nm": str(article_id)},
                    timeout=10,
                )
                if resp.status_code == 200:
                    products = self._extract_products(resp.json())
                    if products:
                        return self._parse_product(products[0], 1)
            except Exception:
                continue
        return None

    def _search_raw(self, query: str, page: int = 1) -> Optional[dict]:
        params = {**DEFAULT_PARAMS, "query": query, "page": str(page)}
        cookies = {"xwb-token": self._token} if self._token else {}
        try:
            resp = self._session.get(
                SEARCH_URL, params=params, cookies=cookies, timeout=12
            )
            if resp.status_code == 200:
                return resp.json()
            logger.error(f"WB вернул статус {resp.status_code}")
        except Exception as e:
            logger.error(f"Сетевая ошибка: {e}")
        time.sleep(self._rate_delay)
        return None

    @staticmethod
    def _parse_product(raw: dict, position: int) -> WBProduct:
        sizes = raw.get("sizes", [{}])
        price_raw = sizes[0].get("price", {}).get("product", 0) if sizes else 0
        rating = raw.get("reviewRating", 0)
        return WBProduct(
            id=raw.get("id", 0),
            name=raw.get("name", ""),
            brand=raw.get("brand", ""),
            price=price_raw / 100,
            rating=rating / 10 if rating > 10 else rating,
            feedbacks=raw.get("feedbacks", 0),
            supplier=raw.get("supplier", ""),
            supplier_rating=raw.get("supplierRating", 0),
            position=position,
            volume=raw.get("volume", 0),
        )

    @staticmethod
    def _in_price_range(base: float, price: float, tolerance: float = 0.30) -> bool:
        if base <= 0:
            return True
        return (base * (1 - tolerance)) <= price <= (base * (1 + tolerance))
