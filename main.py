import asyncio
import io
import logging
import math
import os
import random
import sqlite3
from datetime import datetime, timezone, timedelta

import matplotlib
matplotlib.use("Agg")
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


# ─────────────────────── БАЗА ДАННЫХ ───────────────────────
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


# ─────────────────────── КАЛЬКУЛЯТОР ───────────────────────
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


# ─────────────────────── КЛАВИАТУРЫ ───────────────────────
def main_menu_kb() -> InlineKeyboardMarkup:
    """Главное меню — разделы."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🧮 Калькулятор и числа", callback_data="cat_numbers"),
        ],
        [
            InlineKeyboardButton(text="📐 Уравнения и системы", callback_data="cat_equations"),
        ],
        [
            InlineKeyboardButton(text="📊 Графики и функции", callback_data="cat_plots"),
        ],
        [
            InlineKeyboardButton(text="🌍 Перевод систем счисления", callback_data="cat_bases"),
        ],
        [
            InlineKeyboardButton(text="🧠 Тренажёр и счёт", callback_data="cat_trainer"),
        ],
        [
            InlineKeyboardButton(text="ℹ️ Помощь", callback_data="help_main"),
        ],
    ])


def numbers_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🧮 /calc", callback_data="help_calc"),
            InlineKeyboardButton(text="🔢 /prime", callback_data="help_prime"),
        ],
        [
            InlineKeyboardButton(text="❗ /fact", callback_data="help_fact"),
            InlineKeyboardButton(text="🌀 /fib", callback_data="help_fib"),
        ],
        [
            InlineKeyboardButton(text="🔗 /gcd", callback_data="help_gcd"),
            InlineKeyboardButton(text="⚡ /pow", callback_data="help_pow"),
        ],
        [
            InlineKeyboardButton(text="√ /sqrt", callback_data="help_sqrt"),
            InlineKeyboardButton(text="🎲 /rand", callback_data="help_rand"),
        ],
        [
            InlineKeyboardButton(text="⬅️ Назад", callback_data="back_main"),
        ],
    ])


def equations_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📐 /quad", callback_data="help_quad"),
            InlineKeyboardButton(text="📏 /system", callback_data="help_system"),
        ],
        [
            InlineKeyboardButton(text="⬅️ Назад", callback_data="back_main"),
        ],
    ])


def plots_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📊 /plot", callback_data="help_plot"),
        ],
        [
            InlineKeyboardButton(text="⬅️ Назад", callback_data="back_main"),
        ],
    ])


def bases_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🌍 /base", callback_data="help_base"),
        ],
        [
            InlineKeyboardButton(text="⬅️ Назад", callback_data="back_main"),
        ],
    ])


def trainer_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🧠 /trainer", callback_data="help_trainer"),
            InlineKeyboardButton(text="🏆 /score", callback_data="help_score"),
        ],
        [
            InlineKeyboardButton(text="⬅️ Назад", callback_data="back_main"),
        ],
    ])


def back_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_main")],
    ])


# ─────────────────────── ТЕКСТЫ ───────────────────────
def greeting(name: str) -> str:
    return (
        f"👋 <b>Приветствую, {name}!</b>\n\n"
        f"🧮 Я — <b>MathBot</b>, твой личный помощник в математике.\n\n"
        f"Выбери раздел ниже 👇"
    )


MENU_TEXT = (
    "📚 <b>Главное меню MathBot</b>\n\n"
    "Выбери раздел:"
)

NUMBERS_TEXT = (
    "🧮 <b>Калькулятор и числа</b>\n\n"
    "• <code>/calc 2+2*2</code> — вычислить выражение\n"
    "• <code>/prime 17</code> — простое ли число\n"
    "• <code>/fact 5</code> — факториал\n"
    "• <code>/fib 10</code> — число Фибоначчи\n"
    "• <code>/gcd 12 18</code> — НОД и НОК\n"
    "• <code>/pow 2 10</code> — степень\n"
    "• <code>/sqrt 144</code> — корень\n"
    "• <code>/rand 1 100</code> — случайное число"
)

EQUATIONS_TEXT = (
    "📐 <b>Уравнения и системы</b>\n\n"
    "• <code>/quad 1 -5 6</code> — корни ax²+bx+c=0\n"
    "• <code>/system x+y=5; x-y=1</code> — система уравнений"
)

PLOTS_TEXT = (
    "📊 <b>Графики и функции</b>\n\n"
    "• <code>/plot x^2 -5 5</code> — график y = x²\n"
    "• <code>/plot sin(x) -6.28 6.28</code> — синусоида\n\n"
    "Первый аргумент — выражение, потом xmin и xmax."
)

BASES_TEXT = (
    "🌍 <b>Системы счисления</b>\n\n"
    "• <code>/base 255 16</code> → FF\n"
    "• <code>/base ff 10</code> → 255\n\n"
    "Основание от 2 до 36."
)

TRAINER_TEXT = (
    "🧠 <b>Тренажёр и счёт</b>\n\n"
    "• <code>/trainer</code> — начать тренировку\n"
    "• <code>/score</code> — посмотреть свой счёт\n"
    "• <code>/stop</code> — выйти из тренажёра"
)

HELP_TEXT = (
    "ℹ️ <b>Справка по MathBot</b>\n\n"
    "<b>Команды:</b>\n"
    "/calc /prime /fact /fib /gcd /pow /sqrt /rand\n"
    "/quad /system /plot /base\n"
    "/trainer /score /stop\n\n"
    "💡 <i>Поддерживаются:</i> + − * / ** sqrt sin cos log pi e"
)


# ─────────────────────── КОМАНДЫ ───────────────────────
@dp.message(CommandStart())
async def cmd_start(message: Message):
    name = message.from_user.first_name or "друг"
    await message.answer(
        greeting(name),
        parse_mode="HTML",
        reply_markup=main_menu_kb(),
    )


@dp.message(Command("menu"))
async def cmd_menu(message: Message):
    name = message.from_user.first_name or "друг"
    await message.answer(
        f"👋 <b>{name}</b>, вот меню:\n\n{MENU_TEXT}",
        parse_mode="HTML",
        reply_markup=main_menu_kb(),
    )


@dp.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(HELP_TEXT, parse_mode="HTML", reply_markup=back_kb())


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
        ax.set_xlabel("x"); ax.set_ylabel("y")
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
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        return await message.answer(
            "📝 <code>/system x+y=5; x-y=1</code>\nРазделяй через <b>;</b>",
            parse_mode="HTML",
        )
    parts = [p.strip() for p in args[1].split(";") if p.strip()]
    if len(parts) < 2:
        return await message.answer("❌ Минимум 2 уравнения через ;")
    try:
        eqs = []
        symbols = set()
        for p in parts:
            if "=" not in p:
                return await message.answer(f"❌ Нет '=' в: <code>{p}</code>", parse_mode="HTML")
            left, right = p.split("=", 1)
            left = left.replace("^", "**"); right = right.replace("^", "**")
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
        lines = []
        for sol in solution:
            lines.append(", ".join(f"{k} = {v}" for k, v in sol.items()))
        text = "📏 <b>Решение системы:</b>\n\n" + "\n".join(lines)
        await message.answer(text, parse_mode="HTML")
    except Exception as e:
        await message.answer(f"❌ Ошибка: <code>{e}</code>", parse_mode="HTML")


# ─── /base ───
@dp.message(Command("base"))
async def cmd_base(message: Message):
    args = message.text.split()
    if len(args) < 3:
        return await message.answer(
            "📝 <code>/base число основание</code>\n"
            "Пример: <code>/base 255 16</code> → FF\n"
            "Пример: <code>/base ff 10</code> → 255",
            parse_mode="HTML",
        )
    num_str = args[1].lower()
    try:
        target_base = int(args[2])
    except ValueError:
        return await message.answer("❌ Основание — число от 2 до 36.")
    if not (2 <= target_base <= 36):
        return await message.answer("❌ Основание от 2 до 36.")
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
        if a < b: a, b = b, a
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
    await message.answer("🚪 Вышел из тренажёра.", reply_markup=back_kb())


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
    a = random.randint(1, 20); b = random.randint(1, 20)
    op = random.choice(["+", "-", "*"])
    if op == "+":
        answer = a + b
    elif op == "-":
        if a < b: a, b = b, a
        answer = a - b
    else:
        answer = a * b
    await state.update_data(answer=answer)
    await message.answer(f"➡️ Следующий: <b>{a} {op} {b}</b>?", parse_mode="HTML")


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


# ─────────────────────── CALLBACK: КНОПКИ МЕНЮ ───────────────────────
HELP_MESSAGES = {
    "help_calc":   "🧮 <b>Калькулятор</b>\n\n<code>/calc 2+2*2</code>\n<code>/calc sqrt(16) + sin(0)</code>\n<code>/calc 2**10</code>",
    "help_prime":  "🔢 <b>Простое число</b>\n\n<code>/prime 17</code>",
    "help_fact":   "❗ <b>Факториал</b>\n\n<code>/fact 5</code> → 120",
    "help_fib":    "🌀 <b>Фибоначчи</b>\n\n<code>/fib 10</code> → 55",
    "help_gcd":    "🔗 <b>НОД / НОК</b>\n\n<code>/gcd 12 18</code>",
    "help_pow":    "⚡ <b>Степень</b>\n\n<code>/pow 2 10</code> → 1024",
    "help_sqrt":   "√ <b>Корень</b>\n\n<code>/sqrt 144</code> → 12",
    "help_rand":   "🎲 <b>Случайное</b>\n\n<code>/rand 1 100</code>",
    "help_quad":   "📐 <b>Квадратное</b>\n\n<code>/quad 1 -5 6</code>",
    "help_system": "📏 <b>Система ур.</b>\n\n<code>/system x+y=5; x-y=1</code>\nРазделяй через <b>;</b>",
    "help_plot":   "📊 <b>График</b>\n\n<code>/plot x^2 -5 5</code>\n<code>/plot sin(x) -6.28 6.28</code>",
    "help_base":   "🌍 <b>Системы счисления</b>\n\n<code>/base 255 16</code> → FF\n<code>/base ff 10</code> → 255",
    "help_trainer":"🧠 <b>Тренажёр</b>\n\n<code>/trainer</code> — начать\n<code>/stop</code> — выход",
    "help_score":  "🏆 <b>Мой счёт</b>\n\n<code>/score</code>",
    "help_main":   HELP_TEXT,
}


def section_kb_for(data: str) -> InlineKeyboardMarkup:
    """Возвращает нужную клавиатуру для раздела."""
    if data == "cat_numbers":   return numbers_kb()
    if data == "cat_equations": return equations_kb()
    if data == "cat_plots":     return plots_kb()
    if data == "cat_bases":     return bases_kb()
    if data == "cat_trainer":   return trainer_kb()
    return back_kb()


def section_text_for(data: str) -> str:
    if data == "cat_numbers":   return NUMBERS_TEXT
    if data == "cat_equations": return EQUATIONS_TEXT
    if data == "cat_plots":     return PLOTS_TEXT
    if data == "cat_bases":     return BASES_TEXT
    if data == "cat_trainer":   return TRAINER_TEXT
    return MENU_TEXT


@dp.callback_query(F.data.startswith("cat_"))
async def cb_section(callback: CallbackQuery):
    """Открывает раздел — редактирует сообщение на месте."""
    data = callback.data
    text = section_text_for(data)
    kb = section_kb_for(data)
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    except Exception:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=kb)
    await callback.answer()


@dp.callback_query(F.data == "back_main")
async def cb_back(callback: CallbackQuery):
    """Возврат в главное меню."""
    name = callback.from_user.first_name or "друг"
    try:
        await callback.message.edit_text(
            greeting(name),
            parse_mode="HTML",
            reply_markup=main_menu_kb(),
        )
    except Exception:
        await callback.message.answer(
            greeting(name),
            parse_mode="HTML",
            reply_markup=main_menu_kb(),
        )
    await callback.answer()


@dp.callback_query(F.data.startswith("help_"))
async def cb_help(callback: CallbackQuery):
    """Показывает подсказку по команде."""
    text = HELP_MESSAGES.get(callback.data, "❓")
    await callback.message.answer(text, parse_mode="HTML")
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