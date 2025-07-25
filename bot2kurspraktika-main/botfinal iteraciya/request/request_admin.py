import sqlite3

def get_all_routers():
    """Получение всех роутеров из базы данных"""
    conn = sqlite3.connect('user_data.db')
    cursor = conn.cursor()
    
    try:
        cursor.execute('SELECT * FROM routers_table')
        routers = cursor.fetchall()
        
        # Преобразуем в список словарей для удобства
        columns = [desc[0] for desc in cursor.description]
        result = [dict(zip(columns, row)) for row in routers]
        
        return result
    except Exception as e:
        print(f"Ошибка при получении данных: {e}")
        return []
    finally:
        conn.close()

#Функция для красивого отображения
def format_router_for_display(router):
    """Форматирование информации о роутере для вывода в Telegram"""
    return (
        f"ID: {router['model_id']}\n"
        f"Название: {router['model_name']}\n"
        f"Цена: {router['model_cost']} руб.\n"
        f"Mesh: {'Да' if router['mesh'] else 'Нет'}\n"
        f" 1000 Мбит/с: {'Да' if router['tariff_1000'] else 'Нет'}\n"
        f"5 ГГц: {'Да' if router['g5_diap'] else 'Нет'}\n"
        f"LAN: {router['number_ports']}\n"
        "-------------------------"
    )

def get_all_tariffs():
    
    """Получение всех тарифов"""
    conn = sqlite3.connect('user_data.db')
    cursor = conn.cursor()
    
    try:
        cursor.execute('SELECT * FROM tariffs_table')
        tarif = cursor.fetchall()
        
        # Преобразуем в список словарей для удобства
        columns = [desc[0] for desc in cursor.description]
        result = [dict(zip(columns, row)) for row in tarif]
        
        return result
    except Exception as e:
        print(f"Ошибка при получении данных: {e}")
        return []
    finally:
        conn.close()

#Функция для красивого отображения     
def format_tarifs_for_display(tarif):
    """Форматирование информации о тарифе для вывода в Telegram"""
    return (
        f"Тариф ID: {tarif['id_tarif']}\n"
        f"Название: {tarif['tarif_name']}\n"
        f"Цена: {tarif['stoimost_tarif']} руб.\n"
        f"наличие акции: {'Да' if tarif['akciya'] else 'Нет'}\n"
        f"Цена за пол года: {tarif['stoimost_6month']}\n"
        f"Цена за год: {tarif['stoimost_12month']}\n"
        "-------------------------"
    )



