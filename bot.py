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
ROW, COL = None, None


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
    if is_valid_url(url):
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
    else:
        msg = bot.send_message(message.chat.id, "Отправь мне правильную полную ссылку на таблицу!")
        bot.register_next_step_handler(msg, connect_table)


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
        try:
            df = pd.DataFrame.from_records(ws_values[1:], columns=ws_values[0])
            return worksheet, tables[str(max(map(int, tables.keys())))]["url"], df
        except IndexError:
            return False
    except FileNotFoundError:
        return None


def choose_action(message):
    """Обрабатываем действия верхнего уровня"""
    if message.text == "Подключить Google-таблицу":
        msg = bot.send_message(message.chat.id, "Отправь мне полную ссылку на таблицу")
        bot.register_next_step_handler(msg, connect_table)

    elif message.text == "Редактировать предметы":
        markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        markup.row("Добавить новый предмет")
        markup.row("Изменить информацию о предмете")
        markup.row("Удалить предмет")
        markup.row("Удалить все предметы")
        info = bot.send_message(message.chat.id, "Выбери действие", reply_markup=markup)
        bot.register_next_step_handler(info, choose_subject_action)

    elif message.text == "Изменить дедлайны":
        markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        markup.row("Добавить новый дедлайн")
        markup.row("Редактировать дедлайн")
        bot.send_message(message.chat.id, "Выбери действие", reply_markup=markup)
        bot.register_next_step_handler(message, choose_subject)

    elif message.text == "Посмотреть дедлайны на этой неделе":
        today = datetime.today()
        week = today + timedelta(days=7)
        a, b, df = access_current_sheet()
        mes = f""
        for i in range(2, len(a.col_values(1)) + 1):
            for ind, data in enumerate(a.row_values(i)[2:], 3):
                if is_valid_date(data):
                    if today <= convert_date(data) <= week:
                        mes += f"{a.cell(i, 1).value}, Работа №{a.cell(1, ind).value}: {data}\n"
        if mes == "":
            mes += "На этой неделе дедлайнов нет!"
        bot.send_message(message.chat.id, mes)
        start(message)


def choose_subject_action(message):
    """Выбираем действие в разделе Редактировать предметы"""
    if message.text == "Добавить новый предмет":
        info = bot.send_message(message.chat.id, "Введи название предмета, который хочешь добавить")
        bot.register_next_step_handler(info, add_new_subject)

    elif message.text == "Изменить информацию о предмете":
        markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        markup.row("Изменить название предмета")
        markup.row("Изменить ссылку на таблицу с баллами по предмету")
        info = bot.send_message(message.chat.id, "Выбери действие", reply_markup=markup)
        bot.register_next_step_handler(info, choose_subject)

    elif message.text == "Удалить предмет":
        choose_subject(message)

    elif message.text == "Удалить все предметы":
        markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        markup.row("Да, гори оно всё огнём")
        markup.row("Нет, ещё пригодится")
        info = bot.send_message(message.chat.id, "Точно удалить всё?", reply_markup=markup)
        bot.register_next_step_handler(info, choose_removal_option)


def choose_deadline_action(message, action):
    """Выбираем действие в разделе Редактировать дедлайн"""
    table_data = access_current_sheet()
    ws = table_data[0]
    global ROW, COL
    cell = ws.find(message.text)
    ROW = cell.row
    COL = cell.col
    info = bot.send_message(message.chat.id, "Введи номер работы")
    bot.register_next_step_handler(info, update_subject_deadline, action)


def choose_removal_option(message):
    """Уточняем, точно ли надо удалить все"""
    if message.text == "Да, гори оно всё огнём":
        clear_subject_list(message)

    elif message.text == "Нет, ещё пригодится":
        bot.send_message(message.chat.id, "Как скажете-с!")
        sleep(2)
        start(message)


