"""Order business logic service."""
from repositories.order_repository import OrderRepository
from models.order import Order

class OrderService:
    def __init__(self, repo: OrderRepository):
        self.repo = repo

    def create_order(self, order_id: str, customer_id: str, amount: float) -> Order:
        order = Order(order_id, customer_id, amount)
        return self.repo.save(order)
