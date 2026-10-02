
    import asyncio
import logging
import os
import math
import random
from datetime import datetime, timezone, timedelta

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
    ChatType,
)
from aiohttp import web

# ─────────────────────── НАСТРОЙКИ ───────────────────────
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
PORT = int(os.getenv("PORT", 8080))
MSK = timezone(timedelta(hours=3))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
log = logging.getLogger("MathBot")

bot = Bot(token=TOKEN)
dp = Dispatcher()

# ─────────────────────── БЕЗОПАСНЫЙ КАЛЬКУЛЯТОР ───────────────────────
# Разрешаем только цифры, операторы и математические функции.
ALLOWED_NAMES = {
    k: v for k, v in math.__dict__.items() if not k.startswith("_")
}
ALLOWED_NAMES.update({"abs": abs, "round": round, "min": min, "max": max})


def safe_eval(expr: str) -> float:
    expr = expr.replace("^", "**")
    # Запрещаем опасные символы
    forbidden = ["__", "import", "open", "eval", "exec", "lambda", "os", "sys"]
    for f in forbidden:
        if f in expr.lower():
            raise ValueError("Недопустимое выражение")
    code = compile(expr, "<calc>", "eval")
    for name in code.co_names:
        if name not in ALLOWED_NAMES:
            raise ValueError(f"Функция '{name}' не разрешена")
    return eval(code, {"__builtins__": {}}, ALLOWED_NAMES)


# ─────────────────────── КЛАВИАТУРА ───────────────────────
def main_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🧮 Калькулятор", callback_data="help_calc"),
            InlineKeyboardButton(text="🔢 Простое число", callback_data="help_prime"),
        ],
        [
            InlineKeyboardButton(text="❗ Факториал", callback_data="help_fact"),
            InlineKeyboardButton(text="🌀 Фибоначчи", callback_data="help_fib"),
        ],
        [
            InlineKeyboardButton(text="🔗 НОД / НОК", callback_data="help_gcd"),
            InlineKeyboardButton(text="📐 Квадратное ур.", callback_data="help_quad"),
        ],
        [
            InlineKeyboardButton(text="⚡ Степень", callback_data="help_pow"),
            InlineKeyboardButton(text="√ Корень", callback_data="help_sqrt"),
        ],
        [
            InlineKeyboardButton(text="🎲 Случайное число", callback_data="help_rand"),
        ],
    ])


HELP_TEXT = (
    "🧮 <b>MathBot</b> — твой помощник в математике\n\n"
    "<b>Команды:</b>\n"
    "• <code>/calc 2+2*2</code> — вычислить выражение\n"
    "• <code>/prime 17</code> — проверить, простое ли число\n"
    "• <code>/fact 5</code> — факториал\n"
    "• <code>/fib 10</code> — N-е число Фибоначчи\n"
    "• <code>/gcd 12 18</code> — НОД и НОК\n"
    "• <code>/quad 1 -5 6</code> — корни ax²+bx+c=0\n"
    "• <code>/pow 2 10</code> — 2 в степени 10\n"
    "• <code>/sqrt 144</code> — квадратный корень\n"
    "• <code>/rand 1 100</code> — случайное число в диапазоне\n\n"
    "💡 <i>Поддерживаются:</i> + − * / ** sqrt sin cos log pi e"
)


# ─────────────────────── КОМАНДЫ ───────────────────────
@dp.message(CommandStart())
async def cmd_start(message: Message):
    name = message.from_user.first_name or "друг"
    await message.answer(
        f"👋 Привет, <b>{name}</b>!\n\n{HELP_TEXT}",
        parse_mode="HTML",
        reply_markup=main_kb(),
    )


@dp.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(HELP_TEXT, parse_mode="HTML", reply_markup=main_kb())


