from aiogram.filters import CommandStart, Command, BaseFilter
from aiogram.types import Message
from aiogram import F, Bot, Router, types
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from utils import *
import logging
from request import *
from request.request_admin import *
from request.nlp import *
from aiogram.types import reply_keyboard_markup, keyboard_button
import keyboards.keyboards as kb
from datetime import datetime
from aiogram import types
import nltk
from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords
import random

nlp_processor = NLPProcessor()
processed_messages = {}


# Настройка логгирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = Router()
tarif = Router()


class routerreg(StatesGroup):
    routername = State()
    routercost = State()
    routermesh = State()
    routertariff = State()
    routerg5 = State()
    routerports = State()


class TariffForm(StatesGroup):
    tarif_name = State()
    stoimost_tarif = State()
    stoimost_6month = State()
    stoimost_12month = State()
    akciya = State()


#запрос /start
@router.message(Command("start"))  # Обработчик команды /start
async def start_command(message: Message):
    processed_messages[message.message_id] = True

    user_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name or ""
    last_name = message.from_user.last_name or ""
    fio = f"{first_name} {last_name}".strip()
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Проверяем, есть ли пользователь в базе
    cursor.execute('SELECT admin_status FROM users_table WHERE user_id = ?', (user_id,))
    user_data = cursor.fetchone()
    
    if user_data:
        if user_data[0] == 1:
            await message.answer('Привет, админ!', reply_markup=kb.main_kb)
        else:
            await message.answer('Привет, пользователь!', reply_markup=kb.main_kb)
    else:
        try:
            cursor.execute('''
                INSERT INTO users_table (user_id, username, fio, admin_status)
                VALUES (?, ?, ?, 0)
            ''', (user_id, username, fio))
            conn.commit()
            await message.answer('Добро пожаловать! Вы были добавлены в систему.', reply_markup=kb.main_kb)
        except Exception as e:
            await message.answer(f'Ошибка при добавлении в базу: {str(e)}')
        finally:
            conn.close()
            
# Функция для проверки прав администратора
def is_user_admin(user_id: int) -> bool:
    with sqlite3.connect('user_data.db') as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT admin_status FROM users_table WHERE user_id=?", (user_id,))
        result = cursor.fetchone()
        return result[0] if result else False

@router.message(F.text == 'Оборудование в продаже')
async def show_routers(message: types.Message):
    processed_messages[message.message_id] = True
    user_id = message.from_user.id
    
    # Проверяем права пользователя
    is_admin = is_user_admin(user_id)
    
    routers = get_all_routers()
    if not routers:
        reply_text = "Роутеры не найдены."
        if is_admin:
            reply_text += " Вы можете добавить новый роутер."
            await message.answer(reply_text, reply_markup=kb.change_routers_kb)
        else:
            await message.answer(reply_text, reply_markup=kb.main_kb)
        return
    
    for router in routers:
        formatted_message = format_router_for_display(router)
        if is_admin:
            await message.answer(formatted_message, reply_markup=kb.change_routers_kb)
        else:
            await message.answer(formatted_message) # Отправляем сообщение  reply_markup=kb.change_routers_kb выводклавы редактирования роутеры

#реализация "обратной связи" между юзером и админом
class FeedbackStates(StatesGroup):
    waiting_for_feedback = State()



async def get_admins_ids():
    
    """Получаем список ID администраторов из базы"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM users_table WHERE admin_status = 1")
        admins = [row[0] for row in cursor.fetchall()]
        return admins if admins else [1349520375]  # Возвращаем ваш ID как fallback
    except Exception as e:
        logger.error(f"Error getting admins list: {e}")
        return 
    finally:
        conn.close()

async def is_admin(user_id: int) -> bool:
    """Проверяем, является ли пользователь администратором"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT admin_status FROM users_table WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        return result and result[0] == 1
    except Exception as e:
        logger.error(f"Error checking admin status: {e}")
        return False
    finally:
        conn.close()

@router.message(F.text == 'Обратная связь')
async def start_feedback(message: types.Message, state: FSMContext):
    processed_messages[message.message_id] = True

    await message.answer(
        "📝 Напишите ваше сообщение для администратора:",
        reply_markup=types.ReplyKeyboardRemove()
    )
    await state.set_state(FeedbackStates.waiting_for_feedback)

