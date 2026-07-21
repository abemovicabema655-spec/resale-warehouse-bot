from aiogram.fsm.state import State, StatesGroup

class PurchaseStates(StatesGroup):
    name = State()
    size = State()
    quantity = State()
    purchase_price = State()
    sale_price = State()

class ReplenishStates(StatesGroup):
    quantity = State()

class SearchStates(StatesGroup):
    waiting_for_query = State()

class EditPriceStates(StatesGroup):
    purchase_price = State()
    sale_price = State()

class ResetStates(StatesGroup):
    confirm = State()