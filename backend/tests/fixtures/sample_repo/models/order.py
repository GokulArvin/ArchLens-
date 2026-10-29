"""Order data model entity."""

class Order:
    def __init__(self, order_id: str, customer_id: str, total_amount: float):
        self.order_id = order_id
        self.customer_id = customer_id
        self.total_amount = total_amount
        self.status = "PENDING"