@router.message(FeedbackStates.waiting_for_feedback)
async def process_feedback(message: types.Message, state: FSMContext, bot: Bot):
    user = message.from_user
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO feedback_table 
            (user_fb_id, username_fb, message)
            VALUES (?, ?, ?)
        ''', (user.id, user.username, message.text))
        conn.commit()

        # Получаем список администраторов
        admins = await get_admins_ids()
        success_sent = False
        
        for admin_id in admins:
            try:
                await bot.send_message(
                    admin_id,
                    f"🚀 Новый фидбек!\n"
                    f"От: @{user.username or 'нет username'} (ID: {user.id})\n"
                    f"Текст: {message.text}\n\n"
                    f"Ответить: /reply {user.id} [текст]"
                )
                success_sent = True
            except Exception as e:
                logger.error(f"Can't send message to admin {admin_id}: {e}")
                continue
        
        if success_sent:
            await message.answer("✅ Ваше сообщение отправлено администратору!",reply_markup=kb.main_kb)
        else:
            await message.answer("✅ Ваше сообщение сохранено. Администратор получит его позже.",reply_markup=kb.main_kb)

    except Exception as e:
        print(f"Feedback processing error: {e}")
        #await message.answer("❌ Произошла ошибка при обработке вашего сообщения")
    finally:
        if 'conn' in locals():
            conn.close()
        await state.clear()

@router.message(Command("reply"))
async def admin_reply(message: types.Message, bot: Bot):
    processed_messages[message.message_id] = True

    if not await is_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав для этой команды")
        return

    try:
        parts = message.text.split(maxsplit=2)
        if len(parts) < 3:
            raise ValueError("Недостаточно аргументов")
            
        try:
            user_id = int(parts[1])
        except ValueError:
            raise ValueError("ID пользователя должен быть числом")

        reply_text = parts[2].strip()
        if not reply_text:
            raise ValueError("Текст ответа не может быть пустым")

        # Отправляем ответ пользователю
        try:
            await bot.send_message(
                user_id,
                f"📨 Ответ от администратора:\n\n{reply_text}"
            )
            send_success = True
        except Exception as e:
            logger.error(f"Can't send to user {user_id}: {e}")
            send_success = False

        # Обновляем статус в базе
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE feedback_table 
            SET status = ?,
                admin_id = ?,
                reply_message = ?
            WHERE user_fb_id = ? AND status = 'new'
        ''', ('replied' if send_success else 'failed', 
              message.from_user.id, 
              reply_text, 
              user_id))
        
        conn.commit()
        
        if cursor.rowcount == 0:
            await message.answer(f"⚠ Нет неотвеченных сообщений от пользователя {user_id}")
        else:
            status_msg = "✅ Ответ отправлен" if send_success else "⚠ Ответ сохранен, но не отправлен"
            await message.answer(f"{status_msg} пользователю ID: {user_id}")
            
    except ValueError as e:
        await message.answer(f"❌ Ошибка: {str(e)}\nФормат: /reply USER_ID текст")
    except Exception as e:
        logger.error(f"Admin reply error: {e}")
        await message.answer("❌ Произошла ошибка при обработке команды")
    finally:
        if 'conn' in locals():
            conn.close()

