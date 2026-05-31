"""
bot.py — Telegram-бот для анализа конкурентов на WB
"""

import asyncio
import logging
import os
from pathlib import Path

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command, CommandObject
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from wb_api import WBClient, WBProduct

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

TG_TOKEN = os.getenv("TG_TOKEN", "")
WB_TOKEN_FILE = Path(".token")


def get_wb_token() -> str | None:
    t = os.getenv("WB_TOKEN", "").strip()
    if t:
        return t
    if WB_TOKEN_FILE.exists():
        t = WB_TOKEN_FILE.read_text().strip()
        if t:
            return t
    return None


def esc(text: str) -> str:
    """Экранирует все спецсимволы для MarkdownV2."""
    special = r'_*[]()~`>#+-=|{}.!'
    for ch in special:
        text = text.replace(ch, f'\\{ch}')
    return text


def fmt_product_short(p: WBProduct, index: int) -> str:
    bar_len = int(p.demand_score / 10)
    bar = "▓" * bar_len + "░" * (10 - bar_len)
    name = esc(p.name[:50])
    supplier = esc(p.supplier)
    price = esc(f"{p.price:,.0f}")
    rating = esc(f"{p.rating:.1f}")
    feedbacks = esc(f"{p.feedbacks:,}")
    score = esc(f"{p.demand_score}")
    url = p.url

    prefix = f"*{index}\\. " if index > 0 else "*"
    return (
        f"{prefix}{name}*\n"
        f"   💰 `{price} ₽`  ⭐ `{rating}`  💬 `{feedbacks}`\n"
        f"   📊 `[{bar}]` `{score}/100`\n"
        f"   🏪 {supplier}\n"
        f"   🔗 [Открыть]({url})"
    )


def fmt_report(article_id: int, main: WBProduct | None, competitors: list[WBProduct]) -> str:
    lines = [f"📊 *Анализ конкурентов для арт\\. {article_id}*\n"]

    if main:
        lines.append("*🎯 Ваш товар:*")
        lines.append(fmt_product_short(main, 0))
        lines.append("")

    if not competitors:
        lines.append("⚠️ Конкуренты не найдены")
        return "\n".join(lines)

    lines.append(f"*🏆 Топ\\-{len(competitors)} конкурентов* \\(по силе↓\\):\n")
    for i, c in enumerate(competitors, 1):
        lines.append(fmt_product_short(c, i))
        lines.append("")

    avg_price = sum(c.price for c in competitors) / len(competitors)
    avg_rating = sum(c.rating for c in competitors) / len(competitors)
    avg_demand = sum(c.demand_score for c in competitors) / len(competitors)

    lines.append("─────────────────────")
    lines.append("*📈 Рынок в цифрах:*")
    lines.append(f"  Средняя цена: `{esc(f'{avg_price:,.0f}')} ₽`")
    lines.append(f"  Средний рейтинг: `{esc(f'{avg_rating:.2f}')}`")
    lines.append(f"  Средний спрос: `{esc(f'{avg_demand:.1f}')}/100`")

    if main:
        diff = main.price - avg_price
        sign = "выше" if diff > 0 else "ниже"
        lines.append(f"  Ваша цена: `{esc(f'{abs(diff):,.0f}')} ₽` {sign} рынка")

    best = max(competitors, key=lambda c: c.demand_score)
    lines.append("")
    lines.append("*💡 Главный конкурент:*")
    lines.append(f"  [{esc(best.name[:45])}]({best.url}) — score `{esc(str(best.demand_score))}`")

    return "\n".join(lines)


# ─── Handlers ────────────────────────────────────────────────────────────────

dp = Dispatcher()


@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    await message.answer(
        "👋 *WB Competitor Analyzer*\n\n"
        "Анализирую конкурентов на Wildberries по артикулу\\.\n\n"
        "*Команды:*\n"
        "  `/analyze 123456789` — топ\\-5 конкурентов\n"
        "  `/analyze 123456789 10` — топ\\-10\n"
        "  `/rank 123456789 джинсы` — позиция в поиске\n"
        "  `/help` — справка\n\n"
        "Или просто отправь артикул товара 👇",
        parse_mode=ParseMode.MARKDOWN_V2,
    )


@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    await message.answer(
        "*Справка*\n\n"
        "*Откуда брать артикул?*\n"
        "Из URL страницы товара:\n"
        "`wildberries\\.ru/catalog/123456789/detail\\.aspx`\n\n"
        "*Как определяется «сильный» конкурент?*\n"
        "По метрике demand\\_score \\(0–100\\):\n"
        "  • Отзывы × 40%\n"
        "  • Рейтинг × 30%\n"
        "  • Продажи × 30%\n\n"
        "*Как часто обновляются данные?*\n"
        "Каждый запрос — живые данные с WB\\.",
        parse_mode=ParseMode.MARKDOWN_V2,
    )


