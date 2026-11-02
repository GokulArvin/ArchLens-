package controllers;

import services.OrderService;
import repositories.OrderRepository;   // Architectural violation: controller bypasses service layer

/**
 * OrderController exposes HTTP-like order endpoints.
 * Note: direct import of OrderRepository is an intentional architectural violation
 * (controller should only access the service layer, not the repository directly).
 */
public class OrderController {
    private OrderService service;
    private OrderRepository repository;

    public OrderController(OrderService service, OrderRepository repository) {
        this.service = service;
        this.repository = repository;
    }

    public Object handleCreate(String orderId, String customerId, double amount) {
        return service.createOrder(orderId, customerId, amount);
    }

    public Object handleDirectLookup(String orderId) {
        // Bypasses service layer — intentional architectural violation
        return repository.findById(orderId);
    }
}