@router.message(Command("feedback_list"))
async def list_feedback(message: types.Message):
    processed_messages[message.message_id] = True

    if not await is_admin(message.from_user.id):
        return

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id_fb, user_fb_id, username_fb, message, created_at 
            FROM feedback_table 
            WHERE status = 'new'
            ORDER BY created_at DESC
            LIMIT 50
        ''')
        
        feedbacks = cursor.fetchall()
        
        if not feedbacks:
            await message.answer("📭 Нет новых сообщений")
            return
            
        for fb in feedbacks:
            fb_id, user_id, username, msg, created_at = fb
            
            fb_text = (
                f"📩 ID: {fb_id}\n"
                f"👤 Пользователь: @{username or 'нет username'} (ID: {user_id})\n"
                f"📅 Дата: {created_at}\n"
                f"✉ Сообщение: {msg[:200]}{'...' if len(msg) > 200 else ''}\n\n"
                f"Ответить: /reply {user_id} ваш_текст"
            )
            await message.answer(reply_markup=kb.main_kb)
            try:
                await message.answer(fb_text)
            except Exception as e:
                logger.error(f"Can't send feedback message: {e}")
                continue
                
    except Exception as e:
        logger.error(f"Feedback list error: {e}")
        await message.answer("❌ Ошибка при получении списка сообщений")
    finally:
        conn.close()
    

#запрос кнопка "кто ты? Бот для обратной связи" - кнопка убрана, команда 'кто ты?' осталась
@router.message(F.text == 'Кто ты?')
async def who_are_you(message : Message):
    processed_messages[message.message_id] = True

    await message.answer('я бот для обратной связи')

#запрос кнопка "Актуальные тарифные планы"
@router.message(F.text == 'Актуальные тарифные планы')
async def show_tariffs(message: types.Message):
    processed_messages[message.message_id] = True
    user_id = message.from_user.id
    
    # Проверяем права пользователя
    is_admin = is_user_admin(user_id)
    #user_id = message.from_user.id
    tarifs = get_all_tariffs()
    if not tarifs:
        reply_text = "Роутеры не найдены."
        if is_admin:
            reply_text += " Вы можете добавить новый роутер."
            await message.answer(reply_text, reply_markup=kb.change_tarif_kb)
        else:
            await message.answer(reply_text, reply_markup=kb.main_kb)
        return
    
    for tarifs in tarifs:
        formatted_message = format_tarifs_for_display(tarifs)
        if is_admin:
            await message.answer(formatted_message, reply_markup=kb.change_tarif_kb)
        else:
            await message.answer(formatted_message) # Отправляем сообщение  reply_markup=kb.change_routers_kb выводклавы редактирования роутеры


@router.message(F.text == 'Назад')
async def main_menu(message : Message):
    processed_messages[message.message_id] = True
    await message.answer('Возвращаю вас в главное меню:',reply_markup=kb.main_kb)


#FSM начало роутерс

@router.message(F.text == 'Добавление роутера')
async def add_router1(message: Message, state: FSMContext):
    

    if not admin_authorized(message.from_user.id):
        await message.answer("❌ Эта команда только для администраторов")
        return
    processed_messages[message.message_id] = True
    await state.set_state(routerreg.routername)
    await message.answer('Введите название модели')

@router.message(routerreg.routername)
async def add_router2(message: Message, state: FSMContext):
    processed_messages[message.message_id] = True

    await state.update_data(routername=message.text)
    await state.set_state(routerreg.routercost)
    await message.answer('Введите стоимость роутера (только цифрой)')

@router.message(routerreg.routercost)
async def add_router3(message: Message, state: FSMContext):
    #processed_messages[message.message_id] = True

    try:
        cost = float(message.text)
        await state.update_data(routercost=cost)
        await state.set_state(routerreg.routermesh)
        await message.answer('Поддерживает роутер Mesh? (Да/Нет)')
    except ValueError:
        await message.answer('❌ Введите число для стоимости!')
    processed_messages[message.message_id] = True
@router.message(routerreg.routermesh)
async def add_router4(message: Message, state: FSMContext):
    

    if message.text.lower() not in ['да', 'нет']:
        await message.answer('❌ Ответьте "Да" или "Нет"')
        return
    processed_messages[message.message_id] = True    
    await state.update_data(routermesh=message.text.lower() == 'да')
    await state.set_state(routerreg.routertariff)
    await message.answer('Поддерживает ли роутер тарифы >100 мб? (Да/Нет)')

@router.message(routerreg.routertariff)
async def add_router5(message: Message, state: FSMContext):
    

    if message.text.lower() not in ['да', 'нет']:
        await message.answer('❌ Ответьте "Да" или "Нет"')
        return
    processed_messages[message.message_id] = True    
    await state.update_data(routertariff=message.text.lower() == 'да')
    await state.set_state(routerreg.routerg5)
    await message.answer('Имеет ли роутер диапазон 5G? (Да/Нет)')

@router.message(routerreg.routerg5)
async def add_router6(message: Message, state: FSMContext):
    

    if message.text.lower() not in ['да', 'нет']:
        await message.answer('❌ Ответьте "Да" или "Нет"')
        return
    processed_messages[message.message_id] = True    
    await state.update_data(routerg5=message.text.lower() == 'да')
    await state.set_state(routerreg.routerports)
    await message.answer('Введите количество портов (число)')

@router.message(routerreg.routerports)
async def add_router7(message: Message, state: FSMContext):
    processed_messages[message.message_id] = True

    try:
        ports = int(message.text)
        await state.update_data(routerports=ports)
        data = await state.get_data()
        conn = sqlite3.connect('user_data.db')
        cursor = conn.cursor()
        cursor.execute('''
    INSERT INTO routers_table (model_id, model_name, model_cost, mesh, tariff_1000, g5_diap, number_ports)
    SELECT COALESCE(MAX(model_id), 0) + 1, ?, ?, ?, ?, ?, ? 
    FROM routers_table
