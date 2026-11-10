import asyncio
import logging
import os
from datetime import datetime, timezone, timedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.enums import ChatType
from aiohttp import web

# ⛔️ ВЫКЛЮЧАТЕЛЬ БОТА
BOT_ENABLED = True 

# ⚠️ ВСТАВЬ СЮДА СВОЙ ТОКЕН ИЛИ ЗАДАЙ В ПЕРЕМЕННЫХ ОКРУЖЕНИЯ
TOKEN =8791845044:AAFBz2VWG4BYf2gVKUsxITd23k1j4mGxYVk os.getenv("TELEGRAM_BOT_TOKEN", "ТВОЙ_ТОКЕН_ЗДЕСЬ")
PORT = int(os.getenv("PORT", 8080))

GROUP_ID = -5437265461
CHANNEL_ID = "@transfermarket" # Изменил на ваш канал
MODERATORS = "@Zyro0o0" # Убрал мелвикса

WORK_START = 7
WORK_END = 23
MSK = timezone(timedelta(hours=3))

logging.basicConfig(level=logging.INFO)
bot = Bot(token=TOKEN)
dp = Dispatcher()

def is_working_hours() -> bool:
    now = datetime.now(MSK)
    return WORK_START <= now.hour < WORK_END

def work_hours_text() -> str:
    return f"📅 Расписание работы: <b>{WORK_START}:00–{WORK_END}:00 (МСК)</b>"

class FreeAgentState(StatesGroup):
    requirements = State()
    destination = State()

class TransferState(StatesGroup):
    from_where = State()
    to_where = State()
    position = State()

class ChangeNickState(StatesGroup):
    old_nick = State()
    new_nick = State()

class ChangePosState(StatesGroup):
    old_pos = State()
    new_pos = State()

class EndCareerState(StatesGroup):
    nick = State()
    ps = State()

class ReturnCareerState(StatesGroup):
    nick = State()
    ps = State()

class PauseCareerState(StatesGroup):
    reason = State()

class FindTourState(StatesGroup):
    club = State()
    time = State()
    stadium = State()
    vip = State()

class FindPlayersState(StatesGroup):
    requirement = State()

class ContractState(StatesGroup):
    club = State()
    player_nick = State()
    sign_date = State()

class RentPlayerState(StatesGroup):
    club = State()
    player_nick = State()
    matches = State()
    rent_date = State()

class ModerationState(StatesGroup):
    waiting_decline_reason = State()

