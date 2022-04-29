import telebot
from botrequests import bestdeal, highprice, history
from decouple import config
import parsing
from telegram_bot_calendar import DetailedTelegramCalendar, LSTEP
from datetime import date, datetime

token = config('BOT_TOKEN')
bot = telebot.TeleBot(token)


def init_database() -> None:
    """Функция проверяет в БД наличие таблиц и создает их в случае отсутствия"""
    # история диалогов с пользователями
    parsing.bd_update('''CREATE TABLE IF NOT EXISTS main_log
                        (message_id INTEGER PRIMARY KEY, 
                         chat_id INTEGER, 
                         user_id INTEGER, 
                         username TEXT, 
                         date INTEGER, 
                         text TEXT,
                         photos TEXT)''')
    # открытые на данный момент диалоги
    parsing.bd_update('''CREATE TABLE IF NOT EXISTS current_dialogs
                         (chat_id INTEGER, 
                          query_type TEXT,
                          stage INTEGER, 
                          city_id INTEGER, 
                          check_in TEXT, 
                          check_out TEXT, 
                          guests_num INTEGER, 
                          hotels_num INTEGER, 
                          photos_num INTEGER)''')
    # города, по которым уже производился поиск
    parsing.bd_update('''CREATE TABLE IF NOT EXISTS cities_code
                        (city_id INTEGER, 
                         city_name TEXT)''')
    # фотографии отелей, по которым была выдача
    parsing.bd_update('''CREATE TABLE IF NOT EXISTS photos_url
                        (hotel_id INTEGER, 
                         photo_id INTEGER,
                         photo_url TEXT)''')


def check_num(check_data: str, min_num: int, max_num: int, chat_id: int) -> bool:
    """Функция проверяет, что в диалоге было введено число в указанном диапазоне"""
    try:
        num = int(check_data)
    except ValueError as exc:
        history.errors_log('func - check_num: ' + str(exc))
        bot.send_message(chat_id, 'Введите число от {min} до {max}!'.format(min=str(min_num), max=str(max_num)))
        return False
    if not min_num <= num <= max_num:
        bot.send_message(chat_id, 'Введите число от {min} до {max}!'.format(min=str(min_num), max=str(max_num)))
        return False
    return True


