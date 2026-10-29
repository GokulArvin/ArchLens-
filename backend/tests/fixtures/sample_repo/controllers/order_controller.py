"""Order controller exposing API endpoints."""
from services.order_service import OrderService
from repositories.order_repository import OrderRepository  # Architectural violation: direct repo access from controller!
from models.order import Order

class OrderController:
    def __init__(self, service: OrderService, repo: OrderRepository):
        self.service = service
        self.repo = repo

    def handle_create(self, order_id: str, customer_id: str, amount: float):
        return self.service.create_order(order_id, customer_id, amount)

    def handle_direct_lookup(self, order_id: str):
        # Bypasses service layer
        return self.repo.find_by_id(order_id)
