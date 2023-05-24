import os
from time import sleep

import telebot
import gspread
import json
import pandas as pd
import re
from datetime import datetime, timedelta

from dotenv import load_dotenv

path = os.path.join(os.path.dirname(__file__), '.env')
if os.path.exists(path):
    load_dotenv(path)
    token = os.environ.get("TOKEN")
else:
    raise FileNotFoundError

bot = telebot.TeleBot(token)


def is_valid_date(date: str = "01/01/00", divider: str = "/") -> bool:
    """Проверяем, что дата дедлайна валидна:
    - дата не может быть до текущей
    - не может быть позже, чем через год
    - не может быть такой, которой нет в календаре
    - может быть сегодняшним числом
    - пользователь не должен быть обязан вводить конкретный формат даты
    (например, только через точку или только через слеш)"""
    # Пробуем преобразовать строку даты в объект datetime
    try:
        deadline_date = datetime.strptime(date, f"%d{divider}%m{divider}%y")
    except ValueError:
        return False

    # Получаем текущую дату и время
    now = datetime.today()

    # Проверяем, что дата не может быть до текущей
    if deadline_date + timedelta(days=now.day, hours=now.hour, minutes=now.minute + 1) < now:
        return False

    # Проверяем, что дата не может быть позже, чем через год
    if deadline_date > now + timedelta(days=365):
        return False

    return True


def is_valid_url(url: str = "") -> bool:
    """Проверяем, что ссылка рабочая"""
    regex = r"^(https?://|www\.)\S*\.ru$"
    if re.match(regex, url):
        return True

    regex = r"^en\S*\.[a-z]+\.[a-z]{2,3}$"
    if re.match(regex, url):
        return False

    regex = r"^\S*\.ru$"
    if re.match(regex, url):
        return True

    return False

def convert_date(date: str = "01/01/00"):
    """Конвертируем дату из строки в datetime"""
    day, month, year = date.split("/")
    return datetime(int('20' + year), int(month), int(day))


def connect_table(message):
    """Подключаемся к Google-таблице"""
    url = message.text
    sheet_id = url.split('spreadsheets/d/')[1].split('/edit')[0]
    try:
        with open("tables.json") as json_file:
            tables = json.load(json_file)
        title = len(tables) + 1
        tables[title] = {"url": url, "id": sheet_id}
    except FileNotFoundError:
        tables = {0: {"url": url, "id": sheet_id}}
    with open("tables.json", "w") as json_file:
        json.dump(tables, json_file)
    bot.send_message(message.chat.id, "Таблица подключена!")
    sleep(2)
    start(message)

def access_current_sheet():
    """Обращаемся к Google-таблице"""
    try:
        with open("tables.json") as json_file:
            tables = json.load(json_file)

        sheet_id = tables[str(max(map(int, tables.keys())))]["id"]
        gc = gspread.service_account(filename="my_credentials.json")
        sh = gc.open_by_key(sheet_id)
        worksheet = sh.sheet1
        ws_values = worksheet.get_all_values()
        df = pd.DataFrame.from_records(ws_values[1:], columns=ws_values[0])
        return worksheet, tables[str(max(map(int, tables.keys())))]["url"], df
    except FileNotFoundError:
        return None


def choose_action(message):
    """Обрабатываем действия верхнего уровня"""
    if message.text == "Подключить Google-таблицу":
        # PUT YOUR CODE HERE
        pass
    elif message.text == "Редактировать предметы":
        # PUT YOUR CODE HERE
        pass
    elif message.text == "Редактировать дедлайн":
        # PUT YOUR CODE HERE
        pass
    elif message.text == "Посмотреть дедлайны на этой неделе":
        # PUT YOUR CODE HERE
        pass


def choose_subject_action(message):
    """Выбираем действие в разделе Редактировать предметы"""
    # PUT YOUR CODE HERE
    pass


def choose_deadline_action(message):
    """Выбираем действие в разделе Редактировать дедлайн"""
    # PUT YOUR CODE HERE
    pass


def choose_removal_option(message):
    """Уточняем, точно ли надо удалить все"""
    # PUT YOUR CODE HERE
    pass


def choose_subject(message):
    """Выбираем предмет, у которого надо отредактировать дедлайн"""
    # PUT YOUR CODE HERE
    pass


def update_subject_deadline(message):
    """Обновляем дедлайн"""
    # PUT YOUR CODE HERE
    pass


def add_new_subject(message):
    """Вносим новое название предмета в Google-таблицу"""
    # PUT YOUR CODE HERE
    pass


def add_new_subject_url(message):
    """Вносим новую ссылку на таблицу предмета в Google-таблицу"""
    # PUT YOUR CODE HERE
    pass


def update_subject(message):
    """Обновляем информацию о предмете в Google-таблице"""
    # PUT YOUR CODE HERE
    pass


def delete_subject(message):
    """Удаляем предмет в Google-таблице"""
    # PUT YOUR CODE HERE
    pass


def clear_subject_list(message):
    """Удаляем все из Google-таблицы"""
    # PUT YOUR CODE HERE
    pass


@bot.message_handler(commands=["start"])
def start(message):
    start_markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    start_markup.row("Подключить Google-таблицу")
    start_markup.row("Посмотреть дедлайны на этой неделе")
    start_markup.row("Внести новый дедлайн")
    start_markup.row("Редактировать предметы")
    info = bot.send_message(message.chat.id, "Что хотите сделать?", reply_markup=start_markup)
    bot.register_next_step_handler(info, choose_action)


bot.infinity_polling()
