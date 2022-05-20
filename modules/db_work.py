import sqlite3
from typing import Any, List

from loguru import logger


@logger.catch
class BD:
    """подключение к базе"""
    def __init__(self, db_name):
        self.db_name = db_name

    def __enter__(self):
        self.connection = sqlite3.connect(self.db_name)
        self.cursor = self.connection.cursor()
        return self.cursor

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.connection.commit()
        self.connection.close()


@logger.catch
def bd_update(query: str, values: dict) -> None:
    """запуск запроса на апдейт базы"""
    with BD('bot_data.db') as bd:
        bd.execute(query, values)


@logger.catch
def bd_select(query: str, values: dict) -> List[Any]:
    """запуск запроса на селект из базы"""
    with BD('bot_data.db') as bd:
        bd.execute(query, values)
        rows = bd.fetchall()
        return rows


@logger.catch
def init_database() -> None:
    """Функция проверяет в БД наличие таблиц и создает их в случае отсутствия"""
    # история диалогов с пользователями
    bd_update('''CREATE TABLE IF NOT EXISTS main_log
                        (message_id INTEGER PRIMARY KEY, 
                         chat_id INTEGER, 
                         user_id INTEGER, 
                         username TEXT, 
                         date INTEGER, 
                         text TEXT,
                         photos TEXT)''', {})
    # открытые на данный момент диалоги
    bd_update('''CREATE TABLE IF NOT EXISTS current_dialogs
                         (chat_id INTEGER, 
                          query_type TEXT,
                          stage INTEGER, 
                          city_id INTEGER, 
                          check_in TEXT, 
                          check_out TEXT, 
                          guests_num INTEGER, 
                          hotels_num INTEGER, 
                          photos_num INTEGER,
                          price_bestdeal INTEGER,
                          distance_bestdeal INTEGER)''', {})
    # города, по которым уже производился поиск
    bd_update('''CREATE TABLE IF NOT EXISTS cities_code
                        (city_id INTEGER, 
                         city_name TEXT,
                         latitude REAL,
                         longitude REAL,
                         caption TEXT)''', {})
    # фотографии отелей, по которым была выдача
    bd_update('''CREATE TABLE IF NOT EXISTS photos_url
                        (hotel_id INTEGER, 
                         photo_id INTEGER,
                         photo_url TEXT)''', {})


@logger.catch
def set_field_param(field: str, param: str, chat_id: int) -> None:
    query = "UPDATE current_dialogs SET {fld} = :par WHERE chat_id = :id".format(fld=field)
    values = {'par': param, 'id': str(chat_id)}
    bd_update(query, values)


@logger.catch
def delete_row(chat_id: int) -> None:
    query = "DELETE FROM current_dialogs WHERE chat_id = :id"
    values = {'id': str(chat_id)}
    bd_update(query, values)


@logger.catch
def insert_row(table: str, val_str: str, values: dict) -> None:
    query = "INSERT INTO {tbl} VALUES ({vls})".format(tbl=table, vls=val_str)
    bd_update(query, values)


@logger.catch
def select_rows(table: str, field: str, val: str) -> List[List]:
    query = "SELECT * FROM {tbl} WHERE {fld} = :val".format(tbl=table, fld=field)
    values = {'val': val}
    rows = bd_select(query, values)
    return rows
