package services;

import repositories.OrderRepository;

/**
 * OrderService contains the business logic for orders.
 */
public class OrderService {
    private OrderRepository repository;

    public OrderService(OrderRepository repository) {
        this.repository = repository;
    }

    public Object createOrder(String orderId, String customerId, double amount) {
        return repository.save(orderId, customerId, amount);
    }
}
