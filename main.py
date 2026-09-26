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

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
PORT = int(os.getenv("PORT", 8080))
GROUP_ID = -1004371804499
CHANNEL_ID = "@RssTransfeer"
MODERATORS = "@Tot_samiy_onet, @meelviks"

# --- РАБОЧИЕ ЧАСЫ ---
WORK_START = 7    # 7:00
WORK_END = 23     # 23:00
MSK = timezone(timedelta(hours=3))  # Москва (UTC+3)

logging.basicConfig(level=logging.INFO)
bot = Bot(token=TOKEN)
dp = Dispatcher()

def is_working_hours() -> bool:
    now = datetime.now(MSK)
    return WORK_START <= now.hour < WORK_END

def work_hours_text() -> str:
    return f"📅 Расписание работы: <b>{WORK_START}:00–{WORK_END}:00 (МСК)</b>"

# --- СОСТОЯНИЯ (FSM) ---
class FreeAgentState(StatesGroup):
    requirements = State()
    destination = State()

class TransferState(StatesGroup):
    from_where = State()
    to_where = State()
    position = State()

class ChangeNickState(StatesGroup):
    new_nick = State()

class ChangePosState(StatesGroup):
    old_pos = State()
    new_pos = State()

class EndCareerState(StatesGroup):
    ps = State()

class ReturnCareerState(StatesGroup):
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

class ModerationState(StatesGroup):
    waiting_decline_reason = State()

# --- МЕНЮ ---
def get_main_menu():
    buttons = [
        [InlineKeyboardButton(text="✅ Купить рекламу", callback_data="buy_ad"),
         InlineKeyboardButton(text="👤 Свободный агент", callback_data="free_agent")],
        [InlineKeyboardButton(text="⚽ Переход в клуб", callback_data="transfer_club"),
         InlineKeyboardButton(text="🔄 Смена никнейма", callback_data="change_nick")],
        [InlineKeyboardButton(text="🔄 Смена позиции", callback_data="change_pos"),
         InlineKeyboardButton(text="🏁 Завершение карьеры", callback_data="end_career")],
        [InlineKeyboardButton(text="❤️ Возвращение карьеры", callback_data="return_career"),
         InlineKeyboardButton(text="⏸️ Приост. карьеры", callback_data="pause_career")],
        [InlineKeyboardButton(text="🏆 Поиск товы", callback_data="find_tour"),
         InlineKeyboardButton(text="🔎 Поиск игроков", callback_data="find_players")],
        [InlineKeyboardButton(text="📝 Система контрактов", callback_data="contract_system")],
        [InlineKeyboardButton(text="🛠️ Техподдержка", callback_data="support"),
         InlineKeyboardButton(text="📢 Жалобы", callback_data="complaints")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# --- КОМАНДЫ ---
@dp.message(CommandStart(), F.chat.type == ChatType.PRIVATE)
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    status = "" if is_working_hours() else f"\n\n❗ <b>Бот закончил работу на сегодня.</b>\n{work_hours_text()}"
    await message.answer(f"Выбери категорию:{status}", parse_mode="HTML", reply_markup=get_main_menu())

@dp.message(Command("id"))
async def cmd_id(message: types.Message):
    await message.answer(f"Chat ID: <code>{message.chat.id}</code>", parse_mode="HTML")

@dp.message(Command("cancel"), F.chat.type == ChatType.PRIVATE)
async def cmd_cancel(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("Действие отменено. Выбери категорию:", reply_markup=get_main_menu())

# --- АВТОПОДСТАНОВКА ---
def get_auto_nick(user: types.User) -> str:
    if user.username:
        return f"@{user.username}"
    return user.full_name

def get_author_contact(user: types.User) -> str:
    if user.username:
        return f"@{user.username}"
    return f'<a href="tg://user?id={user.id}">{user.full_name}</a>'

def get_mod_display(user: types.User) -> str:
    if user.username:
        return f"@{user.username}"
    return user.full_name

# --- ОТПРАВКА ЗАЯВКИ ---
async def send_application(user: types.User, text: str, include_contact: bool = True):
    # Проверка рабочих часов
    if not is_working_hours():
        try:
            await bot.send_message(
                chat_id=user.id,
                text=(
                    f"❗ <b>Бот закончил работу на сегодня.</b>\n\n"
                    f"{work_hours_text()}\n\n"
                    f"Ваша заявка не была отправлена. Пожалуйста, попробуйте в рабочее время."
                ),
                parse_mode="HTML"
            )
        except Exception as e:
            logging.error(f"Не удалось уведомить пользователя {user.id}: {e}")
        return
    
    contact = get_author_contact(user)
    
    if include_contact:
        full_text = (
            f"{text}\n\n"
            f"📝 <b>Писать:</b> {contact}\n\n"
            f"📩 <b>Модераторы:</b> {MODERATORS}"
        )
    else:
        full_text = f"{text}\n\n📩 <b>Модераторы:</b> {MODERATORS}"
    
    mod_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Принять", callback_data=f"mod_accept_{user.id}"),
         InlineKeyboardButton(text="❌ Отказать", callback_data=f"mod_decline_{user.id}")]
    ])
    
    try:
        await bot.send_message(chat_id=GROUP_ID, text=full_text, parse_mode="HTML", reply_markup=mod_kb)
    except Exception as e:
        logging.error(f"Ошибка отправки в группу: {e}")
    
    back_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Вернуться в меню", callback_data="back_to_menu")]
    ])
    try:
        await bot.send_message(
            chat_id=user.id,
            text=f"✅ <b>Заявка отправлена модераторам:</b>\n{MODERATORS}\n\nОжидай ответа.",
            parse_mode="HTML",
            reply_markup=back_kb
        )
    except Exception as e:
        logging.error(f"Не удалось отправить подтверждение пользователю {user.id}: {e}")

