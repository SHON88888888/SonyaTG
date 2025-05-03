# states.py — Определение состояний конечного автомата (FSM) для взаимодействия с пользователем

from aiogram.fsm.state import State, StatesGroup

# ChannelState — класс для управления этапами настройки канала и редактирования данных
# Используется в FSM: /start → forward → редактирование промпта или плана

class ChannelState(StatesGroup):
    waiting_for_forward = State()    # Ожидание пересланного сообщения из канала
    editing_prompt = State()        # Состояние ввода нового промпта пользователем
    editing_plan = State()          # Состояние ввода нового контент-плана