@dp.message(Command("analyze"))
async def cmd_analyze(message: types.Message, command: CommandObject):
    args = (command.args or "").split()
    if not args:
        await message.answer(
            "⚠️ Укажи артикул\\. Пример: `/analyze 123456789`",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

    try:
        article_id = int(args[0])
    except ValueError:
        await message.answer("⚠️ Артикул должен быть числом")
        return

    top_n = 5
    if len(args) >= 2:
        try:
            top_n = max(1, min(int(args[1]), 10))
        except ValueError:
            pass

    wait_msg = await message.answer(
        f"🔍 Анализирую арт\\. `{article_id}`\\.\\.\\.",
        parse_mode=ParseMode.MARKDOWN_V2,
    )

    wb_token = get_wb_token()
    if not wb_token:
        await wait_msg.edit_text(
            "❌ *WB токен не настроен*\n\n"
            "Добавь в файл `\\.env`:\n"
            "`WB\\_TOKEN=значение\\_токена`\n\n"
            "Как получить — смотри README\\.",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

    try:
        client = WBClient(token=wb_token)
        main, competitors = await asyncio.to_thread(
            client.find_competitors, article_id, top_n
        )
        report = fmt_report(article_id, main, competitors)
        await wait_msg.edit_text(
            report,
            parse_mode=ParseMode.MARKDOWN_V2,
            disable_web_page_preview=True,
        )
    except Exception as e:
        log.error(f"analyze error: {e}", exc_info=True)
        await wait_msg.edit_text(
            f"❌ Ошибка: `{esc(str(e)[:200])}`",
            parse_mode=ParseMode.MARKDOWN_V2,
        )


@dp.message(Command("rank"))
async def cmd_rank(message: types.Message, command: CommandObject):
    args = (command.args or "").split(maxsplit=1)
    if len(args) < 2:
        await message.answer(
            "⚠️ Пример: `/rank 123456789 джинсы женские`",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

    try:
        article_id = int(args[0])
    except ValueError:
        await message.answer("⚠️ Артикул должен быть числом")
        return

    query = args[1].strip()
    wait_msg = await message.answer(
        f"🔍 Ищу позицию `{article_id}` по запросу *\"{esc(query)}\"*\\.\\.\\.",
        parse_mode=ParseMode.MARKDOWN_V2,
    )

    wb_token = get_wb_token()
    if not wb_token:
        await wait_msg.edit_text(
            "❌ WB токен не настроен\\. Смотри README\\.",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

    try:
        client = WBClient(token=wb_token)
        rank = await asyncio.to_thread(client.get_rank, article_id, query)

        if rank:
            await wait_msg.edit_text(
                f"📍 Арт\\. `{article_id}` по запросу *\"{esc(query)}\"*:\n\n"
                f"  Позиция: *\\#{rank}* из первых 100",
                parse_mode=ParseMode.MARKDOWN_V2,
            )
        else:
            await wait_msg.edit_text(
                f"😔 Арт\\. `{article_id}` не найден в топ\\-100\n"
                f"по запросу *\"{esc(query)}\"*",
                parse_mode=ParseMode.MARKDOWN_V2,
            )
    except Exception as e:
        log.error(f"rank error: {e}", exc_info=True)
        await wait_msg.edit_text(
            f"❌ Ошибка: `{esc(str(e)[:200])}`",
            parse_mode=ParseMode.MARKDOWN_V2,
        )


@dp.message(F.text.regexp(r"^\d{6,12}$"))
async def handle_bare_article(message: types.Message):
    article_id = int(message.text.strip())
    wait_msg = await message.answer(
        f"🔍 Анализирую арт\\. `{article_id}`\\.\\.\\.",
        parse_mode=ParseMode.MARKDOWN_V2,
    )

    wb_token = get_wb_token()
    if not wb_token:
        await wait_msg.edit_text(
            "❌ WB токен не настроен\\. Смотри README\\.",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

    try:
        client = WBClient(token=wb_token)
        main, competitors = await asyncio.to_thread(
            client.find_competitors, article_id, 5
        )
        report = fmt_report(article_id, main, competitors)
        await wait_msg.edit_text(
            report,
            parse_mode=ParseMode.MARKDOWN_V2,
            disable_web_page_preview=True,
        )
    except Exception as e:
        log.error(f"bare article error: {e}", exc_info=True)
        await wait_msg.edit_text(
            f"❌ Ошибка: `{esc(str(e)[:200])}`",
            parse_mode=ParseMode.MARKDOWN_V2,
        )


# ─── Запуск ───────────────────────────────────────────────────────────────────

async def main():
    if not TG_TOKEN:
        print("\n❌ Токен бота не задан!")
        print("   Создай файл .env и добавь строку:")
        print("   TG_TOKEN=токен_от_BotFather\n")
        return

    bot = Bot(TG_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN_V2))
    log.info("Бот запущен. Ctrl+C для остановки.")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
