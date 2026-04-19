from aiogram.fsm.state import State, StatesGroup


class GiveDiamondsStates(StatesGroup):
    waiting_for_user_id = State()
    waiting_for_count = State()
