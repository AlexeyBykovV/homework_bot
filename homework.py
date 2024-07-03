import logging
import os
import sys
import time
from http import HTTPStatus

import requests
from dotenv import load_dotenv
from telebot import TeleBot

from exceptions import (
    HomeworkStatusError,
    ResponseStatusError,
    MessageSendError
)


load_dotenv()

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='log.log',
    level=logging.DEBUG,
)

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def check_tokens():
    """Проверяет доступность переменных окружения.

    Которые необходимы для работы программы. Если отсутствует хотя бы одна
    переменная окружения — продолжать работу бота нет смысла.
    """
    TOKENS = (PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID)
    return all(TOKENS)


def send_message(bot, message):
    """Отправляет сообщение в Telegram-чат, определяемый TELEGRAM_CHAT_ID.

    Принимает на вход два параметра:
    - экземпляр класса TeleBot
    - строку с текстом сообщения.
    """
    logging.info(f'Запущена функция отправки сообщения: {message}.')
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
    except MessageSendError as error:
        logging.error(f'Произошел сбой при отправке сообщения: {error}.')
    else:
        logging.debug(f'Успешное выполнение отправки сообщения: {message}.')


def get_api_answer(timestamp):
    """Делает запрос к единственному эндпоинту API-сервиса.

    В качестве параметра в функцию передаётся временная метка.
    В случае успешного запроса должна вернуть ответ API,
    приведя его из формата JSON к типам данных Python.
    """
    payload = {'from_date': timestamp}

    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=payload)
        logging.info(f'Направлен запрос к API:{payload, HEADERS, ENDPOINT}')

        if response.status_code == HTTPStatus.OK:
            homework = response.json()
            if not homework['homeworks']:
                logging.debug(
                    'Список домашних работ пуст. Статус не изменился.'
                )
            return homework
        else:
            raise ResponseStatusError(
                f'Обнаружена ошибка в ответе сервера: '
                f'Параметры запроса: {payload, HEADERS, ENDPOINT} '
                f'Код ответа сервера: {response.status_code} '
                f'Причина: {response.reason} '
                f'Контекст: {response.text}'
            )

    except Exception as error:
        raise Exception(
            f'Во время подлючения к ендпоинту {ENDPOINT}'
            f'произошла ошибка: {error}'
            f'Параметры: {HEADERS, payload}'
        )


def check_response(response):
    """Проверяет ответ API на соответствие документации.

    Из урока «API сервиса Практикум Домашка».
    В качестве параметра функция получает ответ API,
    приведённый к типам данных Python.
    """
    if not isinstance(response, dict):
        raise TypeError(
            'В ответе API структура данных не соответствует ожиданиям:'
            f'Ожидался тип данных dict, получен {type(response).__name__}'
        )

    homeworks = response.get('homeworks')
    current_date = response.get('current_date')

    if not isinstance(homeworks, list):
        raise TypeError(
            'В ответе API под ключом `homeworks` данные не в виде списка'
            f'Ожидался тип данных list, получен {type(homeworks).__name__}'
        )

    if homeworks is None or current_date is None:
        raise KeyError('Отсутствие ожидаемых ключей в ответе API.')

    return homeworks


def parse_status(homework):
    """Извлекает из информации о конкретной домашней работе статус этой работы.

    В качестве параметра функция получает только один элемент
    из списка домашних работ. В случае успеха функция возвращае
    подготовленную для отправки в Telegram строку, содержащую
    один из вердиктов словаря HOMEWORK_VERDICTS.
    """
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')

    if not homework_name:
        raise KeyError(f'Получено пустое значение по ключу {homework_name}')

    if homework_status not in HOMEWORK_VERDICTS:
        message = 'Неожиданный статус домашней работы.'
        logging.error('Неожиданный статус домашней работы.')
        raise HomeworkStatusError(message)

    verdict = HOMEWORK_VERDICTS[homework_status]
    logging.info(f'Изменился статус проверки работы {homework_name}.{verdict}')
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    bot = TeleBot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())

    if not check_tokens():
        logging.critical('Отсутствует хотя бы одна из переменных окружения')
        sys.exit('Бот завершил работу')

    while True:
        try:
            response = get_api_answer(timestamp)
            homeworks = check_response(response)
            if homeworks:
                status = parse_status(homeworks[0])
                send_message(bot, status)
            timestamp = response['current_date']
        except Exception as error:
            message = f'Произошел сбой в работе программы: {error}'
            logging.error(message)
            send_message(bot, message)
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