''', (
            data['routername'],
            data['routercost'],
            data['routermesh'],
            data['routertariff'],
            data['routerg5'],
            data['routerports'],
))

        
        conn.commit()
        conn.close()
        
        await message.answer(
            f"✅ Роутер  успешно добавлен!\n"
            f"Модель: {data['routername']}\n"
            f"Цена: {data['routercost']} руб.\n"
            f"Mesh: {'Да' if data['routermesh'] else 'Нет'}\n"
            f"Тариф 1000 Мбит/с: {'Да' if data['routertariff'] else 'Нет'}\n"
            f"5 ГГц: {'Да' if data['routerg5'] else 'Нет'}\n"
            f"Портов: {data['routerports']}\n"
            f"_________________________________"
        )
        await state.clear()
        
    except ValueError:
        await message.answer('❌ Введите целое число для количества портов!')
    except Exception as e:
        await message.answer(f'❌ Ошибка базы данных: {str(e)}')
        await state.clear()

#FSM для изменения роутера
class EditRouter(StatesGroup):
    waiting_for_router_id = State()
    routername = State()
    routercost = State()
    routermesh = State()
    routertariff = State()
    routerg5 = State()
    routerports = State()
#поиск по id 
@router.message(F.text == 'Изменение роутера')
async def edit_router_start(message: Message, state: FSMContext):
    

    if not admin_authorized(message.from_user.id):
        await message.answer("❌ Эта команда только для администраторов")
        return
    processed_messages[message.message_id] = True
    routers = get_all_routers()
    if not routers:
        await message.answer("Нет доступных роутеров для изменения")
        return
    
    for router in routers:
        await message.answer(format_router_for_display(router))
    
    await message.answer("Введите ID роутера для изменения:")
    await state.set_state(EditRouter.waiting_for_router_id)

#после id -> изменение нэйма 
@router.message(EditRouter.waiting_for_router_id)
async def edit_router_id(message: Message, state: FSMContext):
    processed_messages[message.message_id] = True

    try:
        router_id = int(message.text)
        router = get_router_by_id(router_id)
        if not router:
            await message.answer(f"Роутер с ID {router_id} не найден")
            await state.clear()
            return
        
        await state.update_data(router_id=router_id, routername=router[1], routercost=router[2],
                                routermesh=router[3], routertariff=router[4], routerg5=router[5], routerports=router[6])
        await state.set_state(EditRouter.routername)
        await message.answer(f"Текущее название: {router[1]}\n"
                             "Введите новое название модели\n"
                             "(или 'пропустить' для сохранения текущего):")
    except ValueError:
        await message.answer("❌ Введите корректный ID (число)")
        return

#изменение стоимости <- изменения нэйма 
@router.message(EditRouter.routername)
async def edit_router_name(message: Message, state: FSMContext):
    processed_messages[message.message_id] = True

    if message.text.lower() != 'пропустить':
        await state.update_data(routername=message.text)
    await state.set_state(EditRouter.routercost)
    data = await state.get_data()
    await message.answer(f"Текущая стоимость: {data['routercost']}\n"
                         f"Введите новую стоимость роутера (только цифрой, или 'пропустить'):")

@router.message(EditRouter.routercost)
async def edit_router_cost(message: Message, state: FSMContext):
    processed_messages[message.message_id] = True

    if message.text.lower() != 'пропустить':
        try:
            cost = float(message.text)
            await state.update_data(routercost=cost)
        except ValueError:
            await message.answer('❌ Введите число для стоимости!')
            return
    await state.set_state(EditRouter.routermesh)
    data = await state.get_data()
    await message.answer(f"Текущая поддержка Mesh: {'Да' if data['routermesh'] else 'Нет'}\n"
                         f"Поддерживает роутер Mesh? (Да/Нет/пропустить):")

@router.message(EditRouter.routermesh)
async def edit_router_mesh(message: Message, state: FSMContext):
    processed_messages[message.message_id] = True

    if message.text.lower() not in ['да', 'нет', 'пропустить']:
        await message.answer('❌ Ответьте "Да", "Нет" или "пропустить"')
        return
    if message.text.lower() != 'пропустить':
        await state.update_data(routermesh=message.text.lower() == 'да')
    await state.set_state(EditRouter.routertariff)
    data = await state.get_data()
    await message.answer(f"Текущая поддержка тарифа >100 Мбит/с: {'Да' if data['routertariff'] else 'Нет'}\nПоддерживает ли роутер тарифы >100 Мбит/с? (Да/Нет/пропустить):")

@router.message(EditRouter.routertariff)
async def edit_router_tariff(message: Message, state: FSMContext):
    processed_messages[message.message_id] = True

    if message.text.lower() not in ['да', 'нет', 'пропустить']:
        await message.answer('❌ Ответьте "Да", "Нет" или "пропустить"')
        return
    if message.text.lower() != 'пропустить':
        await state.update_data(routertariff=message.text.lower() == 'да')
    await state.set_state(EditRouter.routerg5)
    data = await state.get_data()
    await message.answer(f"Текущий диапазон 5G: {'Да' if data['routerg5'] else 'Нет'}\nИмеет ли роутер диапазон 5G? (Да/Нет/пропустить):")

@router.message(EditRouter.routerg5)
async def edit_router_g5(message: Message, state: FSMContext):
    processed_messages[message.message_id] = True

    if message.text.lower() not in ['да', 'нет', 'пропустить']:
        await message.answer('❌ Ответьте "Да", "Нет" или "пропустить"')
        return
    if message.text.lower() != 'пропустить':
        await state.update_data(routerg5=message.text.lower() == 'да')
    await state.set_state(EditRouter.routerports)
    data = await state.get_data()
    await message.answer(f"Текущее количество портов: {data['routerports']}\nВведите новое количество портов (число, или 'пропустить'):")

@router.message(EditRouter.routerports)
async def edit_router_ports(message: Message, state: FSMContext):
    processed_messages[message.message_id] = True

    if message.text.lower() != 'пропустить':
        try:
            ports = int(message.text)
            await state.update_data(routerports=ports)
        except ValueError:
            await message.answer('❌ Введите целое число для количества портов!')
            return
    
    data = await state.get_data()
    try:
        update_router_in_db(data['router_id'], data)
        await message.answer(
           # f"✅ Роутер с ID {data['model_id']} успешно обновлён!\n"
            f"Модель: {data['routername']}\n"
            f"Цена: {data['routercost']} руб.\n"
            f"Mesh: {'Да' if data['routermesh'] else 'Нет'}\n"
            f"Тариф 1000 Мбит/с: {'Да' if data['routertariff'] else 'Нет'}\n"
            f"5 ГГц: {'Да' if data['routerg5'] else 'Нет'}\n"
            f"Портов: {data['routerports']}\n"
            f"_________________________________",
            reply_markup=kb.main_kb
        )
    except Exception as e:
        await message.answer(f'❌ Ошибка базы данных: {str(e)}')
    finally:
        await state.clear()

def update_router_in_db(router_id, data):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE routers_table
        SET model_name = ?, model_cost = ?, mesh = ?, tariff_1000 = ?, g5_diap = ?, number_ports = ?
        WHERE model_id = ?
    ''', (
        data['routername'],
        data['routercost'],
        data['routermesh'],
        data['routertariff'],
        data['routerg5'],
        data['routerports'],
        router_id
    ))
    conn.commit()
    conn.close()
    return True   

