package models;

/**
 * Order is the core domain entity.
 */
public class Order {
    private String id;
    private String customerId;
    private double amount;

    public Order(String id, String customerId, double amount) {
        this.id = id;
        this.customerId = customerId;
        this.amount = amount;
    }

    public String getId() { return id; }
    public String getCustomerId() { return customerId; }
    public double getAmount() { return amount; }
}
