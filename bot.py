import asyncio
import sys
from aiogram import Bot, Dispatcher, F
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from config.settings import settings
from utils.logger import logger
from middlewares.throttling import ThrottlingMiddleware
from middlewares.logging_middleware import LoggingMiddleware
from states.user_states import UserStates

# Импорт роутеров
from routers import commands
from routers.handlers import facts_handlers, jokes_handlers, favorites_handlers

async def main():
    """Главная функция запуска бота"""
    
    # Проверяем наличие токена
    if not settings.BOT_TOKEN:
        logger.error("BOT_TOKEN не найден в переменных окружения!")
        sys.exit(1)
    
    # Создаем бот и диспетчер
    bot = Bot(token=settings.BOT_TOKEN)
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)
    
    # Подключаем middleware
    dp.message.middleware(LoggingMiddleware())
    dp.callback_query.middleware(LoggingMiddleware())
    dp.message.middleware(ThrottlingMiddleware())
    
    # Подключаем роутеры
    dp.include_router(commands.router)
    dp.include_router(facts_handlers.router)
    dp.include_router(jokes_handlers.router)
    dp.include_router(favorites_handlers.router)
    
    # Хендлер для FSM состояний (предсказания по имени)
    @dp.message(UserStates.waiting_for_name_prediction)
    async def handle_name_input(message: Message, state: FSMContext):
        """Обработка ввода имени для предсказания"""
        from routers.handlers.facts_handlers import handle_name_prediction
        
        # Получаем тип предсказания из состояния
        data = await state.get_data()
        prediction_type = data.get("prediction_type", "age")
        
        await handle_name_prediction(message, prediction_type)
        await state.clear()
    
    # Хендлер для текстовых сообщений (простые команды)
    @dp.message(F.text.startswith("/age"))
    async def age_prediction_command(message: Message, state: FSMContext):
        """Команда предсказания возраста"""
        await state.set_state(UserStates.waiting_for_name_prediction)
        await state.update_data(prediction_type="age")
        await message.answer("🎂 Введите имя для предсказания возраста:")
    
    @dp.message(F.text.startswith("/gender"))
    async def gender_prediction_command(message: Message, state: FSMContext):
        """Команда предсказания пола"""
        await state.set_state(UserStates.waiting_for_name_prediction)
        await state.update_data(prediction_type="gender")
        await message.answer("👫 Введите имя для предсказания пола:")
    
    # Обработка неизвестных команд
    @dp.message()
    async def unknown_message(message: Message):
        """Обработка неизвестных сообщений"""
        from keyboards.inline import get_main_menu
        
        await message.answer(
            "🤔 Я не понимаю эту команду.\n\n"
            "Используйте кнопки меню или команды:\n"
            "/help - справка\n"
            "/catfact - факт о котах\n"
            "/joke - шутка\n"
            "/randomfact - случайный факт",
            reply_markup=get_main_menu()
        )
    
    # Обработчик для кнопки "Еще раз"
    @dp.callback_query(F.data.in_(["catfact", "joke", "randomfact"]))
    async def repeat_content_callback(callback: CallbackQuery):
        """Обработка повторного запроса контента"""
        content_type = callback.data
        
        if content_type == "catfact":
            from routers.handlers.facts_handlers import handle_cat_fact
            await handle_cat_fact(callback)
        elif content_type == "joke":
            from routers.handlers.jokes_handlers import handle_joke
            await handle_joke(callback)
        elif content_type == "randomfact":
            from routers.handlers.facts_handlers import handle_random_fact
            await handle_random_fact(callback)
        
        await callback.answer()
    
    # Сохранение последнего контента для добавления в избранное
    def setup_content_saving():
        """Настройка сохранения контента для избранного"""
        from routers.handlers.favorites_handlers import save_last_content
        
        # Переопределяем хендлеры для сохранения контента
        original_cat_fact = facts_handlers.handle_cat_fact
        original_joke = jokes_handlers.handle_joke
        original_random_fact = facts_handlers.handle_random_fact
        
        async def cat_fact_with_save(message_or_callback):
            await original_cat_fact(message_or_callback)
            # Здесь можно добавить логику сохранения контента
        
        async def joke_with_save(message_or_callback):
            await original_joke(message_or_callback)
            # Здесь можно добавить логику сохранения контента
        
        async def random_fact_with_save(message_or_callback):
            await original_random_fact(message_or_callback)
            # Здесь можно добавить логику сохранения контента
        
        facts_handlers.handle_cat_fact = cat_fact_with_save
        jokes_handlers.handle_joke = joke_with_save
        facts_handlers.handle_random_fact = random_fact_with_save
    
    setup_content_saving()
    
    logger.info("🚀 Бот запускается...")
    
    try:
        # Удаляем webhook и запускаем polling
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"Ошибка при запуске бота: {e}")
    finally:
        await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
        sys.exit(1)