#FSM ДЛЯ УДАЛЕНИЯ РОУТЕРА
class DeleteRouter(StatesGroup):
    waiting_for_router_id = State()
    confirmation = State()

@router.message(F.text == 'Удаление роутера')
async def delete_router_start(message: Message, state: FSMContext):
  

    if not admin_authorized(message.from_user.id):
        await message.answer("❌ Эта команда только для администраторов")
        return
    # Показываем все тарифы для наглядности
    processed_messages[message.message_id] = True
    routers= get_all_routers()
    if not routers:
        await message.answer("Нет доступных роутеров для удаления")
        return
    
    for router in routers:
        await message.answer(format_router_for_display(router))
    
    await message.answer("Введите ID тарифа для удаления:")
    await state.set_state(DeleteRouter.waiting_for_router_id)

@router.message(DeleteRouter.waiting_for_router_id)
async def delete_router_by_id(message: Message, state: FSMContext):
    processed_messages[message.message_id] = True

    try:
        router_id = int(message.text)
        if delete_router_from_db(router_id):
            await message.answer(f"Роутер с ID {router_id} успешно удалён")
        else:
            await message.answer(f"Роутер с ID {router_id} не найден")
    except ValueError:
        await message.answer("❌ Введите корректный ID (число)")
    finally:
        await state.clear()



@router.message(DeleteRouter.waiting_for_router_id)
async def confirm_deletion(message: Message, state: FSMContext):
    processed_messages[message.message_id] = True

    router_id = int(message.text)
    await state.update_data(router_id=router_id)
    
    # Показываем информацию о роутере
    router = get_router_by_id(router_id)
    await message.answer(
        f"Вы действительно хотите удалить этот тариф?\n"
        f"{format_router_for_display(router)}\n"
        "Подтвердите (Да/Нет):",
        reply_markup=reply_keyboard_markup(
            keyboard=[
                [keyboard_button(text="Да"), keyboard_button(text="Нет")]
            ],
            resize_keyboard=True
        )
    )
    await state.set_state(DeleteRouter.confirmation)



#добавление тарифа FSM

@router.message(F.text == 'Добавление тарифа')
async def addtariff1(message:Message ,state:FSMContext):
    

    if not admin_authorized(message.from_user.id):
        await message.answer("❌ Эта команда только для администраторов")
        return
    processed_messages[message.message_id] = True
    await state.set_state(TariffForm.tarif_name)
    await message.answer('Введите название тарифа')
