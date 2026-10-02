import asyncio
import io
import logging
import math
import os
import random
import sqlite3
from datetime import datetime, timezone, timedelta

import matplotlib
matplotlib.use("Agg")  # без GUI
import matplotlib.pyplot as plt
import numpy as np

import sympy as sp

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
    BufferedInputFile,
    ChatType,
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from aiohttp import web

# ─────────────────────── НАСТРОЙКИ ───────────────────────
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
PORT = int(os.getenv("PORT", 8080))
MSK = timezone(timedelta(hours=3))
DB_PATH = "mathbot.db"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
log = logging.getLogger("MathBot")

bot = Bot(token=TOKEN)
dp = Dispatcher()

# ─────────────────────── FSM ───────────────────────
class TrainerState(StatesGroup):
    waiting_answer = State()


# ─────────────────────── БАЗА ДАННЫХ (для тренажёра) ───────────────────────
def db_init():
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS scores (
            user_id   INTEGER PRIMARY KEY,
            username  TEXT,
            correct   INTEGER DEFAULT 0,
            wrong     INTEGER DEFAULT 0
        )
    """)
    con.commit()
    con.close()


def db_get_score(user_id: int):
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute("SELECT correct, wrong FROM scores WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    con.close()
    return row or (0, 0)


def db_update_score(user_id: int, username: str, correct_inc: int = 0, wrong_inc: int = 0):
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute("INSERT OR IGNORE INTO scores (user_id, username) VALUES (?, ?)",
                (user_id, username))
    cur.execute("""
        UPDATE scores SET correct = correct + ?, wrong = wrong + ?, username = ?
        WHERE user_id = ?
    """, (correct_inc, wrong_inc, username, user_id))
    con.commit()
    con.close()


# ─────────────────────── БЕЗОПАСНЫЙ КАЛЬКУЛЯТОР ───────────────────────
ALLOWED_NAMES = {k: v for k, v in math.__dict__.items() if not k.startswith("_")}
ALLOWED_NAMES.update({"abs": abs, "round": round, "min": min, "max": max})


def safe_eval(expr: str) -> float:
    expr = expr.replace("^", "**")
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
            InlineKeyboardButton(text="🔢 Простое", callback_data="help_prime"),
        ],
        [
            InlineKeyboardButton(text="❗ Факториал", callback_data="help_fact"),
            InlineKeyboardButton(text="🌀 Фибоначчи", callback_data="help_fib"),
        ],
        [
            InlineKeyboardButton(text="🔗 НОД / НОК", callback_data="help_gcd"),
            InlineKeyboardButton(text="📐 Квадратное", callback_data="help_quad"),
        ],
        [
            InlineKeyboardButton(text="⚡ Степень", callback_data="help_pow"),
            InlineKeyboardButton(text="√ Корень", callback_data="help_sqrt"),
        ],
        [
            InlineKeyboardButton(text="🎲 Случайное", callback_data="help_rand"),
            InlineKeyboardButton(text="📊 График", callback_data="help_plot"),
        ],
        [
            InlineKeyboardButton(text="📏 Система ур.", callback_data="help_system"),
            InlineKeyboardButton(text="🌍 Системы счисления", callback_data="help_base"),
        ],
        [
            InlineKeyboardButton(text="🧠 Тренажёр", callback_data="help_trainer"),
            InlineKeyboardButton(text="🏆 Мой счёт", callback_data="help_score"),
        ],
    ])


HELP_TEXT = (
    "🧮 <b>MathBot</b> — твой помощник в математике\n\n"
    "<b>Команды:</b>\n"
    "• <code>/calc 2+2*2</code> — вычислить\n"
    "• <code>/prime 17</code> — простое ли число\n"
    "• <code>/fact 5</code> — факториал\n"
    "• <code>/fib 10</code> — число Фибоначчи\n"
    "• <code>/gcd 12 18</code> — НОД и НОК\n"
    "• <code>/quad 1 -5 6</code> — корни ax²+bx+c=0\n"
    "• <code>/pow 2 10</code> — степень\n"
    "• <code>/sqrt 144</code> — корень\n"
    "• <code>/rand 1 100</code> — случайное число\n"
    "• <code>/plot x^2 - 5 5</code> — график функции\n"
    "• <code>/system x+y=5; x-y=1</code> — система уравнений\n"
    "• <code>/base 255 16</code> — перевод в 16-ричную\n"
    "• <code>/trainer</code> — тренажёр\n"
    "• <code>/score</code> — мой счёт\n"
    "• <code>/stop</code> — выйти из тренажёра\n\n"
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
        return await message.answer("📝 <code>/calc 2+2*2</code>", parse_mode="HTML")
    try:
        result = safe_eval(args[1])
        if isinstance(result, float) and result.is_integer():
            result = int(result)
        await message.answer(f"🧮 <code>{args[1]}</code> = <b>{result}</b>", parse_mode="HTML")
    except Exception as e:
        await message.answer(f"❌ Ошибка: <code>{e}</code>", parse_mode="HTML")


# ─── /prime ───
@dp.message(Command("prime"))
async def cmd_prime(message: Message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        return await message.answer("📝 <code>/prime 17</code>", parse_mode="HTML")
    try:
        n = int(args[1])
    except ValueError:
        return await message.answer("❌ Нужно целое число.")

    if n < 2:
        return await message.answer(f"❌ {n} — не простое.")
    is_prime = all(n % i != 0 for i in range(2, int(n ** 0.5) + 1))
    if is_prime:
        await message.answer(f"✅ <b>{n}</b> — простое!", parse_mode="HTML")
    else:
        divs = [i for i in range(2, n) if n % i == 0][:5]
        await message.answer(
            f"❌ <b>{n}</b> — составное.\nДелители: {', '.join(map(str, divs))}…",
            parse_mode="HTML",
        )


# ─── /fact ───
@dp.message(Command("fact"))
async def cmd_fact(message: Message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        return await message.answer("📝 <code>/fact 5</code>", parse_mode="HTML")
    try:
        n = int(args[1])
        if n < 0 or n > 1000:
            return await message.answer("❌ Число от 0 до 1000.")
        r = math.factorial(n)
        if n <= 20:
            await message.answer(f"❗ <b>{n}!</b> = <code>{r}</code>", parse_mode="HTML")
        else:
            await message.answer(f"❗ <b>{n}!</b> ≈ <code>{r:.3e}</code>", parse_mode="HTML")
    except ValueError:
        await message.answer("❌ Нужно целое.")


# ─── /fib ───
@dp.message(Command("fib"))
async def cmd_fib(message: Message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        return await message.answer("📝 <code>/fib 10</code>", parse_mode="HTML")
    try:
        n = int(args[1])
        if n < 0 or n > 1000:
            return await message.answer("❌ N от 0 до 1000.")
        a, b = 0, 1
        for _ in range(n):
            a, b = b, a + b
        await message.answer(f"🌀 F({n}) = <b>{a}</b>", parse_mode="HTML")
    except ValueError:
        await message.answer("❌ Нужно целое.")


# ─── /gcd ───
@dp.message(Command("gcd"))
async def cmd_gcd(message: Message):
    args = message.text.split()
    if len(args) < 3:
        return await message.answer("📝 <code>/gcd 12 18</code>", parse_mode="HTML")
    try:
        a, b = int(args[1]), int(args[2])
        g = math.gcd(a, b)
        l = abs(a * b) // g if g else 0
        await message.answer(
            f"🔗 НОД({a}, {b}) = <b>{g}</b>\n📏 НОК({a}, {b}) = <b>{l}</b>",
            parse_mode="HTML",
        )
    except ValueError:
        await message.answer("❌ Нужны 2 целых.")


# ─── /quad ───
@dp.message(Command("quad"))
async def cmd_quad(message: Message):
    args = message.text.split()
    if len(args) < 4:
        return await message.answer("📝 <code>/quad 1 -5 6</code>", parse_mode="HTML")
    try:
        a, b, c = float(args[1]), float(args[2]), float(args[3])
    except ValueError:
        return await message.answer("❌ Коэффициенты — числа.")

    if a == 0:
        return await message.answer("❌ a ≠ 0.")

    d = b * b - 4 * a * c
    text = f"📐 <b>{a}x² + {b}x + {c} = 0</b>\n\nD = <b>{d}</b>\n\n"
    if d > 0:
        x1 = (-b + math.sqrt(d)) / (2 * a)
        x2 = (-b - math.sqrt(d)) / (2 * a)
        text += f"✅ x₁ = <b>{x1:.4g}</b>\nx₂ = <b>{x2:.4g}</b>"
    elif d == 0:
        text += f"✅ x = <b>{-b / (2 * a):.4g}</b>"
    else:
        text += "❌ Корней нет (D < 0)"
    await message.answer(text, parse_mode="HTML")


# ─── /pow ───
@dp.message(Command("pow"))
async def cmd_pow(message: Message):
    args = message.text.split()
    if len(args) < 3:
        return await message.answer("📝 <code>/pow 2 10</code>", parse_mode="HTML")
    try:
        base, exp = float(args[1]), float(args[2])
        r = base ** exp
        if r.is_integer():
            r = int(r)
        await message.answer(f"⚡ <b>{base}^{exp}</b> = <code>{r}</code>", parse_mode="HTML")
    except Exception:
        await message.answer("❌ Нужны 2 числа.")


# ─── /sqrt ───
@dp.message(Command("sqrt"))
async def cmd_sqrt(message: Message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        return await message.answer("📝 <code>/sqrt 144</code>", parse_mode="HTML")
    try:
        n = float(args[1])
        if n < 0:
            return await message.answer("❌ Отрицательное.")
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
        return await message.answer("📝 <code>/rand 1 100</code>", parse_mode="HTML")
    try:
        a, b = int(args[1]), int(args[2])
        if a > b:
            a, b = b, a
        r = random.randint(a, b)
        await message.answer(f"🎲 Случайное от {a} до {b}: <b>{r}</b>", parse_mode="HTML")
    except ValueError:
        await message.answer("❌ Нужны 2 целых.")


# ─── /plot ───
@dp.message(Command("plot"))
async def cmd_plot(message: Message):
    """
    /plot x^2 -5 5
    /plot sin(x) -3.14 3.14
    """
    args = message.text.split(maxsplit=3)
    if len(args) < 4:
        return await message.answer(
            "📝 <code>/plot выражение xmin xmax</code>\n"
            "Пример: <code>/plot x^2 -5 5</code>\n"
            "Пример: <code>/plot sin(x) -6.28 6.28</code>",
            parse_mode="HTML",
        )
    expr_str = args[1].replace("^", "**")
    try:
        xmin = float(args[2])
        xmax = float(args[3])
    except ValueError:
        return await message.answer("❌ Границы — числа.")

    if xmin >= xmax:
        return await message.answer("❌ xmin < xmax.")

    # Считаем в отдельном потоке, чтобы не блокировать loop
    def render():
        x = np.linspace(xmin, xmax, 1000)
        ns = {"x": x, "np": np, "sin": np.sin, "cos": np.cos,
              "tan": np.tan, "log": np.log, "sqrt": np.sqrt,
              "pi": np.pi, "e": np.e, "abs": np.abs}
        try:
            y = eval(expr_str, {"__builtins__": {}}, ns)
        except Exception as e:
            raise ValueError(f"Не удалось вычислить: {e}")

        fig, ax = plt.subplots(figsize=(7, 4.5), dpi=120)
        ax.plot(x, y, color="#1f77b4", linewidth=2)
        ax.axhline(0, color="black", linewidth=0.5)
        ax.axvline(0, color="black", linewidth=0.5)
        ax.grid(True, alpha=0.3)
        ax.set_title(f"y = {expr_str}")
        ax.set_xlabel("x")
        ax.set_ylabel("y")
        buf = io.BytesIO()
        fig.tight_layout()
        fig.savefig(buf, format="png")
        plt.close(fig)
        buf.seek(0)
        return buf.read()

    try:
        png = await asyncio.to_thread(render)
        photo = BufferedInputFile(png, filename="plot.png")
        await message.answer_photo(photo, caption=f"📊 <code>y = {expr_str}</code>",
                                   parse_mode="HTML")
    except Exception as e:
        await message.answer(f"❌ Ошибка: <code>{e}</code>", parse_mode="HTML")


# ─── /system ───
@dp.message(Command("system"))
async def cmd_system(message: Message):
    """
    /system x+y=5; x-y=1
    Уравнения через ; (точку с запятой)
    """
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        return await message.answer(
            "📝 <code>/system x+y=5; x-y=1</code>\n"
            "Разделяй уравнения через <b>;</b>",
            parse_mode="HTML",
        )
    raw = args[1]
    parts = [p.strip() for p in raw.split(";") if p.strip()]
    if len(parts) < 2:
        return await message.answer("❌ Нужно минимум 2 уравнения через ;")

    try:
        # Собираем символы из строк
        eqs = []
        symbols = set()
        for p in parts:
            if "=" not in p:
                return await message.answer(f"❌ Нет '=' в: <code>{p}</code>", parse_mode="HTML")
            left, right = p.split("=", 1)
            # Заменяем ^ на **
            left = left.replace("^", "**")
            right = right.replace("^", "**")
            # Собираем имена переменных
            for token in sp.tokenizer.tokenize(left + "+" + right):
                s = str(token)
                if s.isidentifier() and s not in {"sin", "cos", "tan", "log", "sqrt", "exp"}:
                    symbols.add(s)
            eqs.append(sp.Eq(sp.sympify(left), sp.sympify(right)))

        syms = sorted(symbols, key=str)
        sym_objs = sp.symbols(" ".join(syms))
        if not isinstance(sym_objs, tuple):
            sym_objs = (sym_objs,)

        solution = sp.solve(eqs, sym_objs, dict=True)

        if not solution:
            return await message.answer("❌ Решений нет.")
        if isinstance(solution, list):
            lines = []
            for sol in solution:
                lines.append(", ".join(f"{k} = {v}" for k, v in sol.items()))
            text = "📏 <b>Решение системы:</b>\n\n" + "\n".join(lines)
        else:
            text = f"📏 <b>Решение:</b>\n{solution}"
        await message.answer(text, parse_mode="HTML")
    except Exception as e:
        await message.answer(f"❌ Ошибка: <code>{e}</code>", parse_mode="HTML")


# ─── /base ───
@dp.message(Command("base"))
async def cmd_base(message: Message):
    """
    /base 255 16   → перевести 255 в 16-ричную
    /base ff 10    → из 16-ричной в 10-чную
    Основание от 2 до 36.
    """
    args = message.text.split()
    if len(args) < 3:
        return await message.answer(
            "📝 <code>/base число основание</code>\n"
            "Пример: <code>/base 255 16</code> → FF\n"
            "Пример: <code>/base ff 10</code> → 255\n"
            "Основание от 2 до 36.",
            parse_mode="HTML",
        )
    num_str = args[1].lower()
    try:
        target_base = int(args[2])
    except ValueError:
        return await message.answer("❌ Основание — число от 2 до 36.")
    if not (2 <= target_base <= 36):
        return await message.answer("❌ Основание от 2 до 36.")

    # Пробуем распарсить число. Сначала как десятичное,
    # если не выходит — пробуем по префиксам/буквам.
    value = None
    try:
        value = int(num_str, 10)
    except ValueError:
        for base_try in (16, 8, 2):
            try:
                value = int(num_str, base_try)
                break
            except ValueError:
                continue

    if value is None:
        return await message.answer("❌ Не могу распарсить число.")

    # Перевод
    digits = "0123456789abcdefghijklmnopqrstuvwxyz"
    if value == 0:
        result = "0"
    else:
        negative = value < 0
        v = abs(value)
        out = []
        while v > 0:
            out.append(digits[v % target_base])
            v //= target_base
        result = "".join(reversed(out))
        if negative:
            result = "-" + result

    await message.answer(
        f"🌍 <b>{num_str}</b> (10) → <b>{result.upper()}</b> (основание {target_base})",
        parse_mode="HTML",
    )


# ─── /trainer ───
@dp.message(Command("trainer"), F.chat.type == ChatType.PRIVATE)
async def cmd_trainer(message: Message, state: FSMContext):
    await state.clear()
    a = random.randint(1, 20)
    b = random.randint(1, 20)
    op = random.choice(["+", "-", "*"])
    if op == "+":
        answer = a + b
    elif op == "-":
        if a < b:
            a, b = b, a
        answer = a - b
    else:
        answer = a * b

    await state.update_data(answer=answer)
    await state.set_state(TrainerState.waiting_answer)
    await message.answer(
        f"🧠 <b>Тренажёр</b>\n\nСколько будет <b>{a} {op} {b}</b>?\n\n"
        f"Напиши ответ числом или /stop для выхода.",
        parse_mode="HTML",
    )


@dp.message(Command("stop"))
async def cmd_stop(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("🚪 Вышел из тренажёра.")


@dp.message(TrainerState.waiting_answer, F.chat.type == ChatType.PRIVATE)
async def trainer_answer(message: Message, state: FSMContext):
    data = await state.get_data()
    correct = data.get("answer")
    try:
        user_answer = int(message.text.strip())
    except (ValueError, AttributeError):
        return await message.answer("❌ Нужно число. Или /stop.")

    if user_answer == correct:
        db_update_score(message.from_user.id, message.from_user.username or "", correct_inc=1)
        await message.answer("✅ Верно!")
    else:
        db_update_score(message.from_user.id, message.from_user.username or "", wrong_inc=1)
        await message.answer(f"❌ Неверно. Правильный ответ: <b>{correct}</b>", parse_mode="HTML")

    # Следующий вопрос
    a = random.randint(1, 20)
    b = random.randint(1, 20)
    op = random.choice(["+", "-", "*"])
    if op == "+":
        answer = a + b
    elif op == "-":
        if a < b:
            a, b = b, a
        answer = a - b
    else:
        answer = a * b

    await state.update_data(answer=answer)
    await message.answer(
        f"➡️ Следующий: <b>{a} {op} {b}</b>?",
        parse_mode="HTML",
    )


@dp.message(Command("score"))
async def cmd_score(message: Message):
    correct, wrong = db_get_score(message.from_user.id)
    total = correct + wrong
    percent = (correct / total * 100) if total else 0
    await message.answer(
        f"🏆 <b>Твой счёт</b>\n\n"
        f"✅ Правильно: <b>{correct}</b>\n"
        f"❌ Ошибок: <b>{wrong}</b>\n"
        f"📊 Точность: <b>{percent:.1f}%</b>",
        parse_mode="HTML",
    )


# ─────────────────────── CALLBACK-КНОПКИ ───────────────────────
@dp.callback_query(F.data.startswith("help_"))
async def cb_help(callback: CallbackQuery):
    mapping = {
        "help_calc":   "🧮 <b>Калькулятор</b>\n\n<code>/calc 2+2*2</code>\n<code>/calc sqrt(16) + sin(0)</code>\n<code>/calc 2**10</code>",
        "help_prime":  "🔢 <b>Простое число</b>\n\n<code>/prime 17</code>",
        "help_fact":   "❗ <b>Факториал</b>\n\n<code>/fact 5</code> → 120",
        "help_fib":    "🌀 <b>Фибоначчи</b>\n\n<code>/fib 10</code> → 55",
        "help_gcd":    "🔗 <b>НОД / НОК</b>\n\n<code>/gcd 12 18</code>",
        "help_quad":   "📐 <b>Квадратное</b>\n\n<code>/quad 1 -5 6</code>",
        "help_pow":    "⚡ <b>Степень</b>\n\n<code>/pow 2 10</code> → 1024",
        "help_sqrt":   "√ <b>Корень</b>\n\n<code>/sqrt 144</code> → 12",
        "help_rand":   "🎲 <b>Случайное</b>\n\n<code>/rand 1 100</code>",
        "help_plot":   "📊 <b>График</b>\n\n<code>/plot x^2 -5 5</code>\n<code>/plot sin(x) -6.28 6.28</code>",
        "help_system": "📏 <b>Система ур.</b>\n\n<code>/system x+y=5; x-y=1</code>\nРазделяй через <b>;</b>",
        "help_base":   "🌍 <b>Системы счисления</b>\n\n<code>/base 255 16</code> → FF\n<code>/base ff 10</code> → 255",
        "help_trainer":"🧠 <b>Тренажёр</b>\n\n<code>/trainer</code> — начать\nОтвечай числом. <code>/stop</code> — выход",
        "help_score":  "🏆 <b>Мой счёт</b>\n\n<code>/score</code>",
    }
    await callback.message.answer(mapping.get(callback.data, "❓"), parse_mode="HTML")
    await callback.answer()


# ─────────────────────── ВЕБ-СЕРВЕР ───────────────────────
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
    db_init()
    await start_web()
    log.info("MathBot запущен.")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        log.info("MathBot остановлен.")
