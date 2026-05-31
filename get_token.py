"""
get_token.py
------------
Получает WB-токен (xwb-token из cookie) через undetected-Brave.
"""
import time
from typing import Optional

class WBTokenGetter:
    WB_URL = "https://www.wildberries.ru/"
    COOKIE_NAME = "xwb-token"
    RETRIES = 3
    WAIT_SEC = 5

    def __init__(self, headless: bool = False):
        self.headless = False

    def get_token(self) -> Optional[str]:
        try:
            from seleniumbase import Driver
        except ImportError:
            raise RuntimeError("seleniumbase не установлен.")

        # Маскируем Brave под Chrome, чтобы угодить модулю undetected
        driver = Driver(
            uc=True,
            headless=False,
            browser="chrome",
            binary_location="/Applications/Brave Browser.app/Contents/MacOS/Brave Browser"
        )
        try:
            driver.open(self.WB_URL)
            for attempt in range(1, self.RETRIES + 1):
                print(f"  [get_token] попытка {attempt}/{self.RETRIES}…")
                time.sleep(self.WAIT_SEC)
                
                # Используем стандартный безотказный метод вместо глючного CDP
                all_cookies = driver.get_cookies()
                
                for cookie in all_cookies:
                    if cookie.get("name") == self.COOKIE_NAME:
                        token = cookie["value"]
                        print(f"  [get_token] токен получен (длина {len(token)})")
                        
                        with open(".token", "w") as f:
                            f.write(token)
                        return token
            print("  [get_token] токен не найден за все попытки")
            return None
        finally:
            driver.quit()

def get_wb_token(headless: bool = False) -> Optional[str]:
    return WBTokenGetter(headless=False).get_token()

if __name__ == "__main__":
    token = get_wb_token(headless=False)
    if token:
        print(f"\nТокен успешно сохранен!\n{token}")
    else:
        print("Не удалось получить токен")