#название тарифа переход на стоимость

@router.message(TariffForm.tarif_name)
async def add_tariff2(message:Message, state:FSMContext):
    processed_messages[message.message_id] = True

    await state.update_data(tarif_name=message.text)
    await state.set_state(TariffForm.stoimost_tarif)
    await message.answer('Введите стоимость тарифа (ежемесячно)')
#стоимость тарифа перех=од на скидку 6 месчяцев

@router.message(TariffForm.stoimost_tarif)
async def add_tariff3(message:Message, state:FSMContext):
    processed_messages[message.message_id] = True

    try:
        cost = float(message.text)
        await state.update_data(stoimost_tarif=cost)
        await state.set_state(TariffForm.stoimost_6month)
        await message.answer('Введите стоимость на 6 месяцев (если есть скидка)')
    except ValueError:
        await message.answer('❌ Введите ЧИСЛО для стоимости!')

#скидка 6 месяцев переход на скидку 12 месяцев
@router.message(TariffForm.stoimost_6month)
async def add_tariff4(message:Message, state:FSMContext):
    processed_messages[message.message_id] = True

    try:
        cost = float(message.text)  if message.text.lower() != 'нет' else None
        await state.update_data(stoimost_6month=cost)
        await state.set_state(TariffForm.stoimost_12month)
        await message.answer('Введите стоимость 12 месяцев(Если есть скидка)')
    except ValueError:
        await message.answer('Введите число или "нет"!')

@router.message(TariffForm.stoimost_12month)
async def add_tariff5(message:Message, state:FSMContext):
    processed_messages[message.message_id] = True

    try:
        cost = float(message.text) if message.text.lower() != 'нет' else None
        await state.update_data(stoimost_12month=cost)
        await state.set_state(TariffForm.akciya)
        await message.answer ('Тариф по акции?(Ответьте Да/Нет)')
    except ValueError:
        await message.answer('❌ Введите число или "нет"!')