# --- МОДЕРАЦИЯ: ПРИНЯТЬ ---
@dp.callback_query(F.data.startswith("mod_accept_"), F.message.chat.type.in_({ChatType.GROUP, ChatType.SUPERGROUP}))
async def mod_accept(callback: types.CallbackQuery):
    user_id = int(callback.data.replace("mod_accept_", ""))
    mod_display = get_mod_display(callback.from_user)
    
    try:
        user_info = await bot.get_chat(user_id)
        if user_info.username:
            contact = f"@{user_info.username}"
        else:
            contact = f'<a href="tg://user?id={user_id}">{user_info.full_name}</a>'
    except Exception as e:
        logging.error(f"Не удалось получить инфо о пользователе {user_id}: {e}")
        contact = f"ID: {user_id}"
    
    original_text = callback.message.text or ""
    has_contact = "📝 Писать:" in original_text
    
    if has_contact:
        clean_text = original_text.split("\n\n📝 Писать:")[0]
        channel_post = f"{clean_text}\n\n📝 <b>Писать:</b> {contact}"
    else:
        clean_text = original_text.split("\n\n📩 Модераторы:")[0]
        channel_post = clean_text
    
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.reply(f"✅ Принято модератором {mod_display}")
    
    try:
        await bot.send_message(chat_id=CHANNEL_ID, text=channel_post, parse_mode="HTML")
        logging.info(f"Заявка опубликована в канал {CHANNEL_ID}")
    except Exception as e:
        logging.error(f"Ошибка публикации в канал: {e}")
    
    try:
        await bot.send_message(
            chat_id=user_id,
            text=f"✅ <b>Ваша заявка принята и опубликована!</b>\n\n{clean_text}",
            parse_mode="HTML"
        )
    except Exception as e:
        logging.error(f"Не удалось уведомить пользователя {user_id}: {e}")
    
    await callback.answer("Заявка принята и опубликована!")

