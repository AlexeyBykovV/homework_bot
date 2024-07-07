"""Финальный проект спринта 11. Бот для Телеграмма.

Бот который проверяет статус домашней работы.
"""
import logging
import os
import sys
import time
from http import HTTPStatus

import requests
from requests import RequestException
from dotenv import load_dotenv
from telebot import TeleBot
from telebot.apihelper import ApiException

from exceptions import (
    HomeworkStatusError,
    ResponseStatusError,
)


load_dotenv()

logger = logging.getLogger(__name__)

BASE_NAME = os.path.splitext(os.path.basename(__file__))[0]

PRACTICUM_TOKEN = None
TELEGRAM_TOKEN = None
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
    required_tokens = {
        'PRACTICUM_TOKEN': PRACTICUM_TOKEN,
        'TELEGRAM_TOKEN': TELEGRAM_TOKEN,
        'TELEGRAM_CHAT_ID': TELEGRAM_CHAT_ID
    }

    missing_tokens = [
        token for token, value in required_tokens.items() if value is None
    ]

    if missing_tokens:
        logger.critical(
            'Отсутствует хотя бы одна из обазательных переменных окружения.'
            'Бот завершил работу.'
        )
        raise EnvironmentError(
            f'Недостающие переменные окружения: {missing_tokens}.'
        )
    else:
        logger.info('Все необходимые переменные окружения установлены.')


def send_message(bot, message):
    """Отправляет сообщение в Telegram-чат, определяемый TELEGRAM_CHAT_ID.

    Принимает на вход два параметра:
    - экземпляр класса TeleBot
    - строку с текстом сообщения.
    """
    logger.info(f'Запущена функция отправки сообщения: {message}.')

    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.debug(f'Успешное выполнение отправки сообщения: {message}.')
        return True
    except ApiException as error:
        logger.exception(f'Произошла ошибка API Telegram: {error}.')
        return False
    except RequestException as error:
        logger.exception(f'Произошла ошибка отправки запроса: {error}.')
        return False


def get_api_answer(timestamp):
    """Делает запрос к единственному эндпоинту API-сервиса.

    В качестве параметра в функцию передаётся временная метка.
    В случае успешного запроса должна вернуть ответ API,
    приведя его из формата JSON к типам данных Python.
    """
    payload = {
        'url': ENDPOINT,
        'headers': HEADERS,
        'params': {'from_date': timestamp},
    }

    try:
        response = requests.get(**payload)
        logger.info(f'Направлен запрос к API:{payload}')

    except RequestException as error:
        logger.exception('Ошибка подключения к API:')
        raise ResponseStatusError(
            f'Во время подключения к эндпоинту {payload['url']} '
            f'произошла ошибка: {error} '
            f'Параметры: {payload['headers'], payload['params']}'
        ) from error

    if response.status_code != HTTPStatus.OK:
        error_message = (
            f'Обнаружена ошибка в ответе сервера: '
            f'Параметры запроса: {payload} '
            f'Код ответа сервера: {response.status_code} '
            f'Причина: {response.reason} '
            f'Контекст: {response.text}'
        )
        logger.error(error_message)
        raise ResponseStatusError(error_message) from None

    logger.info(f'Успешный запрос к API: {payload}')
    return response.json()


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

    if 'homeworks' not in response or 'current_date' not in response:
        raise KeyError('Отсутствие ожидаемых ключей в ответе API.')

    homeworks = response['homeworks']

    if not homeworks:
        logger.debug('Список домашних работ пуст. Статус не изменился.')

    if not isinstance(homeworks, list):
        raise TypeError(
            'В ответе API под ключом `homeworks` данные не в виде списка'
            f'Ожидался тип данных list, получен {type(homeworks).__name__}'
        )

    return homeworks


def parse_status(homework):
    """Извлекает из информации о конкретной домашней работе статус этой работы.

    В качестве параметра функция получает только один элемент
    из списка домашних работ. В случае успеха функция возвращает
    подготовленную для отправки в Telegram строку, содержащую
    один из вердиктов словаря HOMEWORK_VERDICTS.
    """
    if 'homework_name' not in homework:
        raise KeyError('Получено пустое значение по ключу "homework_name".')

    homework_name = homework['homework_name']
    homework_status = homework['status']

    if homework_status not in HOMEWORK_VERDICTS:
        raise HomeworkStatusError(
            f'Неожиданный статус домашней работы: {homework_status}'
            )

    verdict = HOMEWORK_VERDICTS[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    check_tokens()
    bot = TeleBot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    error_reported = False

    while True:
        try:
            response = get_api_answer(timestamp)
            homeworks = check_response(response)
            if homeworks:
                status = parse_status(homeworks[0])
                send_message(bot, status)
            timestamp = response.get('current_date', timestamp)
            error_reported = False
        except Exception as error:
            message = f'Произошел сбой в работе программы: {error}'
            logger.error(message)
            if not error_reported:
                send_message(bot, message)
                error_reported = True
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    logger.setLevel(logging.DEBUG)
    logger.addHandler(logging.FileHandler(f'{BASE_NAME}.log'))
    logger.addHandler(logging.StreamHandler(sys.stdout))
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    for handler in logger.handlers:
        handler.setFormatter(formatter)

    main()
