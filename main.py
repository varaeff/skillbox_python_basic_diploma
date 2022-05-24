from datetime import date, datetime, timedelta
from typing import List

import telebot
from decouple import config
from loguru import logger
from telegram_bot_calendar import LSTEP, DetailedTelegramCalendar

from modules.api_work import city_destination_id, hotels_list
from modules.db_work import (delete_row, init_database, insert_row,
                             select_rows, set_field_param)
from modules.history import get_history, set_log
from modules.service_funcs import Dicts, check_num

logger.add("debuglog.log", format="{time:YYYY-MM-DD at HH:mm:ss} | {level} | {name} : {function} : {line} | "
                                  "{message}", level="WARNING")
logger.add("catch_log.log", filter=lambda record: "special" in record["extra"],
           format="{time:YYYY-MM-DD at HH:mm:ss} | {level} | {name} : {function} : {line} | {message}")

logger.add("user_log.log", filter=lambda record: "user" in record["extra"],
           format="{time:YYYY-MM-DD at HH:mm:ss} | {name} : {function} : {line} | {message}")

token = config('BOT_TOKEN')
bot = telebot.TeleBot(token)


@logger.catch
def get_text_messages(message: telebot.types.Message) -> None:
    """Функция запускает ветку нового диалога с пользователем в зависимости от полученного сообщения"""
    help_text = '/lowprice - узнать топ самых дешёвых отелей в городе\n' \
                '/highprice - узнать топ самых дорогих отелей в городе\n' \
                '/bestdeal - узнать список самых дешёвых отелей в городе, находящихся ближе всего к центру\n' \
                '/history - узнать историю поиска отелей\n' \
                '/help - помощь по командам бота'
    hello_text = 'Привет, <b>{}</b>, меня зовут Сергей Вараев и это мой дипломный проект по курсу Python-basic.\n\n'.\
        format(message.from_user.username)

    if not message.text.startswith('/'):
        set_log(message.message_id, message.chat.id, message.from_user.id, message.from_user.username, message.date,
                message.text, '')

    if message.text.lower() == "привет":
        answer_text = hello_text

    elif message.text == "/lowprice":
        new_session(message, 'lowprice')
        return None

    elif message.text == "/highprice":
        new_session(message, 'highprice')
        return None

    elif message.text == "/bestdeal":
        new_session(message, 'bestdeal')
        return None

    elif message.text == "/history":
        logger.bind(user=True).info('user {id} asked for history'.format(id=message.from_user.id))
        parts = get_history(message.chat.id)
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
        logger.bind(user=True).info('user {id} asked for help'.format(id=message.from_user.id))
        answer_text = help_text

    elif message.text == "/start":
        logger.bind(user=True).info('user {id} started bot'.format(id=message.from_user.id))
        answer_text = hello_text + help_text

    else:
        logger.bind(user=True).info("user {id} typed '{txt}'".format(id=message.from_user.id, txt=message.text))
        answer_text = "Команда не распознана! Повторите ввод."

    if len(answer_text) > 0:
        answer = bot.send_message(message.chat.id, answer_text, parse_mode="HTML")
        if not message.text.startswith('/'):
            set_log(answer.message_id, answer.chat.id, answer.from_user.id, answer.from_user.username, answer.date,
                    answer_text, '')


@logger.catch
def new_session(message: telebot.types.Message, command: str) -> None:
    """Функция создает в БД строку нового открытого диалога"""
    logger.bind(user=True).info('user {id} started new {cmd} session'.format(id=message.from_user.id, cmd=command))
    values = {'id': str(message.chat.id), 'cmd': command}
    insert_row('current_dialogs', ':id, :cmd, 0, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL', values)
    dispetcher(message, 0)