def choose_subject(message):
    """Выбираем предмет, у которого надо отредактировать дедлайн"""
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    table_data = access_current_sheet()
    df = table_data[2]
    for i in range(df.shape[0]):
        markup.row(df.at[i, "Subject"])
    info = bot.send_message(message.chat.id, "Выбери предмет", reply_markup=markup)
    if message.text == "Изменить название предмета":
        bot.register_next_step_handler(info, update_subject_title)
    elif message.text == "Изменить ссылку на таблицу с баллами по предмету":
        bot.register_next_step_handler(info, update_subject_url)
    elif message.text == "Удалить предмет":
        bot.register_next_step_handler(info, delete_subject)
    elif message.text == "Добавить новый дедлайн" or message.text == "Редактировать дедлайн":
        action = message.text
        bot.register_next_step_handler(info, choose_deadline_action, action)


def update_subject_deadline(message, action):
    """Обновляем дедлайн"""
    global COL
    if not message.text.isdigit():
        info = bot.send_message(
            message.chat.id,
            "Ошибочка. Введи номер работы как целое число без дополнительных знаков",
        )
        bot.register_next_step_handler(info, update_subject_deadline)
        return
    if int(message.text) > 100:
        info = bot.send_message(
            message.chat.id,
            "Вряд ли у тебя так много работ. Введи номер работы как целое число, не большее, чем 100",
        )
        bot.register_next_step_handler(info, update_subject_deadline)
        return
    table_data = access_current_sheet()
    ws = table_data[0]
    df = table_data[2]
    if action == "Редактировать дедлайн" and int(message.text) > df.shape[1] - 2:
        info = bot.send_message(
            message.chat.id,
            "Такой работы нет (пока). Попробуй еще раз",
        )
        bot.register_next_step_handler(info, update_subject_deadline, action)
        return
    current_date = ws.cell(ROW, COL + int(message.text) + 1).value
    if current_date:
        info = bot.send_message(
            message.chat.id,
            f"Cейчас по этой работе стоит дедлайн <b>{current_date}</b>.\nВведи новую дату в формате\nDD/MM/YY",
            parse_mode="HTML",
        )
    elif action == "Редактировать дедлайн":
        info = bot.send_message(
            message.chat.id,
            "Такой работы нет (пока). Попробуй еще раз",
        )
        bot.register_next_step_handler(info, update_subject_deadline, action)
        return
    else:
        info = bot.send_message(message.chat.id, "Введи дату дедлайна в формате\nDD/MM/YY")
    COL += int(message.text) + 1
    bot.register_next_step_handler(info, update_cell_datetime)


def add_new_subject(message):
    """Вносим новое название предмета в Google-таблицу"""
    table_data = access_current_sheet()
    ws = table_data[0]
    ws.append_row([message.text])
    info = bot.send_message(
        message.chat.id, "Введи полную ссылку на таблицу с баллами по этому предмету"
    )
    bot.register_next_step_handler(info, add_new_subject_url)


def add_new_subject_url(message):
    """Вносим новую ссылку на таблицу предмета в Google-таблицу"""
    text = (
        "https:///" + message.text
        if (len(message.text) > 3 and message.text[:4] == "www.")
        else message.text
    )
    is_valid = is_valid_url(text)
    if not is_valid:
        new = bot.send_message(message.chat.id, "Cсылка не рабочая. Введи нормальную.")
        bot.register_next_step_handler(new, add_new_subject_url)
        return
    table_data = access_current_sheet()
    ws = table_data[0]
    df = table_data[2]
    ws.update_cell(df.shape[0] + 1, 2, text)
    bot.send_message(message.chat.id, "Предмет успешно добавлен")
    sleep(2)
    start(message)


def update_subject_title(message):
    """Обновляем название предмета в Google-таблице"""
    table_data = access_current_sheet()
    ws = table_data[0]
    global ROW, COL
    cell = ws.find(message.text)
    ROW = cell.row
    COL = cell.col
    new = bot.send_message(message.chat.id, "Введи новое название")
    bot.register_next_step_handler(new, update_cell_data, new.text)