# ─── /calc ───
@dp.message(Command("calc"))
async def cmd_calc(message: Message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        return await message.answer("📝 Использование: <code>/calc 2+2*2</code>", parse_mode="HTML")
    try:
        result = safe_eval(args[1])
        if isinstance(result, float) and result.is_integer():
            result = int(result)
        await message.answer(
            f"🧮 <code>{args[1]}</code> = <b>{result}</b>",
            parse_mode="HTML",
        )
    except Exception as e:
        await message.answer(f"❌ Ошибка: <code>{e}</code>", parse_mode="HTML")


# ─── /prime ───
@dp.message(Command("prime"))
async def cmd_prime(message: Message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        return await message.answer("📝 Использование: <code>/prime 17</code>", parse_mode="HTML")
    try:
        n = int(args[1])
    except ValueError:
        return await message.answer("❌ Нужно целое число.")

    if n < 2:
        return await message.answer(f"❌ {n} — не простое число.")

    is_prime = all(n % i != 0 for i in range(2, int(n ** 0.5) + 1))
    if is_prime:
        await message.answer(f"✅ <b>{n}</b> — простое число!", parse_mode="HTML")
    else:
        divisors = [i for i in range(2, n) if n % i == 0][:5]
        await message.answer(
            f"❌ <b>{n}</b> — составное.\nДелители: {', '.join(map(str, divisors))}…",
            parse_mode="HTML",
        )


# ─── /fact ───
@dp.message(Command("fact"))
async def cmd_fact(message: Message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        return await message.answer("📝 Использование: <code>/fact 5</code>", parse_mode="HTML")
    try:
        n = int(args[1])
        if n < 0 or n > 1000:
            return await message.answer("❌ Число от 0 до 1000.")
        result = math.factorial(n)
        if n <= 20:
            await message.answer(f"❗ <b>{n}!</b> = <code>{result}</code>", parse_mode="HTML")
        else:
            await message.answer(f"❗ <b>{n}!</b> ≈ <code>{result:.3e}</code>", parse_mode="HTML")
    except ValueError:
        await message.answer("❌ Нужно целое число.")


# ─── /fib ───
@dp.message(Command("fib"))
async def cmd_fib(message: Message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        return await message.answer("📝 Использование: <code>/fib 10</code>", parse_mode="HTML")
    try:
        n = int(args[1])
        if n < 0 or n > 1000:
            return await message.answer("❌ N от 0 до 1000.")
        a, b = 0, 1
        for _ in range(n):
            a, b = b, a + b
        await message.answer(f"🌀 F({n}) = <b>{a}</b>", parse_mode="HTML")
    except ValueError:
        await message.answer("❌ Нужно целое число.")


# ─── /gcd ───
@dp.message(Command("gcd"))
async def cmd_gcd(message: Message):
    args = message.text.split()
    if len(args) < 3:
        return await message.answer("📝 Использование: <code>/gcd 12 18</code>", parse_mode="HTML")
    try:
        a, b = int(args[1]), int(args[2])
        g = math.gcd(a, b)
        l = abs(a * b) // g if g else 0
        await message.answer(
            f"🔗 НОД({a}, {b}) = <b>{g}</b>\n📏 НОК({a}, {b}) = <b>{l}</b>",
            parse_mode="HTML",
        )
    except ValueError:
        await message.answer("❌ Нужны два целых числа.")


# ─── /quad ───
@dp.message(Command("quad"))
async def cmd_quad(message: Message):
    args = message.text.split()
    if len(args) < 4:
        return await message.answer(
            "📝 Использование: <code>/quad a b c</code>\nПример: <code>/quad 1 -5 6</code>",
            parse_mode="HTML",
        )
    try:
        a, b, c = float(args[1]), float(args[2]), float(args[3])
    except ValueError:
        return await message.answer("❌ Коэффициенты должны быть числами.")

    if a == 0:
        return await message.answer("❌ a не может быть 0 (иначе это не квадратное).")

    d = b * b - 4 * a * c
    text = f"📐 <b>{a}x² + {b}x + {c} = 0</b>\n\nДискриминант D = <b>{d}</b>\n\n"

    if d > 0:
        x1 = (-b + math.sqrt(d)) / (2 * a)
        x2 = (-b - math.sqrt(d)) / (2 * a)
        text += f"✅ Два корня:\nx₁ = <b>{x1:.4g}</b>\nx₂ = <b>{x2:.4g}</b>"
    elif d == 0:
        x = -b / (2 * a)
        text += f"✅ Один корень:\nx = <b>{x:.4g}</b>"
    else:
        text += "❌ Корней нет (D < 0)"

    await message.answer(text, parse_mode="HTML")


# ─── /pow ───
@dp.message(Command("pow"))
async def cmd_pow(message: Message):
    args = message.text.split()
    if len(args) < 3:
        return await message.answer("📝 Использование: <code>/pow 2 10</code>", parse_mode="HTML")
    try:
        base, exp = float(args[1]), float(args[2])
        result = base ** exp
        if result.is_integer():
            result = int(result)
        await message.answer(
            f"⚡ <b>{base}^{exp}</b> = <code>{result}</code>",
            parse_mode="HTML",
        )
    except Exception:
        await message.answer("❌ Нужны два числа.")


# ─── /sqrt ───
@dp.message(Command("sqrt"))
async def cmd_sqrt(message: Message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        return await message.answer("📝 Использование: <code>/sqrt 144</code>", parse_mode="HTML")
    try:
        n = float(args[1])
        if n < 0:
            return await message.answer("❌ Корень из отрицательного не берётся (в ℝ).")
        r = math.sqrt(n)
        if r.is_integer():
            r = int(r)
        await message.answer(f"√ <b>{n}</b> = <code>{r}</code>", parse_mode="HTML")
    except ValueError:
        await message.answer("❌ Нужно число.")


# ─── /rand ───
@dp.message(Command("rand"))
async def cmd_rand(message: Message):
    args = message.text.split()
    if len(args) < 3:
        return await message.answer("📝 Использование: <code>/rand 1 100</code>", parse_mode="HTML")
    try:
        a, b = int(args[1]), int(args[2])
        if a > b:
            a, b = b, a
        r = random.randint(a, b)
        await message.answer(f"🎲 Случайное число от {a} до {b}: <b>{r}</b>", parse_mode="HTML")
    except ValueError:
        await message.answer("❌ Нужны два целых числа.")


# ─────────────────────── CALLBACK-КНОПКИ ───────────────────────
@dp.callback_query(F.data.startswith("help_"))
async def cb_help(callback: CallbackQuery):
    mapping = {
        "help_calc":  "🧮 <b>Калькулятор</b>\n\n<code>/calc 2+2*2</code>\n<code>/calc sqrt(16) + sin(0)</code>\n<code>/calc 2**10</code>",
        "help_prime": "🔢 <b>Простое число</b>\n\n<code>/prime 17</code>",
        "help_fact":  "❗ <b>Факториал</b>\n\n<code>/fact 5</code> → 120",
        "help_fib":   "🌀 <b>Фибоначчи</b>\n\n<code>/fib 10</code> → F(10) = 55",
        "help_gcd":   "🔗 <b>НОД / НОК</b>\n\n<code>/gcd 12 18</code>",
        "help_quad":  "📐 <b>Квадратное уравнение</b>\n\n<code>/quad 1 -5 6</code> → x² − 5x + 6 = 0",
        "help_pow":   "⚡ <b>Степень</b>\n\n<code>/pow 2 10</code> → 1024",
        "help_sqrt":  "√ <b>Корень</b>\n\n<code>/sqrt 144</code> → 12",
        "help_rand":  "🎲 <b>Случайное число</b>\n\n<code>/rand 1 100</code>",
    }
    await callback.message.answer(mapping.get(callback.data, "❓"), parse_mode="HTML")
    await callback.answer()


# ─────────────────────── ВЕБ-СЕРВЕР (health-check) ───────────────────────
async def health(request):
    return web.Response(text="MathBot is running 🧮")


async def start_web():
    app = web.Application()
    app.router.add_get("/", health)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    log.info("Health-check на порту %s", PORT)


# ─────────────────────── ЗАПУСК ───────────────────────
async def main():
    await start_web()
    log.info("MathBot запущен.")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        log.info("MathBot остановлен.")