@logger.catch
def dispetcher(message: telebot.types.Message, stage: int) -> None:
    """Функция узнает у пользователя параметры запроса, сохраняет их в БД и определяет дальнейшие действия"""
    # начало диалога, узнаем город для запроса
    if stage == 0:
        bot.send_message(message.chat.id, 'Введите город для поиска отелей (латиницей на английском)')

    # узнаем дату заезда
    elif stage == 1:
        logger.bind(user=True).info('user {id} tryed to find city {ct}'.format(id=message.from_user.id,
                                                                               ct=message.text))
        # пытаемся найти город среди тех, по которым уже был запрос
        rows = select_rows('cities_code', 'city_name', message.text.capitalize())

        # если нашли хоть один, формируем словарь для дальнейшей обработки
        if len(rows) > 0:
            cities = []
            city = {}
            for i_row in rows:
                city["destinationId"] = i_row[0]
                city["latitude"] = i_row[2]
                city["longitude"] = i_row[3]
                city["caption"] = i_row[4]
                cities.append(city)
                city = {}
        else:
            # если в БД город не найден, делаем запрос к API
            cities = city_destination_id(message.text.capitalize())

            if cities is None or len(cities) == 0:
                # если API ничего не вернул, просим повторить ввод
                bot.send_message(message.chat.id, 'Такой город не найден. Возможно, ошибка в написании. '
                                                  'Пожалуйста, повторите ввод.')
                return None
            else:
                # сохраняем найденные города в БД
                for i_city in cities:
                    values = {'id': i_city["destinationId"],
                              'mt': message.text.capitalize(),
                              'lt': float(i_city["latitude"]),
                              'lg': float(i_city["longitude"]),
                              'cpt': i_city["caption"]}
                    insert_row('cities_code', ':id, :mt, :lt, :lg, :cpt', values)

        # проверяем, сколько городов нашли
        if len(cities) > 1:
            # меняем стадию диалога для колбэка
            set_field_param('stage', '7', message.chat.id)
            # отсылаем пользователю список найденных городов в кнопках для выбора нужного
            choose_city(message.chat.id, cities)
            return None
        else:
            # добавляем город в текущий диалог
            set_field_param('stage', '1', message.chat.id)
            set_field_param('city_id', str(cities[0]["destinationId"]), message.chat.id)

            # если обрабатывается команда bestdeal, включаем сбор дополнительных данных
            rows = select_rows('current_dialogs', 'chat_id', str(message.chat.id))
            if rows[0][1] == 'bestdeal':
                choose_price(message.chat.id)
            else:
                # переходим к выбору даты заезда
                bot.send_message(message.chat.id, 'Выберите дату заезда из календаря.')
                # отсылаем в диалог календарь для выбора даты заезда
                calendar, step = DetailedTelegramCalendar(min_date=date.today() + timedelta(days=1)).build()
                bot.send_message(message.chat.id, f"Select {LSTEP[step]}", reply_markup=calendar)

    # этапы выбора дат. Не реагируем на текстовые сообщения, ждем ответ от календаря
    # 8 - запрет реакции на сообщения при ожидании выбора города с клавиатуры
    elif 1 < stage < 4 or stage > 7:
        logger.bind(user=True).info('user {id} typed {txt} on wrong stage ({stg})'.format(id=message.from_user.id,
                                                                                          txt=message.text,
                                                                                          stg=stage))
        bot.delete_message(message.chat.id, message.message_id)

    # узнаем количество гостей для выборки
    elif stage == 4:
        if not check_num(message.text, 1, 10):
            bot.send_message(message.chat.id, 'Введите число от 1 до 10!')
            return None
        set_field_param('stage', '4', message.chat.id)
        set_field_param('guests_num', message.text, message.chat.id)
        logger.bind(user=True).info('user {id} selected {num} guests'.format(id=message.from_user.id, num=message.text))
        bot.send_message(message.chat.id, 'Сколько отелей вы хотите посмотреть (от 1 до 10)?')

    # узнаем количество отелей для выборки
    elif stage == 5:
        if not check_num(message.text, 1, 10):
            bot.send_message(message.chat.id, 'Введите число от 1 до 10!')
            return None
        set_field_param('stage', '5', message.chat.id)
        set_field_param('hotels_num', message.text, message.chat.id)
        logger.bind(user=True).info('user {id} selected {num} hotels'.format(id=message.from_user.id, num=message.text))
        bot.send_message(message.chat.id, 'Сколько фотографий каждого отеля вы хотите посмотреть (от 0 до 5)?')

    # финальный этап. Узнаем количество фотографий для запроса, формируем и отсылаем запрос к API,
    # сохраняем историю, закрываем текущий диалог
    else:
        if not check_num(message.text, 0, 5):
            bot.send_message(message.chat.id, 'Введите число от 0 до 5!')
            return None

        bot.send_message(message.chat.id, 'Подбираем для вас варианты...')

        set_field_param('stage', '6', message.chat.id)
        set_field_param('photos_num', message.text, message.chat.id)
        logger.bind(user=True).info('user {id} selected {num} photos'.format(id=message.from_user.id, num=message.text))

        # инициализируем параметры запроса в API
        rows = select_rows('current_dialogs', 'chat_id', str(message.chat.id))
        q_type, city_id, check_in, check_out, guest_num, num_hotels, num_photos = \
            rows[0][1], rows[0][3], rows[0][4], rows[0][5], rows[0][6], rows[0][7], rows[0][8]

        # записываем запрос в историю
        city_name = select_rows('cities_code', 'city_id', str(city_id))[0][4]
        goal = {'lowprice': 'дешёвых', 'highprice': 'дорогих', 'bestdeal': 'дешёвых и близких к центру'}
        user_message = "Найди {nh} самых {gl} отелей для {gn} гостей в городе {cn}.\n" \
                       "Дата заезда: {ci}, дата отъезда: {co}.\n" \
                       "Покажи {pn} фотографий каждого отеля".format(nh=num_hotels,
                                                                     gl=goal[q_type],
                                                                     gn=guest_num,
                                                                     cn=city_name,
                                                                     ci=check_in,
                                                                     co=check_out,
                                                                     pn=num_photos)
        if q_type == 'bestdeal':
            price_range, distance_range = str(rows[0][9]), str(rows[0][10])
            add_msg = "\nВыведи отели в ценовом диапазоне {pr}, расположенные на расстоянии {dr} от " \
                      "центра города".format(pr=Dicts.prices[price_range], dr=Dicts.distances[distance_range])
            user_message += add_msg
        else:
            price_range, distance_range = '0', '0'

        set_log(message.message_id, message.chat.id, message.from_user.id, message.from_user.username, message.date,
                user_message, '')

        # запрашиваем данные
        output = hotels_list(str(city_id), q_type, check_in, check_out, str(guest_num), str(num_hotels), num_photos,
                             price_range, distance_range, 1, 0, [])
        # выдаем ответ пользователю
        # - ответ без фотографий
        if num_photos == 0:
            output_txt = ''
            for i_elem in output:
                output_txt += i_elem[0]

            answer = bot.send_message(message.chat.id, output_txt, parse_mode="HTML", disable_web_page_preview=True)
            # сохраняем историю
            set_log(answer.message_id, answer.chat.id, answer.from_user.id, answer.from_user.username, answer.date,
                    output_txt, '')
            logger.bind(user=True).info('user {id} got answer {aid} in main_log'.format(id=message.from_user.id,
                                                                                        aid=answer.message_id))
        # - ответ с фотографиями
        else:
            add_id = 1
            for i_elem in output:
                links = list()
                rows = select_rows('photos_url', 'hotel_id', str(i_elem[1]))
                for i_link in range(num_photos):
                    try:
                        links.append(rows[i_link][2])
                    except Exception as exc:
                        logger.bind(special=True).info('Ошибка при чтении фотографии из базы, error - {}'
                                                       .format(exc.__str__()))
                        continue
                # пытаемся отправить сообщение с фотографиями
                try:
                    medias = []
                    links_to_log = links[0]
                    media = telebot.types.InputMediaPhoto(links[0], caption=i_elem[0], parse_mode="HTML")
                    medias.append(media)
                    for i_link in range(1, len(links)):
                        media = telebot.types.InputMediaPhoto(links[i_link])
                        medias.append(media)
                        links_to_log += ',' + links[i_link]
                    bot.send_media_group(message.chat.id, medias)
                    # сохраняем историю
                    set_log(message.message_id + add_id, message.chat.id, 5161451101, 'HotelsVrvBot', message.date,
                            i_elem[0], links_to_log)
                    logger.bind(user=True).info('user {id} got answer {aid} '
                                                'in main_log'.format(id=message.from_user.id,
                                                                     aid=message.message_id + add_id))
                    add_id += 1
                # если был сбой и в базе пусто или произошел сбой отправки, выдаем ответ без них
                except Exception as exc:
                    logger.bind(special=True).info('Ошибка при попытке отправки медиагруппы, error - {}'
                                                   .format(exc.__str__()))
                    answer = bot.send_message(message.chat.id, i_elem[0], parse_mode="HTML",
                                              disable_web_page_preview=True)
                    # сохраняем историю
                    set_log(answer.message_id, answer.chat.id, answer.from_user.id, answer.from_user.username,
                            answer.date, i_elem[0], '')
                    logger.bind(user=True).info('user {id} got answer {aid} '
                                                'in main_log'.format(id=message.from_user.id,
                                                                     aid=message.message_id + add_id))

        # очищаем текущий диалог
        delete_row(message.chat.id)


