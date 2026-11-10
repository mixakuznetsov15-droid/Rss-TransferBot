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

# ⛔️ ВЫКЛЮЧАТЕЛЬ БОТА (True = включен, False = выключен)
BOT_ENABLED = True 

# ⚠️ Токен берется из настроек Render (Environment Variables)
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
PORT = int(os.getenv("PORT", 8080))

# ⚠️ ВАЖНО: Сюда нужен ЧИСЛОВОЙ ID новой группы! Ссылка не подойдет.
# Если бот не отправляет в группу, значит ID неверный или бот не админ.
GROUP_ID = -5437265461 

# ✅ Твой новый канал
CHANNEL_ID = "@FCSTRA" 
MODERATORS = "@Zyro0o0" 

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

# --- СОСТОЯНИЯ (FSM) ---
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

class ModerationState(StatesGroup):
    waiting_decline_reason = State()

# --- МЕНЮ ---
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

# --- ОТПРАВКА ЗАЯВКИ (в группу) ---
async def send_application(user: types.User, text: str, include_contact: bool = True):
    if not is_working_hours():
        try:
            await bot.send_message(
                chat_id=user.id,
                text=f"❗ <b>Бот закончил работу на сегодня.</b>\n\n{work_hours_text()}\n\nВаша заявка не была отправлена.",
                parse_mode="HTML"
            )
        except Exception as e:
            logging.error(f"Не удалось уведомить пользователя {user.id}: {e}")
        return
    
    contact = get_author_contact(user)
    
    if include_contact:
        full_text = f"{text}\n\n📝 <b>Писать:</b> {contact}\n\n📩 <b>Админы:</b> {MODERATORS}"
    else:
        full_text = f"{text}\n\n📩 <b>Админы:</b> {MODERATORS}"
    
    mod_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Принять", callback_data=f"mod_accept_{user.id}"),
         InlineKeyboardButton(text="❌ Отказать", callback_data=f"mod_decline_{user.id}")]
    ])
    
    try:
        await bot.send_message(chat_id=GROUP_ID, text=full_text, parse_mode="HTML", reply_markup=mod_kb)
    except Exception as e:
        logging.error(f"Ошибка отправки в группу: {e}")

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

