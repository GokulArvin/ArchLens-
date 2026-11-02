package repositories;

import models.Order;

/**
 * OrderRepository handles persistence for orders.
 */
public class OrderRepository {
    public Order findById(String orderId) {
        return new Order(orderId, null, 0.0);
    }

    public Order save(String orderId, String customerId, double amount) {
        return new Order(orderId, customerId, amount);
    }
}
