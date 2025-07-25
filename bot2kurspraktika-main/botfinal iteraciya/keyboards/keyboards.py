from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

                        

#клавиатура для юзера
main_kb = ReplyKeyboardMarkup(
    keyboard=[
    [KeyboardButton(text='Обратная связь')],
    [KeyboardButton(text='Оборудование в продаже')],
    [KeyboardButton(text='Актуальные тарифные планы')]
    ],                      resize_keyboard=True,
                            input_field_placeholder='Выберите действие из меню',
                            selective=True
)

# Клавиатура для админ-панели
admin_panel_kb = ReplyKeyboardMarkup(keyboard=[
    [KeyboardButton(text='Управление роутерами')],
    [KeyboardButton(text='Управление тарифами')],   
    [KeyboardButton(text='Юзеры')],
    [KeyboardButton(text='Назад')]
],                          resize_keyboard=True,
                            input_field_placeholder='Выберите действие из меню'
)

#клавиатура для админа тарифы
change_tarif_kb = ReplyKeyboardMarkup(keyboard=[
    [KeyboardButton(text='Добавление тарифа')],
    [KeyboardButton(text='Изменение тарифа')],
    [KeyboardButton(text='Удаление тарифа')],
    [KeyboardButton(text='Назад')]
],
                            resize_keyboard=True,
                            input_field_placeholder='Выберите действие из меню'
)

#клавиатура для админа роутеры
change_routers_kb = ReplyKeyboardMarkup(keyboard=[
    [KeyboardButton(text='Добавление роутера')],
    [KeyboardButton(text='Изменение роутера')],
    [KeyboardButton(text='Удаление роутера')],
    [KeyboardButton(text='Назад')]
],                          resize_keyboard=True,
                           # one_time_keyboard=True,
                            input_field_placeholder='Выберите действие из меню',
                            selective=True
)


get_yes_no_kb = ReplyKeyboardMarkup(keyboard=[
    [KeyboardButton(text="ДА")],
    [KeyboardButton(text="НЕТ")]
],                          resize_keyboard=True,
                            one_time_keyboard=True)

#панель админа юзеры
change_users_admins_panel = ReplyKeyboardMarkup(keyboard=[
    [KeyboardButton(text='Добавление прав')],
    [KeyboardButton(text='Удаление прав')],
    [KeyboardButton(text='Информация')],
    [KeyboardButton(text='Назад')]
],                          resize_keyboard=True,
                            input_field_placeholder='Выберите действие из меню'
)


