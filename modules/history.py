from modules.db_work import BDqueries
from loguru import logger
from datetime import datetime
from typing import List


@logger.catch
def set_log(message_id: int,
            chat_id: int,
            user_id: int,
            username: str,
            message_date: int,
            msg_text: str,
            photos: str) -> None:
    """добавление данных в историю"""
    try:
        values = {'ms_id': str(message_id), 'ch_id': str(chat_id), 'us_id': str(user_id), 'us_n': username,
                  'ms_dt': str(message_date), 'ms_txt': msg_text, 'ph': photos}
        BDqueries.insert_row('main_log', ':ms_id, :ch_id, :us_id, :us_n, :ms_dt, :ms_txt, :ph', values)
    except Exception as exc:
        logger.bind(special=True).info('Ошибка при попытке добавления данных в историю, error - {}'
                                       .format(exc.__str__()))


@logger.catch
def get_history(chat_id: int) -> List[List[str]]:
    """запрос истории переписки"""
    rows = BDqueries.select_rows('main_log', 'chat_id', str(chat_id))

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
