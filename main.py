import asyncio
import logging
import os
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiohttp import web

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
PORT = int(os.getenv("PORT", 8080))
GROUP_ID = -1004402712685
MODERATORS = "@tot_samiy_onet, @meelviks, @kelist1"

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

# --- КОМАНДЫ ---
@dp.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("Выбери категорию:", reply_markup=get_main_menu())

@dp.message(Command("id"))
async def cmd_id(message: types.Message):
    await message.answer(f"Chat ID: `{message.chat.id}`", parse_mode="Markdown")

@dp.message(Command("cancel"))
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
    
    full_text = f"{text}\n\n👤 **Автор:** {author}\n\n📩 **Модераторы:** {MODERATORS}"
    
    mod_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Принять", callback_data="mod_accept"),
         InlineKeyboardButton(text="❌ Отказать", callback_data="mod_decline")]
    ])
    
    try:
        await bot.send_message(chat_id=GROUP_ID, text=full_text, parse_mode="Markdown", reply_markup=mod_kb)
    except Exception as e:
        logging.error(f"Ошибка отправки в группу: {e}")
    
    back_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Вернуться в меню", callback_data="back_to_menu")]
    ])
    await message.answer(
        f"✅ **Заявка отправлена модераторам:**\n{MODERATORS}\n\nОжидай ответа.",
        parse_mode="Markdown",
        reply_markup=back_kb
    )

# --- МОДЕРАЦИЯ ---
@dp.callback_query(F.data == "mod_accept")
async def mod_accept(callback: types.CallbackQuery):
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.reply(f"✅ Принято модератором {callback.from_user.full_name}")
    await callback.answer("Заявка принята!")

@dp.callback_query(F.data == "mod_decline")
async def mod_decline(callback: types.CallbackQuery):
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.reply(f"❌ Отклонено модератором {callback.from_user.full_name}")
    await callback.answer("Заявка отклонена!")

