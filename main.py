import asyncio
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiohttp import web # Добавляем библиотеку для веб-сервера
import os

# Вставь сюда свой токен от BotFather (но лучше вынести его в переменные окружения, см. Шаг 3)
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

logging.basicConfig(level=logging.INFO)
bot = Bot(token=TOKEN)
dp = Dispatcher()

# --- Функция для простого веб-сервера (нужна для Koyeb) ---
async def handle(request):
    return web.Response(text="Bot is running")

# --- СОСТОЯНИЯ (FSM) ---
class ChangeNickState(StatesGroup):
    old_nick = State()
    new_nick = State()

# --- МЕНЮ ---
def get_main_menu():
    buttons = [
        [InlineKeyboardButton(text="✅ Купить рекламу", callback_data="buy_ad"),
         InlineKeyboardButton(text="🛑 Зеркало", callback_data="mirror")],
        [InlineKeyboardButton(text="👤 Свободный агент", callback_data="free_agent"),
         InlineKeyboardButton(text="⚽ Переход в клуб", callback_data="transfer_club")],
        [InlineKeyboardButton(text="🔄 Смена никнейма", callback_data="change_nick"),
         InlineKeyboardButton(text="🔄 Смена позиции", callback_data="change_pos")],
        [InlineKeyboardButton(text="🏁 Завершение карьеры", callback_data="end_career"),
         InlineKeyboardButton(text="❤️ Возвращение карьеры", callback_data="return_career")],
        [InlineKeyboardButton(text="⏸️ Приост. карьеры", callback_data="pause_career"),
         InlineKeyboardButton(text="🏆 Поиск товы", callback_data="find_tour")],
        [InlineKeyboardButton(text="🔎 Поиск игроков", callback_data="find_players"),
         InlineKeyboardButton(text="🛠️ Техподдержка", callback_data="support")],
        [InlineKeyboardButton(text="📢 Жалобы", callback_data="complaints")],
        [InlineKeyboardButton(text="🛡️ Состав ТММ", callback_data="tmm_staff")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# --- СТАРТ ---
@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    await message.answer("Выбери категорию:", reply_markup=get_main_menu())

# --- ОБРАБОТКА КНОПОК (заглушки) ---
@dp.callback_query(F.data == "buy_ad")
async def process_buy_ad(callback: types.CallbackQuery):
    await callback.message.answer("Чтобы купить рекламу, напишите нам в ЛС и отправьте звезды.")
    await callback.answer()

@dp.callback_query(F.data == "mirror")
async def process_mirror(callback: types.CallbackQuery):
    await callback.message.answer("Зеркало временно недоступно.")
    await callback.answer()

# --- СМЕНА НИКНЕЙМА (Логика) ---
@dp.callback_query(F.data == "change_nick")
async def start_change_nick(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("Напишите ваш текущий никнейм:")
    await state.set_state(ChangeNickState.old_nick)
    await callback.answer()

@dp.message(ChangeNickState.old_nick)
async def process_old_nick(message: types.Message, state: FSMContext):
    await state.update_data(old_nick=message.text)
    await message.answer("Какой никнейм хотите сделать?")
    await state.set_state(ChangeNickState.new_nick)

@dp.message(ChangeNickState.new_nick)
async def process_new_nick(message: types.Message, state: FSMContext):
    data = await state.get_data()
    old_nick = data.get("old_nick")
    new_nick = message.text
    
    post_text = f"🔄 **Смена никнейма**\n\nСтарый ник: {old_nick}\nНовый ник: {new_nick}"
    
    await message.answer(f"✅ Твоя заявка опубликована!\n\n{post_text}", parse_mode="Markdown")
    await state.clear()

# --- ЗАПУСК ---
async def main():
    # Запускаем веб-сервер для Koyeb
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT", 8080)) # Koyeb сам сообщит нам порт
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    
    # Запускаем бота
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
