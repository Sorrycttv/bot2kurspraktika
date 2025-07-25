import asyncio
import logging

#import sqlite3

from aiogram import Bot, Dispatcher

from bot import TOKEN 
from utils import initialize_database, check_tables
from handlers.handlers import  router


async def main():
    initialize_database()
    check_tables()
    bot = Bot(token=TOKEN)
    dp = Dispatcher()
    dp.include_routers(router)
    await dp.start_polling(bot)

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO) 
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print('Exit')