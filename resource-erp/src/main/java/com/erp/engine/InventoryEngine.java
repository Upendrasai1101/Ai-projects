package com.erp.engine;

import com.erp.models.Resource;
import com.erp.models.Transaction;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Optional;

/**
 * Core CRUD + stock-movement engine. Domain-agnostic: works identically
 * regardless of which {@code IndustryProfile} is active, since all domain
 * meaning lives in the {@link Resource} fields (category/unit) rather than
 * in this engine's logic.
 */
public class InventoryEngine {

    private final List<Resource> resources = new ArrayList<>();
    private final List<Transaction> transactions = new ArrayList<>();
    private int idCounter = 1000;

    // ---------------------------------------------------------------- CRUD

    public Resource addResource(String name, String category, String description, String unit,
                                 int quantity, double buyPrice, double sellPrice, int reorderLevel) {
        int id = ++idCounter;
        Resource resource = new Resource(id, name, category, description, unit,
                quantity, buyPrice, sellPrice, reorderLevel);
        resources.add(resource);
        log(Transaction.Type.ADD, resource, quantity, quantity * buyPrice, "Initial stock on creation");
        return resource;
    }

    public List<Resource> getAll() {
        return resources;
    }

    public Optional<Resource> findById(int id) {
        return resources.stream().filter(r -> r.getId() == id).findFirst();
    }

    public List<Resource> searchByName(String keyword) {
        String needle = keyword.toLowerCase();
        List<Resource> matches = new ArrayList<>();
        for (Resource r : resources) {
            if (r.getName().toLowerCase().contains(needle) || r.getCategory().toLowerCase().contains(needle)) {
                matches.add(r);
            }
        }
        return matches;
    }

    public boolean updateResource(int id, String name, String category, String description,
                                   String unit, double buyPrice, double sellPrice, int reorderLevel) {
        Optional<Resource> found = findById(id);
        if (found.isEmpty()) {
            return false;
        }
        Resource r = found.get();
        if (name != null && !name.isBlank()) r.setName(name);
        if (category != null && !category.isBlank()) r.setCategory(category);
        if (description != null && !description.isBlank()) r.setDescription(description);
        if (unit != null && !unit.isBlank()) r.setUnit(unit);
        if (buyPrice >= 0) r.setBuyPrice(buyPrice);
        if (sellPrice >= 0) r.setSellPrice(sellPrice);
        if (reorderLevel >= 0) r.setReorderLevel(reorderLevel);
        log(Transaction.Type.UPDATE, r, 0, 0, "Resource details updated");
        return true;
    }

    public boolean deleteResource(int id) {
        Optional<Resource> found = findById(id);
        if (found.isEmpty()) {
            return false;
        }
        Resource r = found.get();
        resources.remove(r);
        log(Transaction.Type.DELETE, r, -r.getQuantity(), 0, "Resource removed from inventory");
        return true;
    }

    // ---------------------------------------------------------- Stock ops

    public boolean stockIn(int id, int addQty, String note) {
        Optional<Resource> found = findById(id);
        if (found.isEmpty() || addQty <= 0) {
            return false;
        }
        Resource r = found.get();
        r.setQuantity(r.getQuantity() + addQty);
        log(Transaction.Type.STOCK_IN, r, addQty, addQty * r.getBuyPrice(), note);
        return true;
    }

    /** Returns -1 = not found, -2 = insufficient stock, 0 = success. */
    public int stockOut(int id, int removeQty, String note) {
        Optional<Resource> found = findById(id);
        if (found.isEmpty()) {
            return -1;
        }
        Resource r = found.get();
        if (removeQty <= 0 || removeQty > r.getQuantity()) {
            return -2;
        }
        r.setQuantity(r.getQuantity() - removeQty);
        double saleAmount = removeQty * r.getSellPrice();
        log(Transaction.Type.STOCK_OUT, r, -removeQty, saleAmount, note);
        return 0;
    }

    // -------------------------------------------------------------- Alerts

    public List<Resource> getLowStock() {
        List<Resource> low = new ArrayList<>();
        for (Resource r : resources) {
            if (r.isLowStock()) {
                low.add(r);
            }
        }
        low.sort(Comparator.comparingInt(Resource::getQuantity));
        return low;
    }

    // --------------------------------------------------------- Statistics

    public int getTotalResourceCount() {
        return resources.size();
    }

    public int getTotalQuantity() {
        int total = 0;
        for (Resource r : resources) total += r.getQuantity();
        return total;
    }

    public double getTotalStockValue() {
        double total = 0;
        for (Resource r : resources) total += r.stockValue();
        return total;
    }

    public double getTotalPotentialSaleValue() {
        double total = 0;
        for (Resource r : resources) total += r.potentialSaleValue();
        return total;
    }

    public List<String> getUniqueCategories() {
        List<String> categories = new ArrayList<>();
        for (Resource r : resources) {
            if (!categories.contains(r.getCategory())) {
                categories.add(r.getCategory());
            }
        }
        return categories;
    }

    // -------------------------------------------------------- Transactions

    public List<Transaction> getTransactions() {
        return transactions;
    }

    /** Builds a compact plain-text summary of the whole inventory, suitable for AI prompts. */
    public String buildInventorySummaryForAI() {
        StringBuilder sb = new StringBuilder();
        for (Resource r : resources) {
            sb.append(String.format("- %s | Category: %s | Qty: %d %s | Buy: Rs.%.2f | Sell: Rs.%.2f | Reorder Level: %d%s%n",
                    r.getName(), r.getCategory(), r.getQuantity(), r.getUnit(), r.getBuyPrice(), r.getSellPrice(),
                    r.getReorderLevel(), r.isLowStock() ? " [LOW STOCK]" : ""));
        }
        if (sb.length() == 0) {
            sb.append("(inventory is currently empty)");
        }
        return sb.toString();
    }

    /** Builds a compact plain-text log of recent transactions, suitable for the fraud audit AI prompt. */
    public String buildTransactionLogForAI(int maxEntries) {
        StringBuilder sb = new StringBuilder();
        int start = Math.max(0, transactions.size() - maxEntries);
        for (int i = start; i < transactions.size(); i++) {
            sb.append(transactions.get(i).toLogLine()).append('\n');
        }
        if (sb.length() == 0) {
            sb.append("(no transactions recorded yet)");
        }
        return sb.toString();
    }

    private void log(Transaction.Type type, Resource r, int qtyDelta, double amount, String note) {
        transactions.add(new Transaction(type, r.getId(), r.getName(), qtyDelta, amount, note));
    }
}