# --- МОДЕРАЦИЯ: ОТКАЗАТЬ ---
@dp.callback_query(F.data.startswith("mod_decline_"), F.message.chat.type.in_({ChatType.GROUP, ChatType.SUPERGROUP}))
async def mod_decline(callback: types.CallbackQuery, state: FSMContext):
    user_id = int(callback.data.replace("mod_decline_", ""))
    mod_display = get_mod_display(callback.from_user)
    
    original_text = callback.message.text or ""
    if "📝 Писать:" in original_text:
        clean_text = original_text.split("\n\n📝 Писать:")[0]
    else:
        clean_text = original_text.split("\n\n📩 Модераторы:")[0]
    
    await callback.message.edit_reply_markup(reply_markup=None)
    
    await state.update_data(
        author_id=user_id,
        clean_text=clean_text,
        mod_display=mod_display
    )
    await state.set_state(ModerationState.waiting_decline_reason)
    
    await callback.message.reply(
        f"❌ <b>Отклонено модератором {mod_display}.</b>\n\n"
        f"✍️ Напишите причину отказа <b>следующим сообщением</b> в чат.",
        parse_mode="HTML"
    )
    await callback.answer("Напишите причину следующим сообщением")

@dp.message(ModerationState.waiting_decline_reason, F.chat.type.in_({ChatType.GROUP, ChatType.SUPERGROUP}))
async def process_decline_reason(message: types.Message, state: FSMContext):
    data = await state.get_data()
    author_id = data.get("author_id")
    clean_text = data.get("clean_text", "Заявка")
    mod_display = data.get("mod_display", "модератор")
    
    reason = message.text or "Без указания причины"
    await state.clear()
    
    try:
        await bot.send_message(
            chat_id=author_id,
            text=f"❌ <b>Ваша заявка отклонена.</b>\n\n"
                 f"<b>Заявка:</b>\n{clean_text}\n\n"
                 f"<b>Причина отказа:</b> {reason}\n\n"
                 f"<b>Модератор:</b> {mod_display}\n\n"
                 f"Если вы не согласны — свяжитесь с модераторами: {MODERATORS}",
            parse_mode="HTML"
        )
        await message.reply("✅ Причина отказа отправлена автору заявки.")
    except Exception as e:
        logging.error(f"Не удалось уведомить пользователя {author_id}: {e}")
        await message.reply(f"⚠️ Не удалось отправить уведомление автору (ID: {author_id}).")