@dp.callback_query(F.data == "back_to_menu")
async def back_to_menu_handler(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("Выбери категорию:", reply_markup=get_main_menu())
    await callback.answer()

# --- СВОБОДНЫЙ АГЕНТ ---
@dp.callback_query(F.data == "free_agent")
async def start_free_agent(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("Напишите ваш никнейм (или /cancel для отмены):")
    await state.set_state(FreeAgentState.nickname)
    await callback.answer()

@dp.message(FreeAgentState.nickname)
async def process_fa_nick(message: types.Message, state: FSMContext):
    await state.update_data(nickname=message.text)
    await message.answer("Напишите ваше требование:")
    await state.set_state(FreeAgentState.requirements)

@dp.message(FreeAgentState.requirements)
async def process_fa_req(message: types.Message, state: FSMContext):
    await state.update_data(requirements=message.text)
    buttons = [
        [InlineKeyboardButton(text="Клуб", callback_data="fa_dest_club")],
        [InlineKeyboardButton(text="Сборная", callback_data="fa_dest_nat")],
        [InlineKeyboardButton(text="Клуб или Сборная", callback_data="fa_dest_both")]
    ]
    await message.answer("Куда вы хотите переходить?", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
    await state.set_state(FreeAgentState.destination)

@dp.callback_query(FreeAgentState.destination)
async def process_fa_dest(callback: types.CallbackQuery, state: FSMContext):
    dest_map = {"fa_dest_club": "Клуб", "fa_dest_nat": "Сборная", "fa_dest_both": "Клуб или Сборная"}
    data = await state.get_data()
    post_text = f"👤 **Свободный агент**\n\nНик: {data.get('nickname')}\nТребование: {data.get('requirements')}\nКуда: {dest_map.get(callback.data)}"
    await send_application(callback.message, post_text)
    await state.clear()
    await callback.answer()

# --- ПЕРЕХОД В КЛУБ ---
@dp.callback_query(F.data == "transfer_club")
async def start_transfer(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("Откуда переходите? (Свободный агент или название клуба):")
    await state.set_state(TransferState.from_where)
    await callback.answer()

@dp.message(TransferState.from_where)
async def process_tr_from(message: types.Message, state: FSMContext):
    await state.update_data(from_where=message.text)
    await message.answer("Куда переходите?")
    await state.set_state(TransferState.to_where)

@dp.message(TransferState.to_where)
async def process_tr_to(message: types.Message, state: FSMContext):
    await state.update_data(to_where=message.text)
    await message.answer("Напишите вашу позицию:")
    await state.set_state(TransferState.position)

@dp.message(TransferState.position)
async def process_tr_pos(message: types.Message, state: FSMContext):
    data = await state.get_data()
    post_text = f"⚽ **Переход в клуб**\n\nОткуда: {data.get('from_where')}\nКуда: {data.get('to_where')}\nПозиция: {message.text}"
    await send_application(message, post_text)
    await state.clear()

# --- СМЕНА НИКНЕЙМА ---
@dp.callback_query(F.data == "change_nick")
async def start_change_nick(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("Какой у вас никнейм был изначально?")
    await state.set_state(ChangeNickState.old_nick)
    await callback.answer()

@dp.message(ChangeNickState.old_nick)
async def process_cn_old(message: types.Message, state: FSMContext):
    await state.update_data(old_nick=message.text)
    await message.answer("Какой никнейм хотите сделать?")
    await state.set_state(ChangeNickState.new_nick)

@dp.message(ChangeNickState.new_nick)
async def process_cn_new(message: types.Message, state: FSMContext):
    data = await state.get_data()
    post_text = f"🔄 **Смена никнейма**\n\nСтарый: {data.get('old_nick')}\nНовый: {message.text}"
    await send_application(message, post_text)
    await state.clear()

# --- СМЕНА ПОЗИЦИИ ---
@dp.callback_query(F.data == "change_pos")
async def start_change_pos(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("Напишите ваш никнейм:")
    await state.set_state(ChangePosState.nickname)
    await callback.answer()

@dp.message(ChangePosState.nickname)
async def process_cp_nick(message: types.Message, state: FSMContext):
    await state.update_data(nickname=message.text)
    await message.answer("Напишите вашу прошлую позицию:")
    await state.set_state(ChangePosState.old_pos)

@dp.message(ChangePosState.old_pos)
async def process_cp_old(message: types.Message, state: FSMContext):
    await state.update_data(old_pos=message.text)
    await message.answer("Напишите вашу нынешнюю позицию:")
    await state.set_state(ChangePosState.new_pos)

@dp.message(ChangePosState.new_pos)
async def process_cp_new(message: types.Message, state: FSMContext):
    data = await state.get_data()
    post_text = f"🔄 **Смена позиции**\n\nНик: {data.get('nickname')}\nБыло: {data.get('old_pos')}\nСтало: {message.text}"
    await send_application(message, post_text)
    await state.clear()

# --- ЗАВЕРШЕНИЕ КАРЬЕРЫ ---
@dp.callback_query(F.data == "end_career")
async def start_end_career(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("Напишите ваш никнейм:")
    await state.set_state(EndCareerState.nickname)
    await callback.answer()

@dp.message(EndCareerState.nickname)
async def process_ec_nick(message: types.Message, state: FSMContext):
    await state.update_data(nickname=message.text)
    await message.answer("Почему решили завершить карьеру?")
    await state.set_state(EndCareerState.reason)

@dp.message(EndCareerState.reason)
async def process_ec_reason(message: types.Message, state: FSMContext):
    await state.update_data(reason=message.text)
    await message.answer("На какой позиции вы играли?")
    await state.set_state(EndCareerState.position)

@dp.message(EndCareerState.position)
async def process_ec_pos(message: types.Message, state: FSMContext):
    data = await state.get_data()
    post_text = f"🏁 **Завершение карьеры**\n\nНик: {data.get('nickname')}\nПричина: {data.get('reason')}\nПозиция: {message.text}"
    await send_application(message, post_text)
    await state.clear()

# --- ВОЗВРАЩЕНИЕ КАРЬЕРЫ ---
@dp.callback_query(F.data == "return_career")
async def start_return_career(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("Напишите ваш никнейм:")
    await state.set_state(ReturnCareerState.nickname)
    await callback.answer()

@dp.message(ReturnCareerState.nickname)
async def process_rc_nick(message: types.Message, state: FSMContext):
    await state.update_data(nickname=message.text)
    await message.answer("Напишите PS (причину возвращения):")
    await state.set_state(ReturnCareerState.ps)

@dp.message(ReturnCareerState.ps)
async def process_rc_ps(message: types.Message, state: FSMContext):
    data = await state.get_data()
    post_text = f"❤️ **Возвращение карьеры**\n\nНик: {data.get('nickname')}\nPS: {message.text}"
    await send_application(message, post_text)
    await state.clear()

# --- ПРИОСТАНОВЛЕНИЕ КАРЬЕРЫ ---
@dp.callback_query(F.data == "pause_career")
async def start_pause_career(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("Напишите ваш никнейм:")
    await state.set_state(PauseCareerState.nickname)
    await callback.answer()

@dp.message(PauseCareerState.nickname)
async def process_pc_nick(message: types.Message, state: FSMContext):
    await state.update_data(nickname=message.text)
    await message.answer("Почему решили приостановить карьеру?")
    await state.set_state(PauseCareerState.reason)

@dp.message(PauseCareerState.reason)
async def process_pc_reason(message: types.Message, state: FSMContext):
    data = await state.get_data()
    post_text = f"⏸️ **Приостановление карьеры**\n\nНик: {data.get('nickname')}\nПричина: {message.text}"
    await send_application(message, post_text)
    await state.clear()

# --- ПОИСК ТОВЫ (товарищеский матч) ---
@dp.callback_query(F.data == "find_tour")
async def start_find_tour(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("Напишите название вашего клуба:")
    await state.set_state(FindTourState.club)
    await callback.answer()

@dp.message(FindTourState.club)
async def process_ft_club(message: types.Message, state: FSMContext):
    await state.update_data(club=message.text)
    await message.answer("Напишите время:")
    await state.set_state(FindTourState.time)

@dp.message(FindTourState.time)
async def process_ft_time(message: types.Message, state: FSMContext):
    await state.update_data(time=message.text)
    await message.answer("Напишите стадион:")
    await state.set_state(FindTourState.stadium)

@dp.message(FindTourState.stadium)
async def process_ft_stadium(message: types.Message, state: FSMContext):
    await state.update_data(stadium=message.text)
    await message.answer("VIP наше или ваше?")
    await state.set_state(FindTourState.vip)

@dp.message(FindTourState.vip)
async def process_ft_vip(message: types.Message, state: FSMContext):
    data = await state.get_data()
    post_text = f"🏆 **Поиск товы (товарищеский матч)**\n\nКлуб: {data.get('club')}\nВремя: {data.get('time')}\nСтадион: {data.get('stadium')}\nVIP: {message.text}"
    await send_application(message, post_text)
    await state.clear()

# --- ПОИСК ИГРОКОВ ---
@dp.callback_query(F.data == "find_players")
async def start_find_players(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("Напишите ваше требование:")
    await state.set_state(FindPlayersState.requirement)
    await callback.answer()

@dp.message(FindPlayersState.requirement)
async def process_fp_req(message: types.Message, state: FSMContext):
    post_text = f"🔎 **Поиск игроков**\n\nТребование: {message.text}"
    await send_application(message, post_text)
    await state.clear()

# --- КУПИТЬ РЕКЛАМУ ---
@dp.callback_query(F.data == "buy_ad")
async def process_buy_ad(callback: types.CallbackQuery):
    await callback.message.answer(
        f"✅ **Купить рекламу**\n\n"
        f"Чтобы купить рекламу, напишите модераторам в ЛС и переведите звёзды:\n\n"
        f"📩 {MODERATORS}",
        parse_mode="Markdown"
    )
    await callback.answer()

# --- ТЕХПОДДЕРЖКА ---
@dp.callback_query(F.data == "support")
async def process_support(callback: types.CallbackQuery):
    await callback.message.answer(
        f"🛠️ **Техподдержка**\n\n"
        f"По всем вопросам обращайтесь к модераторам:\n\n"
        f"📩 {MODERATORS}",
        parse_mode="Markdown"
    )
    await callback.answer()

# --- ЖАЛОБЫ ---
@dp.callback_query(F.data == "complaints")
async def process_complaints(callback: types.CallbackQuery):
    await callback.message.answer(
        f"📢 **Жалобы**\n\n"
        f"По жалобам обращайтесь к модераторам:\n\n"
        f"📩 {MODERATORS}",
        parse_mode="Markdown"
    )
    await callback.answer()

@dp.callback_query()
async def process_other(callback: types.CallbackQuery):
    await callback.message.answer("Этот раздел находится в разработке. Скоро добавим!")
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

    logging.info("Запуск бота...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