@router.message(TariffForm.akciya)
async def add_tariff6(message:Message, state: FSMContext):
    

    if message.text.lower() not in ['да','нет']:
        await message.answer('❌ Ответьте "Да" или "Нет"')
        return
    processed_messages[message.message_id] = True
    await state.update_data(akciya=message.text.lower() == 'да')
    data = await state.get_data()
    conn = sqlite3.connect('user_data.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO tariffs_table (id_tarif, tarif_name, stoimost_tarif, stoimost_6month, stoimost_12month, akciya)
        SELECT COALESCE(MAX(id_tarif), 0) + 1, ?, ?, ?, ?, ?
        FROM tariffs_table
    ''', 
    (
        data['tarif_name'],
        data['stoimost_tarif'],
        data['stoimost_6month'],
        data['stoimost_12month'],
        data['akciya'],
    ))
    conn.commit()
    conn.close()
   
    await message.answer(
        f"✅ Тариф успешно добавлен!\n"
        f"Название: {data['tarif_name']}\n"
        f"Ежемесячная стоимость: {data['stoimost_tarif']} руб.\n"
        f"На 6 месяцев: {data['stoimost_6month'] or 'нет'}\n"
        f"На 12 месяцев: {data['stoimost_12month'] or 'нет'}\n"
        f"Акционный: {'Да' if data['akciya'] else 'Нет'}\n"
        "_____________________________________"
    )
    await state.clear()


#FSM для изменения тарифа
class EditTariff(StatesGroup):
    waiting_for_tariff_id = State()
    tariff_name = State()
    tarifcost = State()
    cost_6month = State()
    cost_12month = State()
    editakciya = State()

#Изменение тарифа
@router.message(F.text == 'Изменение тарифа')
async def edit_tarif(message: Message, state: FSMContext):
    

    if not admin_authorized(message.from_user.id):
        await message.answer("❌ Эта команда только для администраторов")
        return
    processed_messages[message.message_id] = True
    tariffs = get_all_tariffs()
    if not tariffs:
        await message.answer("Нет доступных тарифов для изменения")
        return
    
    for tarif in tariffs:
        await message.answer(format_tarifs_for_display(tarif))

    await message.answer("Введите ID тарифа для изменения")
    await state.set_state(EditTariff.waiting_for_tariff_id)

#поиск по ID, изменение name    
@router.message(EditTariff.waiting_for_tariff_id)
async def edit_tarif_id(message:Message, state:FSMContext):
    processed_messages[message.message_id] = True

    try:
        tariff_id = int(message.text)
        tarif = get_tarifs_by_id(tariff_id)
        if not tarif:
            await message.answer(f"Тариф с таким ID {tariff_id} не найден")
            await state.clear()
        
        await state.update_data(tariff_id=tariff_id, tarifname=tarif[1],tarifcost=tarif[2],
                                tarif6month=tarif[3], tarif12months=tarif[4], tarifakciya=tarif[5])
        await state.set_state(EditTariff.tariff_name)
        await message.answer(f"Текущее название: {tarif[1]}\n"
                             f"Введите новое название модели \n"
                             f"(или 'пропустить' для сохранения текущего):")
    except ValueError:
        await message.answer("❌ Введите корректный ID (число)")
        return

#Изменение стоимости   
@router.message(EditTariff.tariff_name)
async def edit_tarif_name(message:Message, state: FSMContext):
    

    if message.text.lower() != 'пропустить':
        await state.update_data(tariff_name=message.text)
    processed_messages[message.message_id] = True
    await state.set_state(EditTariff.tarifcost)
    data = await state.get_data()
    await message.answer(f"Текущая стоимость тарифа: {data['tarifcost']} руб.\n"
                         f"Введите новую стоимость тарифа\n"
                         f"(только цифрой, или 'пропустить'):")

#Изменение стоимости за 6 месяцев?
@router.message(EditTariff.tarifcost)
async def edit_tarif_cost(message:Message, state: FSMContext):
    processed_messages[message.message_id] = True

    if message.text.lower() != 'пропустить':
        try:
            cost = float(message.text)
            await state.update_data(tarifcost=cost)
        except ValueError:
            await message.answer('❌ Введите число для стоимости!')
            return
    await state.set_state(EditTariff.cost_6month)
    data = await state.get_data()
    await message.answer(f"Текущая стоимость 6 месяцев: {data['tarif6month']} руб.\n"
                         f"Введите новую стоимость тарифа\n"
                         f"(только цифрой, или 'пропустить'):")

#Изменение стоимости за 12 месяцев
@router.message(EditTariff.cost_6month)
async def edit_tarif_6month(message:Message, state: FSMContext):
    processed_messages[message.message_id] = True

    if message.text.lower() != 'пропустить':
        try:
            cost = float(message.text)
            await state.update_data(cost_6month=cost)
        except ValueError:
            await message.answer('❌ Введите число для стоимости!')
            return
    await state.set_state(EditTariff.cost_12month)
    data = await state.get_data()
    await message.answer(f"Текущая стоимость на 12 месяцев: {data["tarif12months"]} руб.\n"
                         f"Введите новуюстоимость тарифа\n"
                         f"(только цифрой, или 'пропустить'):")
    
@router.message(EditTariff.cost_12month)
async def edit_tarif_12_month(message:Message, state : FSMContext):
    processed_messages[message.message_id] = True

    if message.text.lower() != 'пропустить':
        try:
            cost = float(message.text)
            await state.update_data(cost_12month=cost)
        except ValueError:
            await message.answer('❌ Введите число для стоимости!')
            return
    await state.set_state(EditTariff.editakciya)
    data = await state.get_data()
    await message.answer(f"Тариф акционный: {'Да' if data['tarifakciya'] else 'Нет'}\n"
                         f"Тариф по акции? (Да/Нет/пропустить):")     

@router.message(EditTariff.editakciya)
async def edit_tarif_akciya(message:Message, state:FSMContext):
    processed_messages[message.message_id] = True

    if message.text.lower() not in ['да', 'нет', 'пропустить']:
        await message.answer('❌ Ответьте "Да", "Нет" или "пропустить"')
        return
    if message.text.lower() != 'пропустить':
        await state.update_data(editakciya=message.text.lower() == 'да')
    
    data = await state.get_data()
    try:
        update_tariff_in_db(data['tariff_id'], data)
        await message.answer(
        #    f"✅ Тариф с ID {data['tariff_id']} успешно обновлён!\n"
            f"Название: {data['tariff_name']}\n"
            f"Ежемесячная стоимость: {data['tarifcost']} руб.\n"
            f"На 6 месяцев: {data['cost_6month'] or 'нет'}\n"
            f"На 12 месяцев: {data['cost_12month'] or 'нет'}\n"
            f"Акционный: {'Да' if data['editakciya'] else 'Нет'}\n"
            f"_____________________________________",
            reply_markup=kb.main_kb
        )
    except Exception as e:
        await message.answer(f'❌ Ошибка базы данных: {str(e)}')
    finally:
        await state.clear()

def update_tariff_in_db(tariff_id, data):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE tariffs_table
        SET tarif_name = ?, stoimost_tarif = ?, stoimost_6month = ?, stoimost_12month = ?, akciya = ?
        WHERE id_tarif = ?
''',    ( data['tariff_name'],
        data['tarifcost'],
        data['cost_6month'],
        data['cost_12month'],
        data['editakciya'],
        tariff_id
    ))
    conn.commit()
    conn.close()
    return True      


