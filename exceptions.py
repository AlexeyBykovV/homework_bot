"""Набор ошибок."""


class ResponseStatusError(Exception):
    """Ошибка ответа от сервера."""


class HomeworkStatusError(Exception):
    """Ошибка статуса домашней работы."""


class MessageSendError(Exception):
    """Ошибка отправки сообщения в Telegram."""
