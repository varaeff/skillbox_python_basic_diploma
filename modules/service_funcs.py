from loguru import logger
import math


@logger.catch
def check_num(check_data: str, min_num: int, max_num: int) -> bool:
    """Функция проверяет, что в диалоге было введено число в указанном диапазоне"""
    try:
        num = int(check_data)
    except ValueError as exc:
        logger.bind(special=True).info('Попытка некорректного ввода: error - {}'.format(exc.__str__()))
        return False
    if not min_num <= num <= max_num:
        return False
    return True


@logger.catch
def distance(llat1: float, llong1: float, llat2: float, llong2: float) -> float:
    """функция вычисления расстояния по модифицированной формуле гаверсинусов"""
    # радиус сферы(Земли)
    rad = 6372795
    # в радианах
    lat1 = llat1 * math.pi / 180.
    lat2 = llat2 * math.pi / 180.
    long1 = llong1 * math.pi / 180.
    long2 = llong2 * math.pi / 180.
    # косинусы и синусы широт и разницы долгот
    cl1 = math.cos(lat1)
    cl2 = math.cos(lat2)
    sl1 = math.sin(lat1)
    sl2 = math.sin(lat2)
    delta = long2 - long1
    cdelta = math.cos(delta)
    sdelta = math.sin(delta)
    # вычисления длины большого круга
    y = math.sqrt(math.pow(cl2 * sdelta, 2) + math.pow(cl1 * sl2 - sl1 * cl2 * cdelta, 2))
    x = sl1 * sl2 + cl1 * cl2 * cdelta
    ad = math.atan2(y, x)
    dist = ad * rad

    return round(dist / 1000, 3)


class Dicts:
    prices = {"1": "0 - 2000 руб.",
              "2": "2000 руб. - 4000 руб.",
              "3": "4000 руб. - 6000 руб.",
              "4": "6000 руб. - 8000 руб.",
              "5": "8000+ руб."}
    distances = {"1": "не дальше 1 км.",
                 "2": "не дальше 2 км.",
                 "3": "не дальше 5 км.",
                 "4": "не дальше 10 км.",
                 "5": "не дальше 30 км."}
    price_min = {"2": "2000",
                 "3": "4000",
                 "4": "6000",
                 "5": "8000"}
    price_max = {"1": "2000",
                 "2": "4000",
                 "3": "6000",
                 "4": "8000"}
    distance_max = {"1": 1, "2": 2, "3": 5, "4": 10, "5": 30}
