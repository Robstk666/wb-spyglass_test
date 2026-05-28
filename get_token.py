"""
get_token.py
------------
Получает WB-токен (xwb-token из cookie) через undetected-Chrome.
Логика взята из видео Parsub: WB проверяет браузер через JS-challenge,
выдаёт cookie xwb-token со сроком ~2 недели.
Без этого токена search.wb.ru возвращает 498.

Требует: seleniumbase (pip install seleniumbase)
Запуск:  python get_token.py  -> выводит токен в stdout
"""

import time
from typing import Optional


class WBTokenGetter:
    """Получает xwb-token через headless Selenium (undetected Chrome)."""

    WB_URL = "https://www.wildberries.ru/"
    COOKIE_NAME = "xwb-token"
    RETRIES = 3
    WAIT_SEC = 5

    def __init__(self, headless: bool = True):
        self.headless = headless

    def get_token(self) -> Optional[str]:
        """Возвращает строку токена или None."""
        try:
            from seleniumbase import Driver  # type: ignore
        except ImportError:
            raise RuntimeError(
                "seleniumbase не установлен. Выполни: pip install seleniumbase"
            )

        driver = Driver(uc=True, headless=self.headless)
        try:
            driver.open(self.WB_URL)
            for attempt in range(1, self.RETRIES + 1):
                print(f"  [get_token] попытка {attempt}/{self.RETRIES}…")
                # Получаем ВСЕ куки через CDP (обходит httpOnly)
                all_cookies = driver.execute_cdp_cmd(
                    "Network.getAllCookies", {}
                )
                for cookie in all_cookies.get("cookies", []):
                    if cookie.get("name") == self.COOKIE_NAME:
                        token = cookie["value"]
                        print(f"  [get_token] токен получен (длина {len(token)})")
                        return token
                time.sleep(self.WAIT_SEC)
            print("  [get_token] токен не найден за все попытки")
            return None
        finally:
            driver.quit()


def get_wb_token(headless: bool = True) -> Optional[str]:
    """Удобная функция-обёртка для использования из других модулей."""
    return WBTokenGetter(headless=headless).get_token()


if __name__ == "__main__":
    token = get_wb_token(headless=False)   # headless=False, чтобы видеть браузер
    if token:
        print(f"\nТокен:\n{token}")
    else:
        print("Не удалось получить токен")
