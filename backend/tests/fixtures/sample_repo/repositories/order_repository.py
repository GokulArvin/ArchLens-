"""Order repository for database access."""
from models.order import Order
from typing import Optional, Dict

class OrderRepository:
    def __init__(self):
        self._db: Dict[str, Order] = {}

    def save(self, order: Order) -> Order:
        self._db[order.order_id] = order
        return order

    def find_by_id(self, order_id: str) -> Optional[Order]:
        return self._db.get(order_id)