@logger.catch
def choose_city(chat_id: int, cities: List[dict]) -> None:
    """функция формирования и отправки клавиатуры с выбором городов из найденных по запросу"""
    keyboard = telebot.types.InlineKeyboardMarkup()
    for i_city in cities:
        key = telebot.types.InlineKeyboardButton(text=i_city["caption"], callback_data=i_city["destinationId"])
        keyboard.add(key)
    bot.send_message(chat_id, 'По запросу найдено несколько городов. Выберите нужный:', reply_markup=keyboard)


@logger.catch
def choose_price(chat_id: int) -> None:
    """функция формирования и отправки клавиатуры с выбором диапазона цен"""
    # задаем стадию диалога
    set_field_param('stage', '8', chat_id)

    # формируем клавиатуру
    keyboard = telebot.types.InlineKeyboardMarkup()
    keys = Dicts.prices
    for key, value in keys.items():
        keyboard.add(telebot.types.InlineKeyboardButton(text=value, callback_data=key))

    # отправляем в чат
    bot.send_message(chat_id, 'Выберите подходящую цену за ночь:', reply_markup=keyboard)


@logger.catch
def choose_distance(chat_id: int) -> None:
    """функция формирования и отправки клавиатуры с выбором диапазона цен"""
    # задаем стадию диалога
    set_field_param('stage', '9', chat_id)

    # формируем клавиатуру
    keyboard = telebot.types.InlineKeyboardMarkup()
    keys = Dicts.distances
    for key, value in keys.items():
        keyboard.add(telebot.types.InlineKeyboardButton(text=value, callback_data=key))

    bot.send_message(chat_id, 'Выберите предпочитаемое расстояние до центра города:', reply_markup=keyboard)