# --- ОБЩИЕ КНОПКИ ---
@dp.callback_query(F.data == "cancel_to_main")
async def cb_cancel_to_main(call: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text("<b>Выбери категорию:</b>", parse_mode="HTML", reply_markup=get_main_menu())

@dp.callback_query(F.data == "buy_ad")
async def cb_buy_ad(call: types.CallbackQuery):
    await call.message.edit_text("<b>Купить рекламу можно у @Zyro0o0</b>", parse_mode="HTML", reply_markup=get_main_menu())

@dp.callback_query(F.data == "mirror")
async def cb_mirror(call: types.CallbackQuery):
    await call.message.edit_text("<b>Зеркало — 50 звёзд. По вопросам писать: @Zyro0o0</b>", parse_mode="HTML", reply_markup=get_main_menu())

@dp.callback_query(F.data == "support")
async def cb_support(call: types.CallbackQuery):
    await call.message.edit_text(f"<b>Техподдержка:</b>\nПо всем вопросам писать: {MODERATORS}", parse_mode="HTML", reply_markup=get_main_menu())

@dp.callback_query(F.data == "complaints")
async def cb_complaints(call: types.CallbackQuery):
    await call.message.edit_text(f"<b>Жалобы:</b>\nПо всем вопросам писать: {MODERATORS}", parse_mode="HTML", reply_markup=get_main_menu())

# --- ОБРАБОТКА ПОДТВЕРЖДЕНИЯ (Согласны) ---
@dp.callback_query(F.data.startswith("accept_"))
async def cb_accept(call: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    final_text = data.get("final_text", "Заявка без текста")
    include_contact = data.get("include_contact", True)
    
    await send_application(call.from_user, final_text, include_contact)
    await state.clear()
    
    back_kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Вернуться в меню", callback_data="cancel_to_main")]])
    # Измененный текст без ников админов
    await call.message.edit_text("✅ <b>Заявка отправлена админам.</b>\n\nОжидайте ответа.", parse_mode="HTML", reply_markup=back_kb)

# --- СМЕНА ПОЗИЦИИ ---
@dp.callback_query(F.data == "change_pos")
async def cb_change_pos(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(ChangePosState.old_pos)
    await call.message.edit_text(
        "<b>Выберите старую позицию, затем новую:</b>\n\n<b>Ваш текущий ник:</b> " + get_auto_nick(call.from_user),
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
    
    await state.update_data(final_text=text, include_contact=False)
    await call.message.edit_text(text, parse_mode="HTML", reply_markup=get_final_menu("change_pos"))

# --- СВОБОДНЫЙ АГЕНТ ---
@dp.callback_query(F.data == "free_agent")
async def cb_free_agent(call: types.CallbackQuery, state: FSMContext):
    await state.update_data(nickname=get_auto_nick(call.from_user))
    await state.set_state(FreeAgentState.requirements)
    await call.message.edit_text("<b>Введите ваше требование:</b>", parse_mode="HTML")

@dp.message(FreeAgentState.requirements)
async def process_fa_req(message: types.Message, state: FSMContext):
    await state.update_data(requirements=message.text)
    await state.set_state(FreeAgentState.destination)
    await message.answer("<b>Куда вы хотите переходить?</b> (Клуб / Сборная / Клуб или Сборная)", parse_mode="HTML")

@dp.message(FreeAgentState.destination)
async def process_fa_dest(message: types.Message, state: FSMContext):
    data = await state.get_data()
    text = f"👤 <b>Свободный агент</b>\n\n<b>Ник:</b> {data.get('nickname')}\n<b>Требование:</b> {data.get('requirements')}\n<b>Куда:</b> {message.text}"
    await state.update_data(final_text=text, include_contact=True)
    await message.answer(text, parse_mode="HTML", reply_markup=get_final_menu("free_agent"))

# --- ПЕРЕХОД В КЛУБ ---
@dp.callback_query(F.data == "transfer_club")
async def cb_transfer_club(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(TransferState.from_where)
    await call.message.edit_text("<b>Откуда переходите?</b> (Свободный агент или название клуба)", parse_mode="HTML")

@dp.message(TransferState.from_where)
async def process_tr_from(message: types.Message, state: FSMContext):
    await state.update_data(from_where=message.text)
    await state.set_state(TransferState.to_where)
    await message.answer("<b>Куда переходите?</b>", parse_mode="HTML")

@dp.message(TransferState.to_where)
async def process_tr_to(message: types.Message, state: FSMContext):
    await state.update_data(to_where=message.text)
    await state.set_state(TransferState.position)
    await message.answer("<b>Напишите вашу позицию:</b>", parse_mode="HTML")

@dp.message(TransferState.position)
async def process_tr_pos(message: types.Message, state: FSMContext):
    data = await state.get_data()
    text = f"⚽ <b>Переход в клуб</b>\n\n<b>Откуда:</b> {data.get('from_where')}\n<b>Куда:</b> {data.get('to_where')}\n<b>Позиция:</b> {message.text}"
    await state.update_data(final_text=text, include_contact=True)
    await message.answer(text, parse_mode="HTML", reply_markup=get_final_menu("transfer"))

# --- СМЕНА НИКНЕЙМА ---
@dp.callback_query(F.data == "change_nick")
async def cb_change_nick(call: types.CallbackQuery, state: FSMContext):
    await state.update_data(old_nick=get_auto_nick(call.from_user))
    await state.set_state(ChangeNickState.new_nick)
    await call.message.edit_text(f"<b>Ваш текущий ник:</b> {get_auto_nick(call.from_user)}\n\n<b>Напишите новый никнейм:</b>", parse_mode="HTML")

@dp.message(ChangeNickState.new_nick)
async def process_cn_new(message: types.Message, state: FSMContext):
    data = await state.get_data()
    text = f"🔄 <b>Смена никнейма</b>\n\n<b>Старый:</b> {data.get('old_nick')}\n<b>Новый:</b> {message.text}"
    await state.update_data(final_text=text, include_contact=True)
    await message.answer(text, parse_mode="HTML", reply_markup=get_final_menu("change_nick"))

# --- ЗАВЕРШЕНИЕ КАРЬЕРЫ ---
@dp.callback_query(F.data == "end_career")
async def cb_end_career(call: types.CallbackQuery, state: FSMContext):
    await state.update_data(nickname=get_auto_nick(call.from_user))
    await state.set_state(EndCareerState.ps)
    await call.message.edit_text(f"<b>Ваш ник:</b> {get_auto_nick(call.from_user)}\n\n<b>Напишите P.S.:</b>", parse_mode="HTML")

@dp.message(EndCareerState.ps)
async def process_ec_ps(message: types.Message, state: FSMContext):
    data = await state.get_data()
    text = f"🥀 <b>Завершение карьеры</b>\n\n<b>Ник:</b> {data.get('nickname')}\n<b>P.S:</b> {message.text}"
    await state.update_data(final_text=text, include_contact=False)
    await message.answer(text, parse_mode="HTML", reply_markup=get_final_menu("end_career"))

# --- ВОЗВРАЩЕНИЕ КАРЬЕРЫ ---
@dp.callback_query(F.data == "return_career")
async def cb_return_career(call: types.CallbackQuery, state: FSMContext):
    await state.update_data(nickname=get_auto_nick(call.from_user))
    await state.set_state(ReturnCareerState.ps)
    await call.message.edit_text(f"<b>Ваш ник:</b> {get_auto_nick(call.from_user)}\n\n<b>Напишите PS (причину возвращения):</b>", parse_mode="HTML")

@dp.message(ReturnCareerState.ps)
async def process_rc_ps(message: types.Message, state: FSMContext):
    data = await state.get_data()
    text = f"❤️ <b>Возвращение карьеры</b>\n\n<b>Ник:</b> {data.get('nickname')}\n<b>PS:</b> {message.text}"
    await state.update_data(final_text=text, include_contact=True)
    await message.answer(text, parse_mode="HTML", reply_markup=get_final_menu("return_career"))

# --- ПРИОСТАНОВЛЕНИЕ КАРЬЕРЫ ---
@dp.callback_query(F.data == "pause_career")
async def cb_pause_career(call: types.CallbackQuery, state: FSMContext):
    await state.update_data(nickname=get_auto_nick(call.from_user))
    await state.set_state(PauseCareerState.reason)
    await call.message.edit_text(f"<b>Ваш ник:</b> {get_auto_nick(call.from_user)}\n\n<b>Почему решили приостановить карьеру?</b>", parse_mode="HTML")

@dp.message(PauseCareerState.reason)
async def process_pc_reason(message: types.Message, state: FSMContext):
    data = await state.get_data()
    text = f"🥀 <b>Приостановление карьеры</b>\n\n<b>Ник:</b> {data.get('nickname')}\n<b>Причина:</b> {message.text}"
    await state.update_data(final_text=text, include_contact=True)
    await message.answer(text, parse_mode="HTML", reply_markup=get_final_menu("pause_career"))

# --- ПОИСК ТОВЫ ---
@dp.callback_query(F.data == "find_tour")
async def cb_find_tour(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(FindTourState.club)
    await call.message.edit_text("<b>Введите название вашего клуба:</b>", parse_mode="HTML")

@dp.message(FindTourState.club)
async def process_tour_club(message: types.Message, state: FSMContext):
    await state.update_data(club=message.text)
    await state.set_state(FindTourState.time)
    await message.answer("<b>Введите время (например, 18:00 или D):</b>", parse_mode="HTML")

@dp.message(FindTourState.time)
async def process_tour_time(message: types.Message, state: FSMContext):
    await state.update_data(time=message.text)
    await state.set_state(FindTourState.stadium)
    await message.answer("<b>Введите стадион:</b>", parse_mode="HTML")

@dp.message(FindTourState.stadium)
async def process_tour_stadium(message: types.Message, state: FSMContext):
    await state.update_data(stadium=message.text)
    await state.set_state(FindTourState.vip)
    # Измененный текст VIP
    await message.answer("<b>VIP (да / нет):</b>", parse_mode="HTML")

@dp.message(FindTourState.vip)
async def process_tour_vip(message: types.Message, state: FSMContext):
    data = await state.get_data()
    text = f"🏆 <b>Поиск товы</b>\n\n<b>Клуб:</b> {data.get('club')}\n<b>Время:</b> {data.get('time')}\n<b>Стадион:</b> {data.get('stadium')}\n<b>VIP:</b> {message.text}"
    await state.update_data(final_text=text, include_contact=True)
    await message.answer(text, parse_mode="HTML", reply_markup=get_final_menu("find_tour"))

# --- ПОИСК ИГРОКОВ ---
@dp.callback_query(F.data == "find_players")
async def cb_find_players(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(FindPlayersState.requirement)
    await call.message.edit_text("<b>Напишите ваше требование:</b>", parse_mode="HTML")

@dp.message(FindPlayersState.requirement)
async def process_fp_req(message: types.Message, state: FSMContext):
    text = f"🔎 <b>Поиск игроков</b>\n\n<b>Требование:</b> {message.text}"
    await state.update_data(final_text=text, include_contact=True)
    await message.answer(text, parse_mode="HTML", reply_markup=get_final_menu("find_players"))

# --- МОДЕРАЦИЯ (В ГРУППЕ) ---
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
        clean_text = original_text.split("\n\n📩 Админы:")[0]
        channel_post = clean_text
    
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.reply(f"✅ Принято модератором {mod_display}")
    
    try:
        await bot.send_message(chat_id=CHANNEL_ID, text=channel_post, parse_mode="HTML")
    except Exception as e:
        logging.error(f"Ошибка публикации в канал: {e}")
    
    try:
        await bot.send_message(chat_id=user_id, text=f"✅ <b>Ваша заявка принята и опубликована!</b>\n\n{clean_text}", parse_mode="HTML")
    except Exception as e:
        logging.error(f"Не удалось уведомить пользователя {user_id}: {e}")
    
    await callback.answer("Заявка принята и опубликована!")

@dp.callback_query(F.data.startswith("mod_decline_"), F.message.chat.type.in_({ChatType.GROUP, ChatType.SUPERGROUP}))
async def mod_decline(callback: types.CallbackQuery, state: FSMContext):
    user_id = int(callback.data.replace("mod_decline_", ""))
    mod_display = get_mod_display(callback.from_user)
    
    original_text = callback.message.text or ""
    if "📝 Писать:" in original_text:
        clean_text = original_text.split("\n\n📝 Писать:")[0]
    else:
        clean_text = original_text.split("\n\n📩 Админы:")[0]
    
    await callback.message.edit_reply_markup(reply_markup=None)
    
    await state.update_data(author_id=user_id, clean_text=clean_text, mod_display=mod_display)
    await state.set_state(ModerationState.waiting_decline_reason)
    
    await callback.message.reply(f"❌ <b>Отклонено модератором {mod_display}.</b>\n\n✍️ Напишите причину отказа <b>следующим сообщением</b> в чат.", parse_mode="HTML")
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
            text=f"❌ <b>Ваша заявка отклонена.</b>\n\n<b>Заявка:</b>\n{clean_text}\n\n<b>Причина отказа:</b> {reason}\n\n<b>Модератор:</b> {mod_display}\n\nЕсли вы не согласны — свяжитесь с админами: {MODERATORS}",
            parse_mode="HTML"
        )
        await message.reply("✅ Причина отказа отправлена автору заявки.")
    except Exception as e:
        logging.error(f"Не удалось уведомить пользователя {author_id}: {e}")
        await message.reply(f"⚠️ Не удалось отправить уведомление автору (ID: {author_id}).")

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

    if BOT_ENABLED:
        logging.info("Запуск бота...")
        await dp.start_polling(bot)
    else:
        logging.info("⛔️ БОТ ВРЕМЕННО ОСТАНОВЛЕН.")
        while True:
            await asyncio.sleep(3600)

if __name__ == "__main__":
    asyncio.run(main())