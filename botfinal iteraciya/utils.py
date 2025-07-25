import sqlite3
#import types
#from aiogram.types import Message

# Путь к базе данных
DB_PATH = 'user_data.db'

# Глобальное соединение с базой данных и курсор 
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

def initialize_database():
    """
    Инициализация базы данных: создание таблиц, если они отсутствуют.
    """
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        # Таблица для пользователей
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS users_table (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            fio TEXT,
            admin_status BOOLEAN
        )
        ''')


        # Таблица с оборудованием
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS routers_table (
            model_id INTEGER PRIMARY KEY AUTOINCREMENT,
            model_name TEXT NOT NULL,
            model_cost NUMERIC NOT NULL,
            mesh BOOLEAN,
            tariff_1000 BOOLEAN,
            g5_diap BOOLEAN,
            number_ports NUMERIC
        )
        ''')


        # Таблица тарифов
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS tariffs_table (
	        id_tarif INTEGER PRIMARY KEY AUTOINCREMENT,
	        tarif_name INTEGER NOT NULL,
	        stoimost_tarif NUMERIC NOT NULL,
	        stoimost_6month INTEGER,
	        stoimost_12month INTEGER,
	        akciya BOOLEAN)
            ''')
        

        #обратная связь таблица
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS feedback_table(
            id_fb INTEGER PRIMARY KEY AUTOINCREMENT,
            user_fb_id INTEGER NOT NULL, 
            username_fb TEXT, 
            message TEXT NOT NULL, 
            status TEXT DEFAULT 'new',
            admin_id integer, 
            reply_message TEXT,
            created_at DATETIME,
            FOREIGN KEY (user_fb_id) REFERENCES users_table(user_id))
            ''')
        

        conn.commit()
        print("База данных инициализирована: таблицы созданы или уже существуют.")
    except sqlite3.Error as e:
        print(f"Ошибка при инициализации базы данных: {e}")
    finally:
        if conn:
            conn.close()

def id_authorized(user_id: int) -> bool:
    """
    Проверяет, авторизован ли пользователь по айди.
    """
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('''
        SELECT user_id FROM users_table WHERE user_id = ?
        ''', (user_id,))
        result = cursor.fetchone()
        print(f"Проверка авторизации для username={user_id}: {'авторизован' if result else 'не авторизован'}")
        return result is not None
    except sqlite3.Error as e:
        print(f"Ошибка при проверке авторизации пользователя: {e}")
        return False
    finally:
        if conn:
            conn.close()

def user_authorized(username: str) -> bool:
    """
    Проверяет, авторизован ли пользователь по юзернейм.
    """
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('''
        SELECT username FROM users_table WHERE username = ?
        ''', (username,))
        result = cursor.fetchone()
        print(f"Проверка авторизации для username={username}: {'авторизован' if result else 'не авторизован'}")
        return result is not None
    except sqlite3.Error as e:
        print(f"Ошибка при проверке авторизации пользователя: {e}")
        return False
    finally:
        if conn:
            conn.close()


def admin_authorized(user_id: int) -> bool:
    """
    Проверяет, авторизован ли пользователь и является ли он администратором.
    """
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT admin_status FROM users_table WHERE user_id = ?
        ''', (user_id,))
        result = cursor.fetchone()

        if result:
            admin_status = result[0]
            print(
                f"Проверка статуса администратора для user_id={user_id}: {'администратор' if admin_status else 'не администратор'}")
            return bool(admin_status)
        else:
            print(f"Пользователь с user_id={user_id} не найден.")
            return False
    except sqlite3.Error as e:
        print(f"Ошибка при проверке статуса администратора: {e}")
        return False
    finally:
        if conn:
            conn.close()

def check_tables():
    """
    Проверяет, существуют ли таблицы в базе данных.
    """
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()
    print(f"Таблицы в базе данных: {tables}")

def delete_tariff_from_db(tariff_id: int) -> bool:
    conn = sqlite3.connect('user_data.db')
    cursor = conn.cursor()
    
    # Проверяем существование тарифа
    cursor.execute("SELECT 1 FROM tariffs_table WHERE id_tarif = ?", (tariff_id,))
    if not cursor.fetchone():
        conn.close()
        return False
    
    # Удаляем тариф
    cursor.execute("DELETE FROM tariffs_table WHERE id_tarif = ?", (tariff_id,))
    conn.commit()
    conn.close()
    return True

def get_tarifs_by_id(tariff_id: int) -> tuple | None:
    try:
        conn = sqlite3.connect('user_data.db')
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM tariffs_table WHERE id_tarif = ?", (tariff_id,))
        tariff = cursor.fetchone()
        
        return tariff
        
    except sqlite3.Error as e:
        print(f"Ошибка при получении тарифа: {e}")
        return None
        
    finally:
        if conn:
            conn.close()


def delete_router_from_db(router_id: int) -> bool:
    conn = sqlite3.connect('user_data.db')
    cursor = conn.cursor()
    
    # Проверяем существование тарифа
    cursor.execute("SELECT 1 FROM routers_table WHERE model_id = ?", (router_id,))
    if not cursor.fetchone():
        conn.close()
        return False
    
    # Удаляем тариф
    cursor.execute("DELETE FROM routers_table WHERE model_id = ?", (router_id,))
    conn.commit()
    conn.close()
    return True


def get_router_by_id(router_id: int) -> tuple | None:
    try:
        conn = sqlite3.connect('user_data.db')
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM routers_table WHERE model_id = ?", (router_id,))
        router = cursor.fetchone()
        
        return router
        
    except sqlite3.Error as e:
        print(f"Ошибка при получении роутера: {e}")
        return None
        
    finally:
        if conn:
            conn.close()
