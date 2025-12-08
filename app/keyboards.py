from aiogram.types import (ReplyKeyboardMarkup, KeyboardButton,
                           InlineKeyboardMarkup, InlineKeyboardButton)


main = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text='Задать вопрос')],
        [KeyboardButton(text='о банке')],
        [
            KeyboardButton(text='кнопка00'),
            KeyboardButton(text='кнопка01')
        ]
    ],
    resize_keyboard=True,
    input_field_placeholder='Выберите пункт меню...'
)


question = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text='Как отменить операцию', callback_data='cancel')],
        [InlineKeyboardButton(text='Как заблокировать карту', callback_data='block')]
    ]
)


get_number = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text='отправить номер', request_contact=True)]],
    resize_keyboard=True
)