# --- КНОПКА "В МЕНЮ" ---
@dp.callback_query(F.data == "back_to_menu", F.message.chat.type == ChatType.PRIVATE)
async def back_to_menu_handler(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("Выбери категорию:", reply_markup=get_main_menu())
    await callback.answer()

# --- СВОБОДНЫЙ АГЕНТ ---
@dp.callback_query(F.data == "free_agent", F.message.chat.type == ChatType.PRIVATE)
async def start_free_agent(callback: types.CallbackQuery, state: FSMContext):
    nick = get_auto_nick(callback.from_user)
    await state.update_data(nickname=nick)
    await callback.message.answer(f"✅ Ваш ник: <b>{nick}</b>\n\nНапишите ваше требование:", parse_mode="HTML")
    await state.set_state(FreeAgentState.requirements)
    await callback.answer()

@dp.message(FreeAgentState.requirements, F.chat.type == ChatType.PRIVATE)
async def process_fa_req(message: types.Message, state: FSMContext):
    await state.update_data(requirements=message.text)
    buttons = [
        [InlineKeyboardButton(text="Клуб", callback_data="fa_dest_club")],
        [InlineKeyboardButton(text="Сборная", callback_data="fa_dest_nat")],
        [InlineKeyboardButton(text="Клуб или Сборная", callback_data="fa_dest_both")]
    ]
    await message.answer("Куда вы хотите переходить?", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
    await state.set_state(FreeAgentState.destination)

@dp.callback_query(FreeAgentState.destination, F.message.chat.type == ChatType.PRIVATE)
async def process_fa_dest(callback: types.CallbackQuery, state: FSMContext):
    dest_map = {"fa_dest_club": "Клуб", "fa_dest_nat": "Сборная", "fa_dest_both": "Клуб или Сборная"}
    data = await state.get_data()
    post_text = f"👤 <b>Свободный агент</b>\n\nНик: {data.get('nickname')}\nТребование: {data.get('requirements')}\nКуда: {dest_map.get(callback.data)}"
    await send_application(callback.from_user, post_text)
    await state.clear()
    await callback.answer()

# --- ПЕРЕХОД В КЛУБ ---
@dp.callback_query(F.data == "transfer_club", F.message.chat.type == ChatType.PRIVATE)
async def start_transfer(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("Откуда переходите? (Свободный агент или название клуба):")
    await state.set_state(TransferState.from_where)
    await callback.answer()

@dp.message(TransferState.from_where, F.chat.type == ChatType.PRIVATE)
async def process_tr_from(message: types.Message, state: FSMContext):
    await state.update_data(from_where=message.text)
    await message.answer("Куда переходите?")
    await state.set_state(TransferState.to_where)

@dp.message(TransferState.to_where, F.chat.type == ChatType.PRIVATE)
async def process_tr_to(message: types.Message, state: FSMContext):
    await state.update_data(to_where=message.text)
    await message.answer("Напишите вашу позицию:")
    await state.set_state(TransferState.position)

@dp.message(TransferState.position, F.chat.type == ChatType.PRIVATE)
async def process_tr_pos(message: types.Message, state: FSMContext):
    data = await state.get_data()
    post_text = f"⚽ <b>Переход в клуб</b>\n\nОткуда: {data.get('from_where')}\nКуда: {data.get('to_where')}\nПозиция: {message.text}"
    await send_application(message.from_user, post_text)
    await state.clear()

# --- СМЕНА НИКНЕЙМА ---
@dp.callback_query(F.data == "change_nick", F.message.chat.type == ChatType.PRIVATE)
async def start_change_nick(callback: types.CallbackQuery, state: FSMContext):
    nick = get_auto_nick(callback.from_user)
    await state.update_data(old_nick=nick)
    await callback.message.answer(
        f"✅ Ваш текущий ник: <b>{nick}</b>\n\nНапишите новый никнейм:",
        parse_mode="HTML"
    )
    await state.set_state(ChangeNickState.new_nick)
    await callback.answer()

@dp.message(ChangeNickState.new_nick, F.chat.type == ChatType.PRIVATE)
async def process_cn_new(message: types.Message, state: FSMContext):
    data = await state.get_data()
    post_text = f"🔄 <b>Смена никнейма</b>\n\nСтарый: {data.get('old_nick')}\nНовый: {message.text}"
    await send_application(message.from_user, post_text)
    await state.clear()

# --- СМЕНА ПОЗИЦИИ ---
@dp.callback_query(F.data == "change_pos", F.message.chat.type == ChatType.PRIVATE)
async def start_change_pos(callback: types.CallbackQuery, state: FSMContext):
    nick = get_auto_nick(callback.from_user)
    await state.update_data(nickname=nick)
    await callback.message.answer(f"✅ Ваш ник: <b>{nick}</b>\n\nНапишите вашу прошлую позицию:", parse_mode="HTML")
    await state.set_state(ChangePosState.old_pos)
    await callback.answer()

@dp.message(ChangePosState.old_pos, F.chat.type == ChatType.PRIVATE)
async def process_cp_old(message: types.Message, state: FSMContext):
    await state.update_data(old_pos=message.text)
    await message.answer("Напишите вашу нынешнюю позицию:")
    await state.set_state(ChangePosState.new_pos)

@dp.message(ChangePosState.new_pos, F.chat.type == ChatType.PRIVATE)
async def process_cp_new(message: types.Message, state: FSMContext):
    data = await state.get_data()
    post_text = f"🔄 <b>Смена позиции</b>\n\nНик: {data.get('nickname')}\nБыло: {data.get('old_pos')}\nСтало: {message.text}"
    await send_application(message.from_user, post_text)
    await state.clear()

# --- ЗАВЕРШЕНИЕ КАРЬЕРЫ (только P.S., без "Писать") ---
@dp.callback_query(F.data == "end_career", F.message.chat.type == ChatType.PRIVATE)
async def start_end_career(callback: types.CallbackQuery, state: FSMContext):
    nick = get_auto_nick(callback.from_user)
    await state.update_data(nickname=nick)
    await callback.message.answer(
        f"✅ Ваш ник: <b>{nick}</b>\n\nНапишите <b>P.S.</b>:",
        parse_mode="HTML"
    )
    await state.set_state(EndCareerState.ps)
    await callback.answer()

@dp.message(EndCareerState.ps, F.chat.type == ChatType.PRIVATE)
async def process_ec_ps(message: types.Message, state: FSMContext):
    data = await state.get_data()
    post_text = f"🏁 <b>Завершение карьеры</b>\n\nНик: {data.get('nickname')}\nP.S: {message.text}"
    await send_application(message.from_user, post_text, include_contact=False)
    await state.clear()

# --- ВОЗВРАЩЕНИЕ КАРЬЕРЫ ---
@dp.callback_query(F.data == "return_career", F.message.chat.type == ChatType.PRIVATE)
async def start_return_career(callback: types.CallbackQuery, state: FSMContext):
    nick = get_auto_nick(callback.from_user)
    await state.update_data(nickname=nick)
    await callback.message.answer(f"✅ Ваш ник: <b>{nick}</b>\n\nНапишите PS (причину возвращения):", parse_mode="HTML")
    await state.set_state(ReturnCareerState.ps)
    await callback.answer()

@dp.message(ReturnCareerState.ps, F.chat.type == ChatType.PRIVATE)
async def process_rc_ps(message: types.Message, state: FSMContext):
    data = await state.get_data()
    post_text = f"❤️ <b>Возвращение карьеры</b>\n\nНик: {data.get('nickname')}\nPS: {message.text}"
    await send_application(message.from_user, post_text)
    await state.clear()

# --- ПРИОСТАНОВЛЕНИЕ КАРЬЕРЫ ---
@dp.callback_query(F.data == "pause_career", F.message.chat.type == ChatType.PRIVATE)
async def start_pause_career(callback: types.CallbackQuery, state: FSMContext):
    nick = get_auto_nick(callback.from_user)
    await state.update_data(nickname=nick)
    await callback.message.answer(f"✅ Ваш ник: <b>{nick}</b>\n\nПочему решили приостановить карьеру?", parse_mode="HTML")
    await state.set_state(PauseCareerState.reason)
    await callback.answer()

@dp.message(PauseCareerState.reason, F.chat.type == ChatType.PRIVATE)
async def process_pc_reason(message: types.Message, state: FSMContext):
    data = await state.get_data()
    post_text = f"⏸️ <b>Приостановление карьеры</b>\n\nНик: {data.get('nickname')}\nПричина: {message.text}"
    await send_application(message.from_user, post_text)
    await state.clear()

# --- ПОИСК ТОВЫ ---
@dp.callback_query(F.data == "find_tour", F.message.chat.type == ChatType.PRIVATE)
async def start_find_tour(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("Напишите название вашего клуба:")
    await state.set_state(FindTourState.club)
    await callback.answer()

@dp.message(FindTourState.club, F.chat.type == ChatType.PRIVATE)
async def process_ft_club(message: types.Message, state: FSMContext):
    await state.update_data(club=message.text)
    await message.answer("Напишите время:")
    await state.set_state(FindTourState.time)

@dp.message(FindTourState.time, F.chat.type == ChatType.PRIVATE)
async def process_ft_time(message: types.Message, state: FSMContext):
    await state.update_data(time=message.text)
    await message.answer("Напишите стадион:")
    await state.set_state(FindTourState.stadium)

@dp.message(FindTourState.stadium, F.chat.type == ChatType.PRIVATE)
async def process_ft_stadium(message: types.Message, state: FSMContext):
    await state.update_data(stadium=message.text)
    await message.answer("VIP наше или ваше?")
    await state.set_state(FindTourState.vip)

@dp.message(FindTourState.vip, F.chat.type == ChatType.PRIVATE)
async def process_ft_vip(message: types.Message, state: FSMContext):
    data = await state.get_data()
    post_text = f"🏆 <b>Поиск товы</b>\n\nКлуб: {data.get('club')}\nВремя: {data.get('time')}\nСтадион: {data.get('stadium')}\nVIP: {message.text}"
    await send_application(message.from_user, post_text)
    await state.clear()

# --- ПОИСК ИГРОКОВ ---
@dp.callback_query(F.data == "find_players", F.message.chat.type == ChatType.PRIVATE)
async def start_find_players(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("Напишите ваше требование:")
    await state.set_state(FindPlayersState.requirement)
    await callback.answer()

@dp.message(FindPlayersState.requirement, F.chat.type == ChatType.PRIVATE)
async def process_fp_req(message: types.Message, state: FSMContext):
    post_text = f"🔎 <b>Поиск игроков</b>\n\nТребование: {message.text}"
    await send_application(message.from_user, post_text)
    await state.clear()

# --- СИСТЕМА КОНТРАКТОВ ---
@dp.callback_query(F.data == "contract_system", F.message.chat.type == ChatType.PRIVATE)
async def start_contract(callback: types.CallbackQuery, state: FSMContext):
    nick = get_auto_nick(callback.from_user)
    await state.update_data(nickname=nick)
    await callback.message.answer(
        f"✅ Ваш ник: <b>{nick}</b>\n\n📝 <b>Система контрактов</b>\n\nВведите название вашего клуба:",
        parse_mode="HTML"
    )
    await state.set_state(ContractState.club)
    await callback.answer()

@dp.message(ContractState.club, F.chat.type == ChatType.PRIVATE)
async def process_ct_club(message: types.Message, state: FSMContext):
    await state.update_data(club=message.text)
    await message.answer("Введите никнейм игрока, которого вы подписали:")
    await state.set_state(ContractState.player_nick)

@dp.message(ContractState.player_nick, F.chat.type == ChatType.PRIVATE)
async def process_ct_player(message: types.Message, state: FSMContext):
    await state.update_data(player_nick=message.text)
    await message.answer("Введите дату подписания контракта (например, 26.09.2026):")
    await state.set_state(ContractState.sign_date)

@dp.message(ContractState.sign_date, F.chat.type == ChatType.PRIVATE)
async def process_ct_date(message: types.Message, state: FSMContext):
    data = await state.get_data()
    post_text = (
        f"📝 <b>Система контрактов</b>\n\n"
        f"Клуб: {data.get('club')}\n"
        f"Никнейм игрока: {data.get('player_nick')}\n"
        f"Дата подписания: {message.text}"
    )
    await send_application(message.from_user, post_text)
    await state.clear()

# --- КУПИТЬ РЕКЛАМУ ---
@dp.callback_query(F.data == "buy_ad", F.message.chat.type == ChatType.PRIVATE)
async def process_buy_ad(callback: types.CallbackQuery):
    await callback.message.answer(
        f"✅ <b>Купить рекламу</b>\n\n"
        f"Чтобы купить рекламу, напишите модераторам в ЛС и переведите звёзды:\n\n"
        f"📩 {MODERATORS}",
        parse_mode="HTML"
    )
    await callback.answer()

# --- ТЕХПОДДЕРЖКА ---
@dp.callback_query(F.data == "support", F.message.chat.type == ChatType.PRIVATE)
async def process_support(callback: types.CallbackQuery):
    await callback.message.answer(
        f"🛠️ <b>Техподдержка</b>\n\n"
        f"По всем вопросам обращайтесь к модераторам:\n\n"
        f"📩 {MODERATORS}",
        parse_mode="HTML"
    )
    await callback.answer()

# --- ЖАЛОБЫ ---
@dp.callback_query(F.data == "complaints", F.message.chat.type == ChatType.PRIVATE)
async def process_complaints(callback: types.CallbackQuery):
    await callback.message.answer(
        f"📢 <b>Жалобы</b>\n\n"
        f"По жалобам обращайтесь к модераторам:\n\n"
        f"📩 {MODERATORS}",
        parse_mode="HTML"
    )
    await callback.answer()

# --- ЗАПУСК ---
async def main():
    logging.info("Запуск веб-сервера для Render...")
    app = web.Application()
    app.router.add_get('/', lambda r: web.Response(text="Bot is running"))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', PORT)
    await site.start()
    logging.info(f"Веб-сервер запущен на порту {PORT}")
    logging.info(f"GROUP_ID = {GROUP_ID}")
    logging.info(f"CHANNEL_ID = {CHANNEL_ID}")
    logging.info(f"Рабочие часы: {WORK_START}:00–{WORK_END}:00 МСК")

    logging.info("Запуск бота...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
