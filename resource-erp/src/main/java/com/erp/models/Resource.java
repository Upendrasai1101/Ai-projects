package com.erp.models;

import com.erp.utils.JsonUtil;

import java.util.Objects;

/**
 * Domain-agnostic model of a single inventory / resource item.
 * Works equally for a laptop (Retail), a medicine strip (Pharmacy),
 * a bag of cement (Construction) or a kg of rice (Restaurant) —
 * the {@code unit} and {@code category} fields carry the domain meaning.
 */
public class Resource {

    private final int id;
    private String name;
    private String category;
    private String description;
    private String unit;
    private int quantity;
    private double buyPrice;
    private double sellPrice;
    private int reorderLevel;

    public Resource(int id, String name, String category, String description, String unit,
                     int quantity, double buyPrice, double sellPrice, int reorderLevel) {
        this.id = id;
        this.name = name;
        this.category = category;
        this.description = description;
        this.unit = unit;
        this.quantity = quantity;
        this.buyPrice = buyPrice;
        this.sellPrice = sellPrice;
        this.reorderLevel = reorderLevel;
    }

    public int getId() {
        return id;
    }

    public String getName() {
        return name;
    }

    public void setName(String name) {
        this.name = name;
    }

    public String getCategory() {
        return category;
    }

    public void setCategory(String category) {
        this.category = category;
    }

    public String getDescription() {
        return description;
    }

    public void setDescription(String description) {
        this.description = description;
    }

    public String getUnit() {
        return unit;
    }

    public void setUnit(String unit) {
        this.unit = unit;
    }

    public int getQuantity() {
        return quantity;
    }

    public void setQuantity(int quantity) {
        this.quantity = quantity;
    }

    public double getBuyPrice() {
        return buyPrice;
    }

    public void setBuyPrice(double buyPrice) {
        this.buyPrice = buyPrice;
    }

    public double getSellPrice() {
        return sellPrice;
    }

    public void setSellPrice(double sellPrice) {
        this.sellPrice = sellPrice;
    }

    public int getReorderLevel() {
        return reorderLevel;
    }

    public void setReorderLevel(int reorderLevel) {
        this.reorderLevel = reorderLevel;
    }

    public double stockValue() {
        return quantity * buyPrice;
    }

    public double potentialSaleValue() {
        return quantity * sellPrice;
    }

    public double marginPerUnit() {
        return sellPrice - buyPrice;
    }

    public boolean isLowStock() {
        return quantity <= reorderLevel;
    }

    public boolean isOutOfStock() {
        return quantity == 0;
    }

    /** Serializes this resource to a flat JSON object, for the web API. */
    public String toJson() {
        return "{"
                + "\"id\":" + id + ","
                + "\"name\":\"" + JsonUtil.escape(name) + "\","
                + "\"category\":\"" + JsonUtil.escape(category) + "\","
                + "\"description\":\"" + JsonUtil.escape(description) + "\","
                + "\"unit\":\"" + JsonUtil.escape(unit) + "\","
                + "\"quantity\":" + quantity + ","
                + "\"buyPrice\":" + buyPrice + ","
                + "\"sellPrice\":" + sellPrice + ","
                + "\"reorderLevel\":" + reorderLevel + ","
                + "\"lowStock\":" + isLowStock() + ","
                + "\"outOfStock\":" + isOutOfStock()
                + "}";
    }

    @Override
    public String toString() {
        return String.format("#%d | %-20s | %-15s | Qty:%-6d %-8s | Buy:Rs.%-10.2f | Sell:Rs.%-10.2f",
                id, name, category, quantity, unit, buyPrice, sellPrice);
    }

    @Override
    public boolean equals(Object o) {
        if (this == o) return true;
        if (!(o instanceof Resource)) return false;
        Resource resource = (Resource) o;
        return id == resource.id;
    }

    @Override
    public int hashCode() {
        return Objects.hash(id);
    }
}