@logger.catch
@bot.message_handler(content_types=['text'])
def listener(message: telebot.types.Message) -> None:
    """Функция слушает сообщения из телеги"""
    # Проверяем, существует ли активный диалог с данным пользователем
    rows = select_rows('current_dialogs', 'chat_id', str(message.chat.id))

    if len(rows) == 0:
        # Если нет, запускаем стартовое распознавание запроса
        get_text_messages(message)
        # если пользователь ввел новую команду, сбрасываем текущий диалог, стартуем с нуля
    elif message.text.startswith('/'):
        delete_row(message.chat.id)
        get_text_messages(message)
    else:
        # Если диалог найден, перебрасываем на продолжение
        dispetcher(message, rows[0][2] + 1)


@logger.catch
@bot.callback_query_handler(func=lambda call: call.data.isdigit)
def keyboard_select(c: telebot.types.CallbackQuery) -> None:
    """функция ловит ответы клавиатуры и календаря"""
    # узнаем, на какой стадии диалога мы находимся
    rows = select_rows('current_dialogs', 'chat_id', str(c.message.chat.id))

    # если диалог находится на стадии выбора одного из городов
    if rows[0][2] == 7:
        # вносим id города в текущий диалог
        set_field_param('stage', '1', c.message.chat.id)
        set_field_param('city_id', c.data, c.message.chat.id)
        # вытягиваем описание города
        city_name = select_rows('cities_code', 'city_id', c.data)[0][4]
        # сносим клавиатуру с выбором городов
        bot.edit_message_text('Выбран город {d}'.format(d=city_name), c.message.chat.id,
                              c.message.message_id, reply_markup=None)
        logger.bind(user=True).info('user {id} selected city {ct}'.format(id=c.message.from_user.id, ct=city_name))

        # если выполняется команда bestdeal, включаем сбор дополнительных данных
        if rows[0][1] == 'bestdeal':
            choose_price(c.message.chat.id)
        else:
            bot.send_message(c.message.chat.id, 'Выберите дату заезда из календаря.')
            # отсылаем в диалог календарь для выбора даты заезда
            calendar, step = DetailedTelegramCalendar(min_date=date.today() + timedelta(days=1)).build()
            bot.send_message(c.message.chat.id, f"Select {LSTEP[step]}", reply_markup=calendar)

    # если диалог на стадии выбора цен
    elif rows[0][2] == 8:
        # вносим номер диапазона цены в текущий диалог
        set_field_param('price_bestdeal', c.data, c.message.chat.id)
        # сносим клавиатуру с выбором цен
        bot.edit_message_text('Выбран диапазон цен {d}'.format(d=Dicts.prices[c.data]), c.message.chat.id,
                              c.message.message_id, reply_markup=None)
        logger.bind(user=True).info('user {id} selected price {p}'.format(id=c.message.from_user.id,
                                                                          p=Dicts.prices[c.data]))
        # переходим к выбору расстояния до центра города
        choose_distance(c.message.chat.id)

    # если диалог на стадии определения оптимального расстояния до центра
    elif rows[0][2] == 9:
        # вносим номер диапазона расстояния в текущий диалог
        set_field_param('distance_bestdeal', c.data, c.message.chat.id)
        # сносим клавиатуру с выбором расстояния
        bot.edit_message_text('Выбрано расстояние до центра {d}'.format(d=Dicts.distances[c.data]), c.message.chat.id,
                              c.message.message_id, reply_markup=None)
        logger.bind(user=True).info('user {id} selected distance {dst}'.format(id=c.message.from_user.id,
                                                                               dst=Dicts.distances[c.data]))
        # меняем стадию диалога
        set_field_param('stage', '1', c.message.chat.id)
        # отсылаем в диалог календарь для выбора даты заезда
        calendar, step = DetailedTelegramCalendar(min_date=date.today() + timedelta(days=1)).build()
        bot.send_message(c.message.chat.id, f"Select {LSTEP[step]}", reply_markup=calendar)

    # если диалог находится на стадии выбора дат
    else:
        cal(c, rows[0])