#FSM ДЛЯ УДАЛЕНИЯ ТАРИФА

class DeleteTariff(StatesGroup):
    waiting_for_tariff_id = State()
    confirmation = State()

@router.message(F.text == 'Удаление тарифа')
async def delete_tariff_start(message: Message, state: FSMContext):
    

    if not admin_authorized(message.from_user.id):
        await message.answer("❌ Эта команда только для администраторов")
        return
    processed_messages[message.message_id] = True
    # Показываем все тарифы для наглядности
    tariffs = get_all_tariffs()
    if not tariffs:
        await message.answer("Нет доступных тарифов для удаления")
        return
    
    for tariff in tariffs:
        await message.answer(format_tarifs_for_display(tariff))
    
    await message.answer("Введите ID тарифа для удаления:")
    await state.set_state(DeleteTariff.waiting_for_tariff_id)

@router.message(DeleteTariff.waiting_for_tariff_id)
async def delete_tariff_by_id(message: Message, state: FSMContext):
    processed_messages[message.message_id] = True

    try:
        tariff_id = int(message.text)
        if delete_tariff_from_db(tariff_id):
            await message.answer(f"Тариф с ID {tariff_id} успешно удалён")
        else:
            await message.answer(f"Тариф с ID {tariff_id} не найден")
    except ValueError:
        await message.answer("❌ Введите корректный ID (число)")
    finally:
        await state.clear()



@router.message(DeleteTariff.waiting_for_tariff_id)
async def confirm_deletion(message: Message, state: FSMContext):
    processed_messages[message.message_id] = True

    tariff_id = int(message.text)
    await state.update_data(tariff_id=tariff_id)
    
    # Показываем информацию о тарифе
    tariff = get_tarifs_by_id(tariff_id)
    await message.answer(
        f"Вы действительно хотите удалить этот тариф?\n"
        f"{format_tarifs_for_display(tariff)}\n"
        "Подтвердите (Да/Нет):",
        reply_markup=reply_keyboard_markup(
            keyboard=[
                [keyboard_button(text="Да"), keyboard_button(text="Нет")]
            ],
            resize_keyboard=True
        )
    )
    await state.set_state(DeleteTariff.confirmation)




class NLPResponder:
    def __init__(self):
        self._init_nltk()
        self.stop_words = set(stopwords.words('russian'))
        self.knowledge_base = {
            "привет": ["Здравствуйте! Чем могу помочь?", "Привет! Как я могу вам помочь сегодня?"],
            "проблема": ["Опишите, пожалуйста, вашу проблему подробнее.", "Я постараюсь помочь с вашей проблемой. Что случилось?"],
            "проблемы": ["Опишите, пожалуйста, вашу проблему подробнее.", "Я постараюсь помочь с вашей проблемой. Что случилось?"],
            "интернет": ["Проверьте подключение кабеля и перезагрузите роутер.", "Попробуйте подключиться к другой сети для проверки."],
            "компьютер": ["Попробуйте перезагрузить компьютер.", "Проверьте, все ли кабели подключены правильно."],
            "спасибо": ["Пожалуйста! Обращайтесь, если будут еще вопросы.", "Рад был помочь! Хорошего дня!"],
            "default": ["Извините, я не совсем понял. Можете переформулировать?", "Не уверен, что понял вопрос. Уточните, пожалуйста."]
        }

    def _init_nltk(self):
        try:
            nltk.data.find('tokenizers/punkt')
            nltk.data.find('corpora/stopwords')
        except LookupError:
            nltk.download('punkt_tab')
            nltk.download('stopwords')

    def preprocess_text(self, text):
        tokens = word_tokenize(text.lower())
        return [token for token in tokens if token.isalpha() and token not in self.stop_words]

    async def get_response(self, text):
        tokens = self.preprocess_text(text)
        for word in tokens:
            if word in self.knowledge_base:
                return random.choice(self.knowledge_base[word])
        return random.choice(self.knowledge_base["default"])

nlp_responder = NLPResponder()

@router.message()
async def nlp_fallback_handler(message: types.Message):
    """
    Обработчик для сообщений, не пойманных другими обработчиками.
    Отвечает на вопросы из knowledge_base.
    """
    # Пропускаем команды (начинающиеся с /)
    if message.text.startswith('/'):
        return
        
    # Пропускаем если сообщение уже обработано другими обработчиками
    if not getattr(message, 'handled', False):
        response = nlp_processor.get_response(message.text)
        await message.answer(response)