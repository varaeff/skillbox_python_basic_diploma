import json
from datetime import datetime
from typing import List, Union

import requests
from decouple import config
from loguru import logger

from modules.db_work import insert_row, select_rows
from modules.service_funcs import Dicts, distance

headers = {"X-RapidAPI-Host": config('API_HOST'),
           "X-RapidAPI-Key": config('API_KEY')}


@logger.catch
def hotels_list(city_id: str, q_type: str, check_in: str, check_out: str, guest_num: str, num_hotels: str,
                num_photos: int, price_bstd: str, dist_bstd: str, page: int, found: int, resp: List) -> List:
    """запрос к API для подбора отелей"""
    sort_order = {'lowprice': "PRICE", 'highprice': "PRICE_HIGHEST_FIRST", 'bestdeal': "PRICE"}

    url = "https://hotels4.p.rapidapi.com/properties/list"
    querystring = {"destinationId": city_id,
                   "pageNumber": str(page),
                   "pageSize": num_hotels,
                   "checkIn": check_in,
                   "checkOut": check_out,
                   "adults1": guest_num,
                   "sortOrder": sort_order[q_type],
                   "locale": "ru_RU",
                   "currency": "RUB"}
    dist_max = 30
    if q_type == 'bestdeal':
        querystring["pageSize"] = '25'
        if price_bstd != '1':
            querystring["priceMin"] = Dicts.price_min[price_bstd]
        if price_bstd != '5':
            querystring["priceMax"] = Dicts.price_max[price_bstd]
        if dist_bstd != '5':
            dist_max = Dicts.distance_max[dist_bstd]

    # вытаскиваем координаты центра города
    rows = select_rows('cities_code', 'city_id', city_id)
    city_lat, city_long = rows[0][2], rows[0][3]

    # считаем количество ночей проживания
    nights = (datetime.strptime(check_out, "%Y-%m-%d") - datetime.strptime(check_in, "%Y-%m-%d")).days

    # делаем запрос на поиск отелей
    try:
        response = requests.request("GET", url, headers=headers, params=querystring)
        resp_data = json.loads(response.text)
    except Exception as exc:
        logger.bind(special=True).info('Ошибка при поиске отелей, error - {}'.format(exc.__str__()))
        resp.append(['По вашему запросу ничего не найдено.', 0])
        return resp

    # собираем в список данные для вывода об отеле плюс id отеля
    for i_elem in resp_data["data"]["body"]["searchResults"]["results"]:
        if found == int(num_hotels):
            break
        try:
            dist = distance(i_elem["coordinate"]["lat"], i_elem["coordinate"]["lon"], city_lat, city_long)
            if q_type == 'bestdeal' and not dist <= dist_max:
                continue

            resp_text = '<b>Отель:</b> ' + i_elem["name"] + '\n' + \
                        '<b>Адрес:</b> ' + i_elem["address"]["locality"] + ', ' \
                        + i_elem["address"]["streetAddress"] + '\n' + '<b>Расстояние до центра:</b> ' \
                        + str(dist) + ' км\n' + \
                        '<b>Цена за сутки:</b> ' + str(i_elem["ratePlan"]["price"]["exactCurrent"]) + ' RUB\n' + \
                        '<b>Всего:</b> ' + str(round(i_elem["ratePlan"]["price"]["exactCurrent"] * nights, 2)) + \
                        ' RUB\n' + '<a href=\'https://www.hotels.com/ho' + str(i_elem["id"]) + \
                        '\'>Посмотреть на сайте</a>' + '\n\n'
        except Exception as exc:
            logger.bind(special=True).info('Ошибка при сборе информации об отеле id={id}, error - {er}'
                                           .format(id=i_elem["id"], er=exc.__str__()))
            resp_text = 'Произошла ошибка при сборе информации об отеле!\n<a href=\'https://www.hotels.com/ho' + \
                        str(i_elem["id"]) + '\'>Уточните детали на сайте</a>' + \
                        '\n\n'
        resp.append([resp_text, i_elem["id"]])
        found += 1

        # если пользователь хочет фоток, сохраняем фотки по отелю в базу
        if num_photos > 0:
            try:
                save_photos(str(i_elem["id"]))
            except Exception as exc:
                logger.bind(special=True).info('Ошибка при попытке сохранения фотографий, error - {}'
                                               .format(exc.__str__()))

    # если при команде bestdeal 25 отелей не хватило для формирования выборки,
    # повторяем запрос для следующих 25 отелей
    if found < int(num_hotels):
        try:
            next_page = resp_data["data"]["body"]["searchResults"]["pagination"]["nextPageNumber"]
        except Exception as exc:
            logger.bind(special=True).info('Следующая страница в выборке отсутствует, error - {}'
                                           .format(exc.__str__()))
            next_page = 0
        if page < next_page < 11:
            resp = hotels_list(city_id, q_type, check_in, check_out, guest_num, num_hotels, num_photos, price_bstd,
                               dist_bstd, page + 1, found, resp)
        elif found == 0:
            resp.append(['По вашему запросу ничего не найдено.', 0])
        else:
            resp.append(['К сожалению, это всё, что нашлось по запросу.', 0])
    return resp


@logger.catch
def city_destination_id(city: str) -> Union[List[dict], None]:
    """запрос к API, пытаемся узнать id города по наименованию"""
    url = "https://hotels4.p.rapidapi.com/locations/v2/search"
    querystring = {"query": city}
    try:
        response = requests.request("GET", url, headers=headers, params=querystring)
        members = response.json()["suggestions"][0]["entities"]
        cities = []
        city = {}
        for i_dict in members:
            if i_dict["type"] == "CITY":
                city["destinationId"] = i_dict["destinationId"]
                city["latitude"] = i_dict["latitude"]
                city["longitude"] = i_dict["longitude"]

                # убираем разметку из описания города
                caption = ''
                copy = True
                for i_letter in i_dict["caption"]:
                    if i_letter == '<':
                        copy = False
                    elif i_letter == '>':
                        copy = True
                    else:
                        if copy:
                            caption += i_letter

                city["caption"] = caption
                cities.append(city)
                city = {}
        return cities
    except Exception as exc:
        logger.bind(special=True).info('Город по запросу не найден, error - {}'.format(exc.__str__()))
        return None


@logger.catch
def save_photos(hotel_id: str) -> None:
    """сохранение фотографий отеля в БД"""
    # проверяем БД на наличие фоток отеля. Если есть, выходим из функции
    rows = select_rows('photos_url', 'hotel_id', str(hotel_id))
    if len(rows) > 0:
        return None

    # запрашиваем данные
    url = "https://hotels4.p.rapidapi.com/properties/get-hotel-photos"
    querystring = {"id": hotel_id}
    try:
        response = requests.request("GET", url, headers=headers, params=querystring)
        resp_data = json.loads(response.text)
    except Exception as exc:
        logger.bind(special=True).info('Фотографии по запросу не найдены, error - {}'.format(exc.__str__()))
        resp_data = None

    # 5 первых фоток сохраняем в БД
    if resp_data is not None:
        num = 0
        for i_elem in resp_data["hotelImages"]:
            values = {'id': hotel_id, 'ph_id': i_elem["imageId"], 'url': i_elem["baseUrl"].format(size='w')}
            insert_row('photos_url', ':id, :ph_id, :url', values)
            num += 1
            if num == 5:
                break
