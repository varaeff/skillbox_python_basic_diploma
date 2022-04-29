import requests
import json
from decouple import config
import sqlite3
from typing import Union, List, Any
from botrequests import history

headers = {"X-RapidAPI-Host": config('API_HOST'),
           "X-RapidAPI-Key": config('API_KEY')}


def hotels_list(city_id: str, check_in: str, check_out: str, guest_num: str, num_hotels: str, num_photos: int) -> List:
    """запрос к API для команды /lowprice"""
    url = "https://hotels4.p.rapidapi.com/properties/list"
    querystring = {"destinationId": city_id,
                   "pageNumber": "1",
                   "pageSize": num_hotels,
                   "checkIn": check_in,
                   "checkOut": check_out,
                   "adults1": guest_num,
                   "sortOrder": "PRICE",
                   "locale": "ru_RU",
                   "currency": "RUB"}

    # делаем запрос для команды lowprice
    response = requests.request("GET", url, headers=headers, params=querystring)
    resp_data = json.loads(response.text)
    resp = []

    try:
        # собираем в список данные для вывода об отеле плюс id отеля
        for i_elem in resp_data["data"]["body"]["searchResults"]["results"]:
            resp_text = '<b>Отель:</b> ' + i_elem["name"] + '\n' + \
                         '<b>Адрес:</b> ' + i_elem["address"]["locality"] + ', ' \
                         + i_elem["address"]["streetAddress"] + '\n' + \
                         '<b>Цена за сутки:</b> ' + i_elem["ratePlan"]["price"]["current"] + '\n' +  \
                         '<a href=\'https://www.hotels.com/ho' + str(i_elem["id"]) + '\'>Посмотреть на сайте</a>' + \
                         '\n\n'
            # если пользователь хочет фоток, сохраняем фотки по отелю в базу
            if num_photos > 0:
                try:
                    history.save_photos(str(i_elem["id"]))
                except Exception as exc:
                    history.errors_log('func - save_photos: ' + exc.__str__())
            resp.append([resp_text, i_elem["id"]])
    except Exception as exc:
        history.errors_log('func - hotels_list: ' + exc.__str__())
        resp.append(['По вашему запросу ничего не найдено.', 0])

    return resp


def city_destination_id(city: str) -> Union[int, None]:
    """запрос к API, пытаемся узнать id города по наименованию"""
    url = "https://hotels4.p.rapidapi.com/locations/v2/search"
    querystring = {"query": city}
    response = requests.request("GET", url, headers=headers, params=querystring)
    try:
        return response.json()["suggestions"][0]["entities"][0]["destinationId"]
    except Exception as exc:
        history.errors_log('func - city_destination_id: ' + exc.__str__())
        return None


def bd_update(query: str) -> None:
    """запуск запроса на апдейт базы"""
    connection = sqlite3.connect('bot_data.db')
    cursor = connection.cursor()
    cursor.execute(query)
    connection.commit()
    connection.close()


def bd_select(query: str) -> List[Any]:
    """запуск запроса на селект из базы"""
    connection = sqlite3.connect('bot_data.db')
    cursor = connection.cursor()
    cursor.execute(query)
    rows = cursor.fetchall()
    connection.commit()
    connection.close()
    return rows
