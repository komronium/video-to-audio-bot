from aiogram.fsm.state import State, StatesGroup


class PostStates(StatesGroup):
    waiting_for_post = State()
