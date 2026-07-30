package com.erp.models;

import com.erp.utils.JsonUtil;

import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;

/**
 * Immutable record of a single inventory movement (stock-in, stock-out,
 * creation, update, deletion). Used both for the human-readable transaction
 * log and as raw data fed into the AI Fraud & Stock Leakage Audit report.
 */
public class Transaction {

    public enum Type { ADD, UPDATE, DELETE, STOCK_IN, STOCK_OUT }

    private static final DateTimeFormatter FORMAT = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");

    private final LocalDateTime timestamp;
    private final Type type;
    private final int resourceId;
    private final String resourceName;
    private final int quantityDelta;
    private final double amount;
    private final String note;

    public Transaction(Type type, int resourceId, String resourceName, int quantityDelta,
                        double amount, String note) {
        this.timestamp = LocalDateTime.now();
        this.type = type;
        this.resourceId = resourceId;
        this.resourceName = resourceName;
        this.quantityDelta = quantityDelta;
        this.amount = amount;
        this.note = note;
    }

    public LocalDateTime getTimestamp() {
        return timestamp;
    }

    public Type getType() {
        return type;
    }

    public int getResourceId() {
        return resourceId;
    }

    public String getResourceName() {
        return resourceName;
    }

    public int getQuantityDelta() {
        return quantityDelta;
    }

    public double getAmount() {
        return amount;
    }

    public String getNote() {
        return note;
    }

    /** Compact one-line representation used both on-screen and when sent to the AI service. */
    public String toLogLine() {
        return String.format("[%s] %s | Resource: %s (#%d) | Qty Change: %+d | Amount: Rs.%.2f | %s",
                timestamp.format(FORMAT), type, resourceName, resourceId, quantityDelta, amount, note);
    }

    /** Serializes this transaction to a flat JSON object, for the web API. */
    public String toJson() {
        return "{"
                + "\"timestamp\":\"" + timestamp.format(FORMAT) + "\","
                + "\"type\":\"" + type + "\","
                + "\"resourceId\":" + resourceId + ","
                + "\"resourceName\":\"" + JsonUtil.escape(resourceName) + "\","
                + "\"quantityDelta\":" + quantityDelta + ","
                + "\"amount\":" + amount + ","
                + "\"note\":\"" + JsonUtil.escape(note) + "\""
                + "}";
    }

    @Override
    public String toString() {
        return toLogLine();
    }
}
