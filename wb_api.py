"""
wb_api.py
---------
Клиент для открытых API Wildberries.

Источники:
  - Статья «Парсинг цен и данных о товарах конкурентов на Wildberries» (Amvera/Habr)
  - Видео Parsub: обход защиты WB + поиск позиции товара

Как работает защита WB (май 2026):
  1. При первом открытии wildberries.ru браузер решает JS-challenge
     (Cloudflare / собственный антибот).
  2. После решения сервер записывает cookie xwb-token (~2 недели).
  3. search.wb.ru/exactmatch/... без этого cookie → HTTP 498.
  4. Решение: получаем токен через undetected-Chrome (get_token.py),
     затем все запросы делаем обычным requests с этим токеном в cookies.

Поведение при 498:
  - Класс автоматически вызывает get_wb_token() для обновления.
  - До 2 повторных попыток.
"""

import time
import logging
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import quote

import requests

logger = logging.getLogger(__name__)


# ─── Настройки ───────────────────────────────────────────────────────────────

# URL из статьи (v18 – актуальный на момент написания)
SEARCH_URL = "https://search.wb.ru/exactmatch/ru/common/v18/search"

# Параметры по умолчанию из статьи
DEFAULT_PARAMS: dict = {
    "appType": "1",        # 1 = веб, 4 = мобильное
    "curr": "rub",
    "dest": "-1257786",    # регион (Москва по умолчанию)
    "lang": "ru",
    "resultset": "catalog",
    "sort": "popular",
    "spp": "30",
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "*/*",
    "Accept-Language": "ru-RU,ru;q=0.9",
    "Origin": "https://www.wildberries.ru",
    "Referer": "https://www.wildberries.ru/",
}


# ─── Модели данных ───────────────────────────────────────────────────────────

@dataclass
class WBProduct:
    """Товар из поисковой выдачи WB."""
    id: int
    name: str
    brand: str
    price: float           # рублей, уже делённые на 100
    rating: float          # 1-5
    feedbacks: int         # количество отзывов
    supplier: str
    supplier_rating: float
    position: int          # позиция в поиске (1-based)
    volume: int            # наличие

    # Расчётная метрика «силы» конкурента
    demand_score: float = field(init=False)

    def __post_init__(self):
        self.demand_score = self._calc_demand_score()

    def _calc_demand_score(self) -> float:
        """
        Взвешенная метрика 0-100.
        Формула:
          reviews_score (40%) = min(feedbacks/1000, 1) * 100
          rating_score  (30%) = rating * 20          (5 звёзд → 100)
          sales_est     (30%) = min(feedbacks*12/10000, 1)*100
        """
        rev = min(self.feedbacks / 1000, 1.0) * 100
        rat = self.rating * 20
        sal = min((self.feedbacks * 12) / 10_000, 1.0) * 100
        return round(rev * 0.4 + rat * 0.3 + sal * 0.3, 1)

    @property
    def url(self) -> str:
        return f"https://www.wildberries.ru/catalog/{self.id}/detail.aspx"

    def __str__(self) -> str:
        bar_len = int(self.demand_score / 10)
        bar = "▓" * bar_len + "░" * (10 - bar_len)
        return (
            f"  #{self.position:>3}  {self.name[:55]}\n"
            f"       💰 {self.price:>8,.0f} ₽   "
            f"⭐ {self.rating:.1f}   "
            f"💬 {self.feedbacks:,}\n"
            f"       📊 [{bar}] {self.demand_score}/100   "
            f"🏪 {self.supplier}\n"
            f"       🔗 {self.url}"
        )


# ─── Основной клиент ─────────────────────────────────────────────────────────

