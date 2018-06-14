from telebot import types


def set_main_keyboard():
    keyboard = types.ReplyKeyboardMarkup(True)
    keyboard.row('Следующий матч')
    keyboard.row('Новости')
    keyboard.row('Время')
    keyboard.row('Настройки')
    return keyboard


def set_return_keyboard():
    keyboard = types.ReplyKeyboardMarkup(True)
    keyboard.row('Назад')
    return keyboard