def dispetcher(message: telebot.types.Message, stage: int) -> None:
    """Функция узнает у пользователя параметры запроса, сохраняет их в БД и определяет дальнейшие действия"""

    # сообщения для отправки пользлвателю в зависимости от этапа диалога
    messages = {0: 'Введите город для поиска отелей (латиницей на английском)',
                1: 'Выберите дату заезда из календаря.',
                4: 'Сколько отелей вы хотите посмотреть (от 1 до 10)?',
                5: 'Сколько фотографий каждого отеля вы хотите посмотреть (от 0 до 5)?',
                'city': 'Такой город не найден. Возможно, ошибка в написании. Пожалуйста, повторите ввод.'}

    # запросы к БД в зависимости от этапа диалога
    queries = {1: "UPDATE current_dialogs SET stage = 1, city_id = {cc} WHERE chat_id = {id}",
               4: "UPDATE current_dialogs SET stage = 4, guests_num = {mt} WHERE chat_id = {id}",
               5: "UPDATE current_dialogs SET stage = 5, hotels_num = {mt} WHERE chat_id = {id}",
               6: "UPDATE current_dialogs SET stage = 6, photos_num = {mt} WHERE chat_id = {id}",
               'city': "SELECT * FROM cities_code WHERE city_name = '{mt}'",
               'add_city': "INSERT INTO cities_code VALUES ({cc}, '{mt}')"}

    # начало диалога, узнаем город для запроса
    if stage == 0:
        bot.send_message(message.chat.id, messages[stage])

    # узнаем дату заезда
    elif stage == 1:
        # пытаемся найти город среди тех, по которым уже был запрос
        query = queries['city'].format(mt=message.text.capitalize())
        rows = parsing.bd_select(query)

        # если нашли, используем id из БД
        if len(rows) != 0:
            city_code = rows[0][0]
        else:
            # если в БД город не найден, делаем запрос к API
            city_code = parsing.city_destination_id(message.text.capitalize())
            if city_code is None:
                # если API ничего не вернул, просим повторить ввод
                bot.send_message(message.chat.id, messages['city'])
                return None
            else:
                # сохраняем город в БД
                query = queries['add_city'].format(cc=city_code, mt=message.text.capitalize())
                parsing.bd_update(query)
        # добавляем город в текущий диалог
        query = queries[stage].format(cc=str(city_code), id=str(message.chat.id))
        parsing.bd_update(query)
        bot.send_message(message.chat.id, messages[stage])

        # отсылаем в диалог календарь для выбора даты заезда
        calendar, step = DetailedTelegramCalendar().build()
        bot.send_message(message.chat.id, f"Select {LSTEP[step]}", reply_markup=calendar)

    # этапы выбора дат. Не реагируем на текстовые сообщения, ждем ответ от календаря
    elif stage == 2 or stage == 3:
        bot.delete_message(message.chat.id, message.message_id)

    # узнаем количество гостей для выборки
    elif stage == 4:
        if not check_num(message.text, 1, 10, message.chat.id):
            return None
        query = queries[stage].format(mt=message.text, id=str(message.chat.id))
        parsing.bd_update(query)
        bot.send_message(message.chat.id, messages[stage])

    # узнаем количество отелей для выборки
    elif stage == 5:
        if not check_num(message.text, 1, 10, message.chat.id):
            return None
        query = queries[stage].format(mt=message.text, id=str(message.chat.id))
        parsing.bd_update(query)
        bot.send_message(message.chat.id, messages[stage])

    # финальный этап. Узнаем количество фотографий для запроса, формируем и отсылаем запрос к API,
    # сохраняем историю, закрываем текущий диалог
    else:
        if not check_num(message.text, 0, 5, message.chat.id):
            return None

        bot.send_message(message.chat.id, 'Подбираем для вас варианты...')

        query = queries[stage].format(mt=message.text, id=str(message.chat.id))
        parsing.bd_update(query)

        # инициализируем параметры запроса в API
        query = 'SELECT * FROM current_dialogs WHERE chat_id = ' + str(message.chat.id)
        rows = parsing.bd_select(query)
        q_type, city_id, check_in, check_out, guest_num, num_hotels, num_photos = \
            rows[0][1], rows[0][3], rows[0][4], rows[0][5], rows[0][6], rows[0][7], rows[0][8]

        # записываем запрос в историю
        query = "SELECT * FROM cities_code WHERE city_id = {id}".format(id=str(city_id))
        rows = parsing.bd_select(query)
        city_name = rows[0][1]
        user_message = "Найди {nh} самых дешёвых отелей для {gn} гостей в городе {cn}.\n" \
                       "Дата заезда: {ci}, дата отъезда: {co}.\n" \
                       "Покажи {pn} фотографий каждого отеля".format(nh=num_hotels,
                                                                     gn=guest_num,
                                                                     cn=city_name,
                                                                     ci=check_in,
                                                                     co=check_out,
                                                                     pn=num_photos)
        history.set_log(message.message_id, message.chat.id, message.from_user.id, message.from_user.username,
                        message.date, user_message, '')

        # запрашиваем данные
        output = parsing.hotels_list(str(city_id), str(check_in), str(check_out), str(guest_num), str(num_hotels),
                                     num_photos)
        # выдаем ответ пользователю
        if num_photos == 0:
            output_txt = ''
            for i_elem in output:
                output_txt += i_elem[0]

            answer = bot.send_message(message.chat.id, output_txt, parse_mode="HTML", disable_web_page_preview=True)
            # сохраняем историю
            history.set_log(answer.message_id, answer.chat.id, answer.from_user.id, answer.from_user.username,
                            answer.date, output_txt, '')
        else:
            add_id = 1
            for i_elem in output:
                query = 'SELECT photo_url FROM photos_url WHERE hotel_id = {id} LIMIT {n}'.format(n=str(num_photos),
                                                                                                  id=str(i_elem[1]))
                links = parsing.bd_select(query)
                # проверяем, нашлись ли в базе фотки
                if len(links) > 0:
                    medias = []
                    links_to_log = links[0][0]
                    media = telebot.types.InputMediaPhoto(links[0][0], caption=i_elem[0], parse_mode="HTML")
                    medias.append(media)
                    for i_link in range(1, len(links)):
                        media = telebot.types.InputMediaPhoto(links[i_link][0])
                        medias.append(media)
                        links_to_log += ',' + links[i_link][0]
                    bot.send_media_group(message.chat.id, medias)
                    # сохраняем историю
                    history.set_log(message.message_id + add_id, message.chat.id, 5161451101, 'HotelsVrvBot',
                                    message.date, i_elem[0], links_to_log)
                    add_id += 1
                # если был сбой и в базе пусто, выдаем ответ без них
                else:
                    answer = bot.send_message(message.chat.id, i_elem[0], parse_mode="HTML",
                                              disable_web_page_preview=True)
                    # сохраняем историю
                    history.set_log(answer.message_id, answer.chat.id, answer.from_user.id, answer.from_user.username,
                                    answer.date, i_elem[0], '')

        # очищаем текущий диалог
        query = 'DELETE FROM current_dialogs WHERE chat_id = {id}'.format(id=str(message.chat.id))
        parsing.bd_update(query)