class WBClient:
    """
    Клиент для поиска товаров через открытый API WB.

    Пример:
        client = WBClient(token="xwb-token-value")
        products = client.search("джинсы женские", limit=50)
    """

    def __init__(self, token: Optional[str] = None, rate_delay: float = 0.8):
        """
        token      – значение cookie xwb-token (получить через get_token.py).
                     Если None, первый запрос попробует без токена,
                     и при 498 запросит токен автоматически.
        rate_delay – задержка между запросами (рекомендуется ≥0.5 с).
        """
        self._token = token
        self._rate_delay = rate_delay
        self._session = requests.Session()
        self._session.headers.update(HEADERS)

    # ── Публичные методы ──────────────────────────────────────────────────

    def search(self, query: str, page: int = 1, limit: int = 100) -> list[WBProduct]:
        """
        Поиск товаров по запросу.
        Возвращает список WBProduct, отсортированный по позиции.
        """
        raw = self._search_raw(query, page)
        if raw is None:
            return []

        products_raw = raw.get("data", {}).get("products", [])
        result = []
        for pos, p in enumerate(products_raw[:limit], start=(page - 1) * 100 + 1):
            result.append(self._parse_product(p, pos))
        return result

    def find_competitors(
        self,
        article_id: int,
        top_n: int = 5,
    ) -> tuple[Optional[WBProduct], list[WBProduct]]:
        """
        Находит топ-N конкурентов для товара.

        Алгоритм:
        1. Ищем сам товар (берём первую страницу, ищем по id).
        2. Используем название для нового поиска.
        3. Фильтруем по ценовому диапазону ±30 %.
        4. Сортируем по demand_score, исключаем сам товар.

        Возвращает: (основной товар, список конкурентов).
        """
        # 1. Ищем основной товар по артикулу через поиск
        main = self._find_by_article(article_id)
        if main is None:
            logger.warning(f"Товар {article_id} не найден через поиск")
            return None, []

        # 2. Ищем похожие товары по первым словам названия
        query_words = " ".join(main.name.split()[:3])
        logger.info(f"Поиск конкурентов по: «{query_words}»")

        all_products = self.search(query_words, limit=100)
        time.sleep(self._rate_delay)

        # 3. Фильтрация и ранжирование
        competitors = []
        for p in all_products:
            if p.id == article_id:
                continue
            if not self._in_price_range(main.price, p.price, tolerance=0.30):
                continue
            competitors.append(p)

        competitors.sort(key=lambda x: x.demand_score, reverse=True)
        return main, competitors[:top_n]

    def get_rank(self, article_id: int, query: str) -> Optional[int]:
        """
        Возвращает позицию товара в поисковой выдаче по запросу.
        None — если товар не найден на первой странице (100 позиций).
        """
        raw = self._search_raw(query, page=1)
        if raw is None:
            return None
        products = raw.get("data", {}).get("products", [])
        for idx, p in enumerate(products, start=1):
            if p.get("id") == article_id:
                return idx
        return None

    # ── Внутренние методы ────────────────────────────────────────────────

    def _find_by_article(self, article_id: int) -> Optional[WBProduct]:
        """Ищет конкретный артикул в выдаче."""
        # Прямой поиск по артикулу (иногда работает)
        raw = self._search_raw(str(article_id), page=1)
        if raw:
            for pos, p in enumerate(raw.get("data", {}).get("products", []), 1):
                if p.get("id") == article_id:
                    return self._parse_product(p, pos)
        return None

    def _search_raw(self, query: str, page: int = 1) -> Optional[dict]:
        """
        Делает GET-запрос к search.wb.ru.
        При 498 — пытается обновить токен и повторяет.
        """
        params = {**DEFAULT_PARAMS, "query": quote(query, safe=""), "page": str(page)}
        cookies = {}
        if self._token:
            cookies["xwb-token"] = self._token

        for attempt in range(1, 3):
            try:
                resp = self._session.get(
                    SEARCH_URL,
                    params=params,
                    cookies=cookies,
                    timeout=12,
                )
                logger.debug(f"[{attempt}] {query!r} → HTTP {resp.status_code}")

                if resp.status_code == 200:
                    return resp.json()

                if resp.status_code == 498:
                    logger.warning("498: токен невалиден, обновляем…")
                    new_token = self._refresh_token()
                    if new_token:
                        self._token = new_token
                        cookies["xwb-token"] = new_token
                    continue

                logger.error(f"HTTP {resp.status_code}: {resp.text[:120]}")
                return None

            except requests.RequestException as exc:
                logger.error(f"Запрос упал: {exc}")
                return None
            finally:
                time.sleep(self._rate_delay)

        return None

    def _refresh_token(self) -> Optional[str]:
        """Получает свежий токен через seleniumbase."""
        try:
            from get_token import get_wb_token  # type: ignore
            return get_wb_token(headless=True)
        except ImportError:
            logger.error("get_token.py не найден; установи seleniumbase")
            return None
        except Exception as exc:
            logger.error(f"Не удалось обновить токен: {exc}")
            return None

    # ── Парсинг ──────────────────────────────────────────────────────────

    @staticmethod
    def _parse_product(raw: dict, position: int) -> WBProduct:
        """Строит WBProduct из сырого JSON (формат из статьи)."""
        sizes = raw.get("sizes", [{}])
        price_data = sizes[0].get("price", {}) if sizes else {}
        price_raw = price_data.get("product", 0)

        return WBProduct(
            id=raw.get("id", 0),
            name=raw.get("name", ""),
            brand=raw.get("brand", ""),
            price=price_raw / 100,                     # копейки → рубли (из статьи!)
            rating=raw.get("reviewRating", 0) / 10     # WB хранит как 47 = 4.7
                   if raw.get("reviewRating", 0) > 10
                   else raw.get("reviewRating", 0),
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
