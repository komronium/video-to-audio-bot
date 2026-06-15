from aiogram.fsm.state import State, StatesGroup


class PostStates(StatesGroup):
    choosing_segment = State()
    waiting_for_post = State()
    confirming = State()