def update_subject_url(message):
    """Обновляем ссылку на предмет в Google-таблице"""
    table_data = access_current_sheet()
    ws = table_data[0]
    global ROW, COL
    cell = ws.find(message.text)
    ROW = cell.row
    COL = cell.col + 1
    new = bot.send_message(message.chat.id, "Введи новую ссылку")
    bot.register_next_step_handler(new, update_cell_data, new.text)


def update_cell_data(message, action):
    if action == "Введи новую ссылку" or action == "Cсылка не рабочая. Введи нормальную.":
        text = (
            "https://" + message.text
            if (len(message.text) > 3 and message.text[:4] == "www.")
            else message.text
        )
        is_valid = is_valid_url(text)
        if not is_valid:
            new = bot.send_message(message.chat.id, "Cсылка не рабочая. Введи нормальную.")
            bot.register_next_step_handler(new, update_cell_data, new.text)
            return
        message.text = text
    global ROW, COL
    table_data = access_current_sheet()
    ws = table_data[0]
    ws.update_cell(ROW, COL, message.text)
    bot.send_message(message.chat.id, "Готово!")
    sleep(2)
    start(message)


def update_cell_datetime(message):
    today = datetime.now()
    if not is_valid_date(message.text):
        info = bot.send_message(
            message.chat.id,
            "Ошибочка. Дата должна соответствовать форматy DD/MM/YY и иметь адекватные временные рамки.\nПопробуй "
            "ещё раз",
        )
        bot.register_next_step_handler(info, update_cell_datetime)
        return
    date = convert_date(message.text)
    delta = date - today
    if delta.days // 365 > 5 or date < today:
        info = bot.send_message(
            message.chat.id,
            "Ошибочка. Дата должна иметь адекватные временные рамки.\nПопробуй ещё раз",
        )
        bot.register_next_step_handler(info, update_cell_datetime)
        return

    global ROW, COL
    table_data = access_current_sheet()
    ws = table_data[0]
    ws.update_cell(ROW, COL, message.text)
    bot.send_message(message.chat.id, "Готово!")
    sleep(2)
    start(message)


def delete_subject(message):
    """Удаляем предмет в Google-таблице"""
    table_data = access_current_sheet()
    ws = table_data[0]
    cell = ws.find(message.text)
    ws.delete_rows(cell.row)
    bot.send_message(message.chat.id, "Исполнено!")
    sleep(2)
    start(message)


def clear_subject_list(message):
    """Удаляем все из Google-таблицы"""
    table_data = access_current_sheet()
    ws = table_data[0]
    ws.clear()
    bot.send_message(message.chat.id, "Теперь таблица девственно чиста!")
    sleep(2)
    start(message)


@bot.message_handler(commands=["start"])
def greetings(message):
    bot.send_message(message.chat.id, "Привет! Я бот и я помогу тебе разгрести дедлайны")
    table_data = access_current_sheet()
    if table_data:
        df = table_data[2]
        bot.send_message(message.chat.id, "Доступные предметы")
        for i in range(df.shape[0]):
            bot.send_message(
                message.chat.id,
                f"<a href='{df.at[i, 'Link']}'> {df.at[i, 'Subject']} </a>",
                parse_mode="HTML",
                disable_web_page_preview=True,
            )
    start(message)


def start(message):
    start_markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    table_data = access_current_sheet()
    if not table_data:
        if table_data is None:
            start_markup.row("Подключить Google-таблицу")
        else:
            start_markup.row("Данная таблица пуста, добавьте данные")
    else:
        start_markup.row("Посмотреть дедлайны на этой неделе")
        start_markup.row("Изменить дедлайны")
        start_markup.row("Редактировать предметы")
    info = bot.send_message(message.chat.id, "Что хочешь сделать?", reply_markup=start_markup)
    bot.register_next_step_handler(info, choose_action)


bot.infinity_polling()
