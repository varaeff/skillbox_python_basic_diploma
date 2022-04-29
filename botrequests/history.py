import sqlite3
from datetime import datetime
import parsing
from typing import List
import requests
import json


def set_log(message_id: int,
            chat_id: int,
            user_id: int,
            username: str,
            message_date: int,
            msg_text: str,
            photos: str) -> None:
    """добавление данных в историю"""
    message_data = str(message_id), str(chat_id), str(user_id), "\"" + username + "\"", \
                   str(message_date), "\"" + msg_text + "\"", "\"" + photos + "\""
    message_data = ", ".join(message_data)
    try:
        parsing.bd_update("INSERT INTO main_log VALUES (" + message_data + ")")
    except Exception as exc:
        errors_log('func - set_log: ' + exc.__str__())


def get_history(chat_id: int) -> List[List[str]]:
    """запрос истории переписки"""
    connection = sqlite3.connect('bot_data.db')
    cursor = connection.cursor()
    cursor.execute('select * from main_log where chat_id = ' + str(chat_id))
    rows = cursor.fetchall()
    connection.commit()
    connection.close()

    answers = []
    answer, answer_msg = '', ''
    for row in rows:
        answer = '<i>' + datetime.fromtimestamp(row[4]).strftime('%Y-%m-%d %H:%M:%S') + '</i> <b>' + row[3] \
                 + ':</b>\n' + row[5] + '\n\n\n'

        # проверка ограничения размера сообщения в телеграме
        # плюс проверка на отсутствие вложенных фотографий в сообщении
        if len(answer_msg) + len(answer) < 4096 and row[6] == '':
            answer_msg += answer
        elif row[6] == '':
            answers.append([answer_msg, ''])
            answer_msg = answer
        else:
            if answer_msg != '':
                answers.append([answer_msg, ''])
            answers.append([answer, row[6]])
            answer_msg = ''
    if answer_msg != '':
        answers.append([answer_msg, ''])

    return answers


def errors_log(err_msg: str) -> None:
    """сохранение ошибок, возникших при обработке исключений, в лог"""
    now = datetime.now().astimezone()
    time_format = "%d.%m.%Y %H:%M:%S"
    with open('logfile.log', 'a') as logfile:
        logfile.write(f'{now:{time_format}} Exception: {err_msg}\n')


def save_photos(hotel_id: str) -> None:
    """сохранение фотографий отеля в БД"""
    # проверяем БД на наличие фоток отеля. Если есть, выходим из функции
    query = 'SELECT * FROM photos_url WHERE hotel_id = {id}'.format(id=str(hotel_id))
    rows = parsing.bd_select(query)
    if len(rows) > 0:
        return None

    # запрашиваем данные
    url = "https://hotels4.p.rapidapi.com/properties/get-hotel-photos"
    querystring = {"id": hotel_id}
    headers = parsing.headers
    response = requests.request("GET", url, headers=headers, params=querystring)
    resp_data = json.loads(response.text)

    # 5 первых фоток сохраняем в БД
    num = 0
    for i_elem in resp_data["hotelImages"]:
        query = "INSERT INTO photos_url VALUES ({id}, {ph_id}, '{url}')".format(id=hotel_id,
                                                                                ph_id=i_elem["imageId"],
                                                                                url=i_elem["baseUrl"].format(size='w'))
        parsing.bd_update(query)
        num += 1
        if num == 5:
            break
