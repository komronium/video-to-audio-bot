from aiogram.fsm.state import State, StatesGroup


class PromoStates(StatesGroup):
    choosing_type = State()
    entering_value = State()
    entering_hours = State()
    entering_label = State()
    confirming = State()