def new_session(message: telebot.types.Message, command: str) -> None:
    """Функция создает в БД строку нового открытого диалога"""
    query = "INSERT INTO current_dialogs VALUES ({id}, '{cmd}', 0, NULL, NULL, NULL, NULL, NULL, " \
            "NULL)".format(id=str(message.chat.id), cmd=command)
    parsing.bd_update(query)
    dispetcher(message, 0)


def get_text_messages(message: telebot.types.Message) -> None:
    """Функция запускает ветку нового диалога с пользователем в зависимости от полученного сообщения"""
    if not message.text.startswith('/'):
        history.set_log(message.message_id, message.chat.id, message.from_user.id, message.from_user.username,
                        message.date, message.text, '')

    if message.text.lower() == "привет":
        answer_text = 'Привет, <b>' + message.from_user.username + \
                      '</b>, меня зовут Сергей Вараев и это мой дипломный проект по курсу Python-basic.'
    elif message.text == "/lowprice":
        new_session(message, 'lowprice')
        return None

    elif message.text == "/highprice":
        answer_text = highprice.get_hidhprice()
    elif message.text == "/bestdeal":
        answer_text = bestdeal.get_bestdeal()
    elif message.text == "/history":
        parts = history.get_history(message.chat.id)
        for row in parts:
            if row[1] == '':
                bot.send_message(message.chat.id, row[0], parse_mode="HTML", disable_web_page_preview=True)
            else:
                links = row[1].split(',')
                medias = []
                media = telebot.types.InputMediaPhoto(links[0], caption=row[0], parse_mode="HTML")
                medias.append(media)

                for i_link in range(1, len(links)):
                    media = telebot.types.InputMediaPhoto(links[i_link])
                    medias.append(media)
                bot.send_media_group(message.chat.id, medias)
        return None

    elif message.text == "/help":
        answer_text = '/lowprice - узнать топ самых дешёвых отелей в городе\n' \
                      '/highprice - узнать топ самых дорогих отелей в городе\n' \
                      '/bestdeal - узнать список самых дешёвых отелей в городе, находящихся ближе всего к центру\n' \
                      '/history - узнать историю поиска отелей\n' \
                      '/help - помощь по командам бота'
    else:
        answer_text = "Команда не распознана! Повторите ввод."

    if len(answer_text) > 0:
        answer = bot.send_message(message.chat.id, answer_text, parse_mode="HTML")
        if not message.text.startswith('/'):
            history.set_log(answer.message_id, answer.chat.id, answer.from_user.id, answer.from_user.username,
                            answer.date, answer_text, '')