# --- МЕНЮ (КАК НА СКРИНШОТЕ) ---
def get_main_menu():
    buttons = [
        [InlineKeyboardButton(text="✅ Купить рекламу", callback_data="buy_ad"),
         InlineKeyboardButton(text="🪞 Зеркало", callback_data="mirror")],
        [InlineKeyboardButton(text="👤 Свободный агент", callback_data="free_agent"),
         InlineKeyboardButton(text="⚽ Переход в клуб", callback_data="transfer_club")],
        [InlineKeyboardButton(text="🔄 Смена никнейма", callback_data="change_nick"),
         InlineKeyboardButton(text="🔄 Смена позиции", callback_data="change_pos")],
        [InlineKeyboardButton(text="🥀 Завершение карьеры", callback_data="end_career"),
         InlineKeyboardButton(text="❤️ Возвращение карьеры", callback_data="return_career")],
        [InlineKeyboardButton(text="🥀 Приост. карьеры", callback_data="pause_career"),
         InlineKeyboardButton(text="🏆 Поиск товы", callback_data="find_tour")],
        [InlineKeyboardButton(text="🔎 Поиск игроков", callback_data="find_players"),
         InlineKeyboardButton(text="🛠️ Техподдержка", callback_data="support")],
        [InlineKeyboardButton(text="📢 Жалобы", callback_data="complaints")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_final_menu(action_type):
    buttons = [
        [InlineKeyboardButton(text="✅ Согласны", callback_data=f"accept_{action_type}"),
         InlineKeyboardButton(text="🔄 Начать заново", callback_data=f"restart_{action_type}")],
        [InlineKeyboardButton(text="🔙 Отмена", callback_data="cancel_to_main")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_positions_menu(exclude=None):
    positions = [
        ("Форвард", "pos_fwd"),
        ("Полузащитник", "pos_mid"),
        ("Защитник", "pos_def"),
        ("Голкипер", "pos_gk")
    ]
    buttons = []
    for name, callback in positions:
        if name != exclude:
            buttons.append([InlineKeyboardButton(text=name, callback_data=callback)])
    buttons.append([InlineKeyboardButton(text="🔙 Отмена", callback_data="cancel_to_main")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# --- КОМАНДЫ ---
@dp.message(CommandStart(), F.chat.type == ChatType.PRIVATE)
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    status = "" if is_working_hours() else f"\n\n❗ <b>Бот закончил работу на сегодня.</b>\n{work_hours_text()}"
    await message.answer(f"<b>Выбери категорию:</b>{status}", parse_mode="HTML", reply_markup=get_main_menu())

@dp.message(Command("id"))
async def cmd_id(message: types.Message):
    await message.answer(f"Chat ID: <code>{message.chat.id}</code>", parse_mode="HTML")

@dp.message(Command("cancel"))
async def cmd_cancel(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("<b>Действие отменено. Вы вернулись в главное меню.</b>", parse_mode="HTML", reply_markup=get_main_menu())

# --- ОБРАБОТКА КНОПОК ---
@dp.callback_query(F.data == "buy_ad")
async def cb_buy_ad(call: types.CallbackQuery):
    await call.message.edit_text("<b>Купить рекламу можно у @Zyro0o0</b>", parse_mode="HTML", reply_markup=get_main_menu())

@dp.callback_query(F.data == "mirror")
async def cb_mirror(call: types.CallbackQuery):
    await call.message.edit_text("<b>Зеркало — 50 звёзд. По вопросам писать: @Zyro0o0</b>", parse_mode="HTML", reply_markup=get_main_menu())

@dp.callback_query(F.data == "cancel_to_main")
async def cb_cancel_to_main(call: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text("<b>Выбери категорию:</b>", parse_mode="HTML", reply_markup=get_main_menu())

@dp.callback_query(F.data == "change_pos")
async def cb_change_pos(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(ChangePosState.old_pos)
    await call.message.edit_text(
        "<b>Выберите старую позицию, затем новую:</b>\n\n<b>Ваш текущий ник:</b> " + call.from_user.full_name,
        parse_mode="HTML",
        reply_markup=get_positions_menu()
    )

@dp.callback_query(ChangePosState.old_pos, F.data.startswith("pos_"))
async def process_old_pos(call: types.CallbackQuery, state: FSMContext):
    pos_map = {"pos_fwd": "Форвард", "pos_mid": "Полузащитник", "pos_def": "Защитник", "pos_gk": "Голкипер"}
    old_pos = pos_map[call.data]
    await state.update_data(old_pos=old_pos)
    await state.set_state(ChangePosState.new_pos)
    await call.message.edit_text(
        f"<b>Выбрана старая позиция:</b> {old_pos}\n<b>Теперь выберите новую позицию:</b>",
        parse_mode="HTML",
        reply_markup=get_positions_menu(exclude=old_pos)
    )

@dp.callback_query(ChangePosState.new_pos, F.data.startswith("pos_"))
async def process_new_pos(call: types.CallbackQuery, state: FSMContext):
    pos_map = {"pos_fwd": "Форвард", "pos_mid": "Полузащитник", "pos_def": "Защитник", "pos_gk": "Голкипер"}
    new_pos = pos_map[call.data]
    data = await state.get_data()
    old_pos = data.get("old_pos")
    
    await state.clear()
    
    text = (
        f"❗️📢 <b>@Zyro0o0</b> | <b>Пл - ОФИЦИАЛЬНО СМЕНИЛ ПОЗИЦИЮ)</b>\n\n"
        f"🔹 - <b>{old_pos} -> {new_pos}</b>\n"
        f"💠 <b>Перемурчено</b>"
    )
    
    await state.update_data(final_text=text)
    await call.message.edit_text(text, parse_mode="HTML", reply_markup=get_final_menu("change_pos"))

@dp.callback_query(F.data == "find_tour")
async def cb_find_tour(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(FindTourState.club)
    await call.message.edit_text("<b>Введите название вашего клуба:</b>", parse_mode="HTML")

@dp.message(FindTourState.club)
async def process_tour_club(message: types.Message, state: FSMContext):
    await state.update_data(club=message.text)
    await state.set_state(FindTourState.time)
    await message.answer("<b>Введите время (например, 18:00 или D):</b>", parse_mode="HTML")
