import asyncio
import logging
import os
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
CHANNEL_ID = 0  # ⚠️ СЮДА ВСТАВЬ ID КАНАЛА
MODERATORS = "@Tot_samiy_onet, @meelviks"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=TOKEN)
dp = Dispatcher()

# --- СОСТОЯНИЯ (FSM) ---
class FreeAgentState(StatesGroup):
    nickname = State()
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
    nickname = State()
    old_pos = State()
    new_pos = State()

class EndCareerState(StatesGroup):
    nickname = State()
    reason = State()
    position = State()

class ReturnCareerState(StatesGroup):
    nickname = State()
    ps = State()

class PauseCareerState(StatesGroup):
    nickname = State()
    reason = State()

class FindTourState(StatesGroup):
    club = State()
    time = State()
    stadium = State()
    vip = State()

class FindPlayersState(StatesGroup):
    requirement = State()

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
        [InlineKeyboardButton(text="🛠️ Техподдержка", callback_data="support"),
         InlineKeyboardButton(text="📢 Жалобы", callback_data="complaints")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# --- КОМАНДЫ (работают везде) ---
@dp.message(CommandStart(), F.chat.type == ChatType.PRIVATE)
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("Выбери категорию:", reply_markup=get_main_menu())

@dp.message(Command("id"))
async def cmd_id(message: types.Message):
    await message.answer(f"Chat ID: <code>{message.chat.id}</code>", parse_mode="HTML")

@dp.message(Command("cancel"), F.chat.type == ChatType.PRIVATE)
async def cmd_cancel(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("Действие отменено. Выбери категорию:", reply_markup=get_main_menu())

# --- ФУНКЦИЯ ОТПРАВКИ ЗАЯВКИ ---
async def send_application(message: types.Message, text: str):
    user = message.from_user
    if user.username:
        author = f"@{user.username}"
    else:
        author = f"{user.full_name} (ID: {user.id})"
    
    full_text = f"{text}\n\n👤 <b>Автор:</b> {author}\n\n📩 <b>Модераторы:</b> {MODERATORS}"
    
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
    await message.answer(
        f"✅ <b>Заявка отправлена модераторам:</b>\n{MODERATORS}\n\nОжидай ответа.",
        parse_mode="HTML",
        reply_markup=back_kb
    )

# --- МОДЕРАЦИЯ (работает только в группе) ---
@dp.callback_query(F.data.startswith("mod_accept_"), F.message.chat.type.in_({ChatType.GROUP, ChatType.SUPERGROUP}))
async def mod_accept(callback: types.CallbackQuery):
    user_id = int(callback.data.replace("mod_accept_", ""))
    
    if callback.message.text:
        original_text = callback.message.text
        clean_text = original_text.split("\n\n👤 ")[0]
        author_line = ""
        if "👤 " in original_text:
            author_part = original_text.split("👤 ")[1].split("\n")[0]
            author_line = author_part.replace("<b>", "").replace("</b>", "").replace("Автор: ", "")
    else:
        clean_text = "Заявка"
        author_line = "Неизвестно"
    
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.reply(f"✅ Принято модератором {callback.from_user.full_name}")
    
    channel_post = f"{clean_text}\n\n👤 {author_line}"
    try:
        if CHANNEL_ID != 0:
            await bot.send_message(chat_id=CHANNEL_ID, text=channel_post, parse_mode="HTML")
            logging.info(f"Заявка опубликована в канал {CHANNEL_ID}")
        else:
            logging.warning("CHANNEL_ID не настроен, публикация пропущена")
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

@dp.callback_query(F.data.startswith("mod_decline_"), F.message.chat.type.in_({ChatType.GROUP, ChatType.SUPERGROUP}))
async def mod_decline(callback: types.CallbackQuery):
    user_id = int(callback.data.replace("mod_decline_", ""))
    
    if callback.message.text:
        original_text = callback.message.text
        clean_text = original_text.split("\n\n👤 ")[0]
    else:
        clean_text = "Заявка"
    
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.reply(f"❌ Отклонено модератором {callback.from_user.full_name}")
    
    try:
        await bot.send_message(
            chat_id=user_id,
            text=f"❌ <b>Ваша заявка отклонена.</b>\n\n"
                 f"Заявка: {clean_text}\n\n"
                 f"Если вы не согласны — свяжитесь с модераторами: {MODERATORS}",
            parse_mode="HTML"
        )
    except Exception as e:
        logging.error(f"Не удалось уведомить пользователя {user_id}: {e}")
    
    await callback.answer("Заявка отклонена!")

# --- МЕНЮ-КНОПКИ (только в личке) ---
@dp.callback_query(F.data == "back_to_menu", F.message.chat.type == ChatType.PRIVATE)
async def back_to_menu_handler(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("Выбери категорию:", reply_markup=get_main_menu())
    await callback.answer()

# --- СВОБОДНЫЙ АГЕНТ ---
@dp.callback_query(F.data == "free_agent", F.message.chat.type == ChatType.PRIVATE)
async def start_free_agent(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("Напишите ваш никнейм (или /cancel для отмены):")
    await state.set_state(FreeAgentState.nickname)
    await callback.answer()

@dp.message(FreeAgentState.nickname, F.chat.type == ChatType.PRIVATE)
async def process_fa_nick(message: types.Message, state: FSMContext):
    await state.update_data(nickname=message.text)
    await message.answer("Напишите ваше требование:")
    await state.set_state(FreeAgentState.requirements)

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
    await send_application(callback.message, post_text)
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
    await send_application(message, post_text)
    await state.clear()

# --- СМЕНА НИКНЕЙМА ---
@dp.callback_query(F.data == "change_nick", F.message.chat.type == ChatType.PRIVATE)
async def start_change_nick(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("Какой у вас никнейм был изначально?")
    await state.set_state(ChangeNickState.old_nick)
    await callback.answer()

@dp.message(ChangeNickState.old_nick, F.chat.type == ChatType.PRIVATE)
async def process_cn_old(message: types.Message, state: FSMContext):
    await state.update_data(old_nick=message.text)
    await message.answer("Какой никнейм хотите сделать?")
    await state.set_state(ChangeNickState.new_nick)

@dp.message(ChangeNickState.new_nick, F.chat.type == ChatType.PRIVATE)
async def process_cn_new(message: types.Message, state: FSMContext):
    data = await state.get_data()
    post_text = f"🔄 <b>Смена никнейма</b>\n\nСтарый: {data.get('old_nick')}\nНовый: {message.text}"
    await send_application(message, post_text)
    await state.clear()

# --- СМЕНА ПОЗИЦИИ ---
@dp.callback_query(F.data == "change_pos", F.message.chat.type == ChatType.PRIVATE)
async def start_change_pos(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("Напишите ваш никнейм:")
    await state.set_state(ChangePosState.nickname)
    await callback.answer()

@dp.message(ChangePosState.nickname, F.chat.type == ChatType.PRIVATE)
async def process_cp_nick(message: types.Message, state: FSMContext):
    await state.update_data(nickname=message.text)
    await message.answer("Напишите вашу прошлую позицию:")
    await state.set_state(ChangePosState.old_pos)

@dp.message(ChangePosState.old_pos, F.chat.type == ChatType.PRIVATE)
async def process_cp_old(message: types.Message, state: FSMContext):
    await state.update_data(old_pos=message.text)
    await message.answer("Напишите вашу нынешнюю позицию:")
    await state.set_state(ChangePosState.new_pos)

@dp.message(ChangePosState.new_pos, F.chat.type == ChatType.PRIVATE)
async def process_cp_new(message: types.Message, state: FSMContext):
    data = await state.get_data()
    post_text = f"🔄 <b>Смена позиции</b>\n\nНик: {data.get('nickname')}\nБыло: {data.get('old_pos')}\nСтало: {message.text}"
    await send_application(message, post_text)
    await state.clear()

# --- ЗАВЕРШЕНИЕ КАРЬЕРЫ ---
@dp.callback_query(F.data == "end_career", F.message.chat.type == ChatType.PRIVATE)
async def start_end_career(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("Напишите ваш никнейм:")
    await state.set_state(EndCareerState.nickname)
    await callback.answer()

@dp.message(EndCareerState.nickname, F.chat.type == ChatType.PRIVATE)
async def process_ec_nick(message: types.Message, state: FSMContext):
    await state.update_data(nickname=message.text)
    await message.answer("Почему решили завершить карьеру?")
    await state.set_state(EndCareerState.reason)

@dp.message(EndCareerState.reason, F.chat.type == ChatType.PRIVATE)
async def process_ec_reason(message: types.Message, state: FSMContext):
    await state.update_data(reason=message.text)
    await message.answer("На какой позиции вы играли?")
    await state.set_state(EndCareerState.position)

@dp.message(EndCareerState.position, F.chat.type == ChatType.PRIVATE)
async def process_ec_pos(message: types.Message, state: FSMContext):
    data = await state.get_data()
    post_text = f"🏁 <b>Завершение карьеры</b>\n\nНик: {data.get('nickname')}\nПричина: {data.get('reason')}\nПозиция: {message.text}"
    await send_application(message, post_text)
    await state.clear()

# --- ВОЗВРАЩЕНИЕ КАРЬЕРЫ ---
@dp.callback_query(F.data == "return_career", F.message.chat.type == ChatType.PRIVATE)
async def start_return_career(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("Напишите ваш никнейм:")
    await state.set_state(ReturnCareerState.nickname)
    await callback.answer()

@dp.message(ReturnCareerState.nickname, F.chat.type == ChatType.PRIVATE)
async def process_rc_nick(message: types.Message, state: FSMContext):
    await state.update_data(nickname=message.text)
    await message.answer("Напишите PS (причину возвращения):")
    await state.set_state(ReturnCareerState.ps)

@dp.message(ReturnCareerState.ps, F.chat.type == ChatType.PRIVATE)
async def process_rc_ps(message: types.Message, state: FSMContext):
    data = await state.get_data()
    post_text = f"❤️ <b>Возвращение карьеры</b>\n\nНик: {data.get('nickname')}\nPS: {message.text}"
    await send_application(message, post_text)
    await state.clear()

# --- ПРИОСТАНОВЛЕНИЕ КАРЬЕРЫ ---
@dp.callback_query(F.data == "pause_career", F.message.chat.type == ChatType.PRIVATE)
async def start_pause_career(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("Напишите ваш никнейм:")
    await state.set_state(PauseCareerState.nickname)
    await callback.answer()

@dp.message(PauseCareerState.nickname, F.chat.type == ChatType.PRIVATE)
async def process_pc_nick(message: types.Message, state: FSMContext):
    await state.update_data(nickname=message.text)
    await message.answer("Почему решили приостановить карьеру?")
    await state.set_state(PauseCareerState.reason)

@dp.message(PauseCareerState.reason, F.chat.type == ChatType.PRIVATE)
async def process_pc_reason(message: types.Message, state: FSMContext):
    data = await state.get_data()
    post_text = f"⏸️ <b>Приостановление карьеры</b>\n\nНик: {data.get('nickname')}\nПричина: {message.text}"
    await send_application(message, post_text)
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
    post_text = f"🏆 <b>Поиск товы (товарищеский матч)</b>\n\nКлуб: {data.get('club')}\nВремя: {data.get('time')}\nСтадион: {data.get('stadium')}\nVIP: {message.text}"
    await send_application(message, post_text)
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
    await send_application(message, post_text)
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

    logging.info("Запуск бота...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