@bot.callback_query_handler(func=DetailedTelegramCalendar.func())
def cal(c: telebot.types.CallbackQuery) -> None:
    """Функция ловит ответ календаря"""
    result, key, step = DetailedTelegramCalendar().process(c.data)
    if not result and key:
        bot.edit_message_text(f"Select {LSTEP[step]}",
                              c.message.chat.id,
                              c.message.message_id,
                              reply_markup=key)
    elif result:
        bot.edit_message_text(f"Выбрана дата {result}",
                              c.message.chat.id,
                              c.message.message_id)
        query = "SELECT * FROM current_dialogs WHERE chat_id = {id}".format(id=str(c.message.chat.id))
        rows = parsing.bd_select(query)

        # инициализация переменных для этапа выбора даты заезда
        if rows[0][2] == 1:
            check_date = date.today()
            err_msg = 'Выбранная дата должна быть больше текущей, повторите ввод!'
            stage = '2'
            field = 'check_in'
            ok_msg = 'Выберите дату отъезда из календаря.'
        # инициализация переменных для этапа выбора даты отъезда
        else:
            check_date = datetime.strptime(rows[0][4], '%Y-%m-%d').date()
            err_msg = 'Дата отъезда должна быть больше даты заселения, повторите ввод!'
            stage = '3'
            field = 'check_out'
            ok_msg = 'Введите количество гостей (целое число от 1 до 10).'

        # проверка даты на корректность (заезд после текущей, отъезд после заезда)
        # если некорректно, пишем пользователю, что он лопух, кидаем ему календарь ещё раз
        if result <= check_date:
            bot.send_message(c.message.chat.id, err_msg)
            calendar, step = DetailedTelegramCalendar().build()
            bot.send_message(c.message.chat.id, f"Select {LSTEP[step]}", reply_markup=calendar)
            return None
        # если все хорошо, сохраняем результат
        else:
            query = "UPDATE current_dialogs SET stage = {stg}, {fld} = '{mt}' WHERE chat_id = {id}" \
                .format(mt=result,
                        stg=stage,
                        fld=field,
                        id=str(c.message.chat.id))
            bot.send_message(c.message.chat.id, ok_msg)

        # отправка в чат календаря для выбора даты отъезда
        if rows[0][2] == 1:
            calendar, step = DetailedTelegramCalendar().build()
            bot.send_message(c.message.chat.id, f"Select {LSTEP[step]}", reply_markup=calendar)

        parsing.bd_update(query)


@bot.message_handler(content_types=['text'])
def listener(message: telebot.types.Message) -> None:
    """Функция слушает сообщения из телеги"""
    # Проверяем, существует ли активный диалог с данным пользователем
    query = 'SELECT * FROM current_dialogs WHERE chat_id = ' + str(message.chat.id)
    rows = parsing.bd_select(query)

    if len(rows) == 0:
        # Если нет, запускаем стартовое распознавание запроса
        get_text_messages(message)
        # если пользователь ввел новую команду, сбрасываем текущий диалог, стартуем с нуля
    elif message.text.startswith('/'):
        query = 'DELETE FROM current_dialogs WHERE chat_id = ' + str(message.chat.id)
        parsing.bd_update(query)
        get_text_messages(message)
    else:
        # Если диалог найден, перебрасываем на продолжение
        dispetcher(message, rows[0][2] + 1)


if __name__ == "__main__":

    init_database()
    bot.infinity_polling()