@logger.catch
def cal(c: telebot.types.CallbackQuery, row: list) -> None:
    """Функция обрабатывает ответ календаря"""
    # инсключаем из календаря лишние даты
    if row[2] == 1:
        allow_date = date.today() + timedelta(days=1)
    else:
        allow_date = datetime.strptime(row[4], '%Y-%m-%d').date() + timedelta(days=1)

    # обработка календаря
    result, key, step = DetailedTelegramCalendar(min_date=allow_date).process(c.data)
    if not result and key:
        bot.edit_message_text(f"Select {LSTEP[step]}",
                              c.message.chat.id,
                              c.message.message_id,
                              reply_markup=key)
    elif result:
        bot.edit_message_text(f"Выбрана дата {result}",
                              c.message.chat.id,
                              c.message.message_id)
        logger.bind(user=True).info('user {id} selected date {dt}'.format(id=c.message.from_user.id, dt=result))

        # инициализация переменных для этапа выбора даты заезда
        if row[2] == 1:
            stage = '2'
            field = 'check_in'
            ok_msg = 'Выберите дату отъезда из календаря.'
        # инициализация переменных для этапа выбора даты отъезда
        else:
            stage = '3'
            field = 'check_out'
            ok_msg = 'Введите количество гостей (целое число от 1 до 10).'

        # сохраняем результат
        set_field_param('stage', stage, c.message.chat.id)
        set_field_param(field, str(result), c.message.chat.id)
        bot.send_message(c.message.chat.id, ok_msg)

        # отправка в чат календаря для выбора даты отъезда
        if row[2] == 1:
            calendar, step = DetailedTelegramCalendar(min_date=allow_date).build()
            bot.send_message(c.message.chat.id, f"Select {LSTEP[step]}", reply_markup=calendar)


if __name__ == "__main__":

    init_database()
    bot.infinity_polling()
