package com.erp;

import com.erp.engine.BudgetEngine;
import com.erp.engine.InventoryEngine;
import com.erp.models.IndustryProfile;
import com.erp.models.Resource;
import com.erp.models.Transaction;
import com.erp.services.AIService;

import java.util.List;
import java.util.Locale;
import java.util.Scanner;

/**
 * Console entry point for the Universal AI-Powered Resource & Budget ERP System.
 */
public class Main {

    private static final Scanner sc = new Scanner(System.in);
    private static InventoryEngine inventory;
    private static BudgetEngine budget;
    private static AIService ai;
    private static IndustryProfile activeProfile;

    public static void main(String[] args) {
        printBanner();
        selectProfile();
        seedSampleData();
        setupBudget();

        ai = new AIService(activeProfile);
        if (!ai.isConfigured()) {
            System.out.println("\n[!] GROQ_API_KEY not found. AI features will show a setup notice until " +
                    "you configure .env (see .env.example).");
        }

        int choice;
        do {
            showMainMenu();
            choice = readInt("Enter choice: ");
            handleChoice(choice);
        } while (choice != 0);

        System.out.println("\nThank you for using the Universal Resource & Budget ERP System. Goodbye!");
    }

    // ============================================================= SETUP

    private static void printBanner() {
        System.out.println("==================================================================");
        System.out.println("   UNIVERSAL AI-POWERED RESOURCE & BUDGET ERP SYSTEM");
        System.out.println("   Pure Java 11+  |  Groq REST API  |  Multi-Domain Engine");
        System.out.println("==================================================================");
    }

    private static void selectProfile() {
        IndustryProfile.printMenu();
        IndustryProfile chosen = null;
        while (chosen == null) {
            int choice = readInt("Enter choice (1-" + IndustryProfile.values().length + "): ");
            chosen = IndustryProfile.fromChoice(choice);
            if (chosen == null) {
                System.out.println("Invalid choice, please try again.");
            }
        }
        activeProfile = chosen;
        System.out.println("\n[OK] Active Profile: " + activeProfile.getDisplayName());
    }

    private static void seedSampleData() {
        inventory = new InventoryEngine();
        String[] items = activeProfile.getSampleItems();
        String unit = activeProfile.getDefaultUnit();
        for (String item : items) {
            int qty = 20 + (int) (Math.random() * 80);
            double buy = 50 + Math.random() * 500;
            double sell = buy * (1.15 + Math.random() * 0.35);
            inventory.addResource(item, activeProfile.getDisplayName(), "Sample seeded item", unit,
                    qty, round2(buy), round2(sell), 15);
        }
        System.out.println("[OK] Loaded " + items.length + " sample resources for this domain.");
    }

    private static void setupBudget() {
        System.out.println("\n--- Budget Setup ---");
        double cap = readDouble("Enter your Monthly/Project Budget Cap: Rs.");
        int days = readInt("Enter budget period length in days (e.g. 30): ");
        budget = new BudgetEngine(cap, Math.max(1, days));
        System.out.println("[OK] Budget cap set to Rs." + cap + " over " + days + " days.");
    }

    // ============================================================== MENU

    private static void showMainMenu() {
        System.out.println("\n===================== MAIN MENU (" + activeProfile.getDisplayName() + ") =====================");
        System.out.println(" -- Core Resource Management --");
        System.out.println("  1.  Add New Resource");
        System.out.println("  2.  View All Resources");
        System.out.println("  3.  Search Resource");
        System.out.println("  4.  Update Resource");
        System.out.println("  5.  Delete Resource");
        System.out.println("  6.  Stock In (Add Stock)");
        System.out.println("  7.  Stock Out (Consume/Sell)");
        System.out.println("  8.  Low Stock Alerts");
        System.out.println("  9.  View Transaction Log");
        System.out.println(" 10.  View Statistics");
        System.out.println(" -- Budget & Cost Control --");
        System.out.println(" 11.  View Budget Dashboard (Burn Rate / Variance)");
        System.out.println(" 12.  Record a Purchase (Smart Purchase Guard)");
        System.out.println(" 13.  Cost Optimizer (EOQ + Vendor Insights)");
        System.out.println(" -- Groq AI Features --");
        System.out.println(" 14.  AI Industry Business Advisor");
        System.out.println(" 15.  AI Supplier Reorder Email Generator");
        System.out.println(" 16.  AI Smart Natural Language Query");
        System.out.println(" 17.  AI Auto-Categorizer & Description Writer");
        System.out.println(" 18.  AI Fraud & Stock Leakage Audit Report");
        System.out.println(" -- System --");
        System.out.println(" 19.  Switch Industry Profile");
        System.out.println("  0.  Exit");
        System.out.println("=================================================================================");
        System.out.println("Total Resources: " + inventory.getTotalResourceCount() +
                " | Budget Remaining: Rs." + round2(budget.getRemainingBudget()));
    }

    private static void handleChoice(int choice) {
        switch (choice) {
            case 1: addResource(); break;
            case 2: viewAllResources(); break;
            case 3: searchResource(); break;
            case 4: updateResource(); break;
            case 5: deleteResource(); break;
            case 6: stockIn(); break;
            case 7: stockOut(); break;
            case 8: lowStockAlerts(); break;
            case 9: viewTransactions(); break;
            case 10: viewStatistics(); break;
            case 11: viewBudgetDashboard(); break;
            case 12: recordPurchase(); break;
            case 13: costOptimizer(); break;
            case 14: aiBusinessAdvisor(); break;
            case 15: aiReorderEmail(); break;
            case 16: aiNaturalLanguageQuery(); break;
            case 17: aiAutoCategorize(); break;
            case 18: aiFraudAudit(); break;
            case 19: selectProfile(); ai.setActiveProfile(activeProfile); break;
            case 0: break;
            default: System.out.println("Invalid choice! Try again.");
        }
    }

    // ===================================================== CORE FEATURES

    private static void addResource() {
        System.out.println("\n========== ADD NEW RESOURCE ==========");
        System.out.print("Name: ");
        String name = sc.nextLine();
        System.out.print("Category: ");
        String category = sc.nextLine();
        System.out.print("Unit (e.g. " + activeProfile.getDefaultUnit() + "): ");
        String unit = sc.nextLine();
        int qty = readInt("Quantity: ");
        double buy = readDouble("Buy Price: Rs.");
        double sell = readDouble("Sell Price: Rs.");
        int reorderLevel = readInt("Reorder Level (low-stock threshold): ");

        if (qty < 0 || buy < 0 || sell < 0 || reorderLevel < 0) {
            System.out.println("Invalid values!");
            return;
        }

        System.out.print("Description (leave blank to auto-generate with AI): ");
        String description = sc.nextLine();
        if (description.isBlank()) {
            System.out.println("Generating description with AI...");
            String aiResult = ai.autoCategorizeAndDescribe(name);
            System.out.println("AI Suggestion:\n" + aiResult);
            description = aiResult;
        }

        Resource r = inventory.addResource(name, category, description, unit, qty, buy, sell, reorderLevel);
        System.out.println("\n[OK] Resource added successfully! ID: " + r.getId());
    }

    private static void viewAllResources() {
        System.out.println("\n========== ALL RESOURCES ==========");
        List<Resource> all = inventory.getAll();
        if (all.isEmpty()) {
            System.out.println("No resources in inventory!");
            return;
        }
        for (Resource r : all) {
            System.out.println(r + (r.isLowStock() ? "  [LOW STOCK]" : ""));
        }
        System.out.println("Total: " + all.size() + " resources.");
    }

    private static void searchResource() {
        System.out.print("\nEnter search keyword (name or category): ");
        String keyword = sc.nextLine();
        List<Resource> matches = inventory.searchByName(keyword);
        if (matches.isEmpty()) {
            System.out.println("No matches found.");
            return;
        }
        matches.forEach(System.out::println);
    }

    private static void updateResource() {
        int id = readInt("\nEnter Resource ID to update: ");
        System.out.print("New Name (blank = keep): ");
        String name = sc.nextLine();
        System.out.print("New Category (blank = keep): ");
        String category = sc.nextLine();
        System.out.print("New Description (blank = keep): ");
        String description = sc.nextLine();
        System.out.print("New Unit (blank = keep): ");
        String unit = sc.nextLine();
        double buy = readDouble("New Buy Price (-1 = keep): Rs.");
        double sell = readDouble("New Sell Price (-1 = keep): Rs.");
        int reorderLevel = readInt("New Reorder Level (-1 = keep): ");

        boolean ok = inventory.updateResource(id, name, category, description, unit, buy, sell, reorderLevel);
        System.out.println(ok ? "[OK] Resource updated." : "Resource not found.");
    }

    private static void deleteResource() {
        int id = readInt("\nEnter Resource ID to delete: ");
        boolean ok = inventory.deleteResource(id);
        System.out.println(ok ? "[OK] Resource deleted." : "Resource not found.");
    }

    private static void stockIn() {
        int id = readInt("\nEnter Resource ID: ");
        int qty = readInt("Enter quantity to add: ");
        boolean ok = inventory.stockIn(id, qty, "Manual stock-in");
        System.out.println(ok ? "[OK] Stock added." : "Invalid resource ID or quantity.");
    }

    private static void stockOut() {
        int id = readInt("\nEnter Resource ID: ");
        int qty = readInt("Enter quantity to remove: ");
        int result = inventory.stockOut(id, qty, "Manual stock-out");
        if (result == -1) {
            System.out.println("Resource not found.");
        } else if (result == -2) {
            System.out.println("Invalid quantity or insufficient stock.");
        } else {
            System.out.println("[OK] Stock removed.");
            inventory.findById(id).ifPresent(r -> {
                if (r.isLowStock()) {
                    System.out.println("[WARNING] Low stock: only " + r.getQuantity() + " " + r.getUnit() + " left.");
                }
            });
        }
    }

    private static void lowStockAlerts() {
        System.out.println("\n========== LOW STOCK ALERTS ==========");
        List<Resource> low = inventory.getLowStock();
        if (low.isEmpty()) {
            System.out.println("All resources have sufficient stock!");
            return;
        }
        for (Resource r : low) {
            String tag = r.isOutOfStock() ? "OUT OF STOCK" : (r.getQuantity() <= r.getReorderLevel() / 2 ? "CRITICAL" : "LOW");
            System.out.println(r + "  [" + tag + "]");
        }
    }

    private static void viewTransactions() {
        System.out.println("\n========== TRANSACTION LOG ==========");
        List<Transaction> tx = inventory.getTransactions();
        if (tx.isEmpty()) {
            System.out.println("No transactions yet!");
            return;
        }
        for (int i = 0; i < tx.size(); i++) {
            System.out.println((i + 1) + ". " + tx.get(i));
        }
        System.out.println("Total Transactions: " + tx.size());
    }

    private static void viewStatistics() {
        System.out.println("\n========== INVENTORY STATISTICS ==========");
        if (inventory.getTotalResourceCount() == 0) {
            System.out.println("No resources in inventory!");
            return;
        }
        double stockValue = inventory.getTotalStockValue();
        double saleValue = inventory.getTotalPotentialSaleValue();
        System.out.printf("Total Resources       : %d%n", inventory.getTotalResourceCount());
        System.out.printf("Total Quantity         : %d%n", inventory.getTotalQuantity());
        System.out.printf("Categories             : %d%n", inventory.getUniqueCategories().size());
        System.out.printf("Low Stock Items        : %d%n", inventory.getLowStock().size());
        System.out.printf("Total Stock Value       : Rs.%.2f%n", stockValue);
        System.out.printf("Potential Sale Value    : Rs.%.2f%n", saleValue);
        System.out.printf("Potential Profit        : Rs.%.2f%n", saleValue - stockValue);
    }

    // =================================================== BUDGET FEATURES

    private static void viewBudgetDashboard() {
        System.out.println("\n========== BUDGET DASHBOARD ==========");
        System.out.println("Period: " + budget.getPeriodStart() + " to " + budget.getPeriodEnd());
        System.out.println(budget.buildBudgetSummary());
        if (budget.getCostVariance() < 0) {
            System.out.println("[ALERT] Projected spend exceeds budget cap. Consider using Cost Optimizer " +
                    "or the AI Business Advisor for reallocation ideas.");
        }
    }

    private static void recordPurchase() {
        System.out.println("\n========== RECORD PURCHASE (Smart Purchase Guard) ==========");
        System.out.print("Item / description: ");
        String desc = sc.nextLine();
        double cost = readDouble("Purchase cost: Rs.");

        if (budget.canAfford(cost)) {
            budget.recordExpense(desc, cost);
            System.out.println("[OK] Purchase recorded. " + budget.buildBudgetSummary());
        } else {
            System.out.println("[BLOCKED] This purchase of Rs." + cost + " exceeds your remaining budget of Rs." +
                    round2(budget.getRemainingBudget()) + "!");
            System.out.println("Consulting AI for auto-reallocation strategies...\n");
            String advice = ai.purchaseGuardStrategy(desc, cost, budget.getRemainingBudget(), budget.getBudgetCap());
            System.out.println(advice);

            System.out.print("\nOverride and record anyway? (y/n): ");
            String override = sc.nextLine();
            if (override.equalsIgnoreCase("y")) {
                budget.recordExpense(desc, cost);
                System.out.println("[OK] Purchase recorded despite exceeding budget.");
            } else {
                System.out.println("Purchase cancelled.");
            }
        }
    }

    private static void costOptimizer() {
        System.out.println("\n========== COST OPTIMIZER (EOQ) ==========");
        System.out.print("Item name: ");
        String name = sc.nextLine();
        int annualDemand = readInt("Estimated annual demand (units): ");
        double orderingCost = readDouble("Ordering cost per order: Rs.");
        double holdingCost = readDouble("Holding cost per unit per year: Rs.");

        double eoq = BudgetEngine.calculateEOQ(annualDemand, orderingCost, holdingCost);
        System.out.printf("%nCalculated EOQ: %.1f units per order%n", eoq);

        System.out.println("\nAsking AI for vendor negotiation insights...\n");
        String advice = ai.costOptimizer(name, annualDemand, orderingCost, holdingCost);
        System.out.println(advice);
    }

    // ======================================================= AI FEATURES

    private static void aiBusinessAdvisor() {
        System.out.println("\n========== AI INDUSTRY BUSINESS ADVISOR ==========");
        System.out.println("Analyzing inventory for " + activeProfile.getDisplayName() + "...\n");
        String result = ai.businessAdvisor(inventory.buildInventorySummaryForAI());
        System.out.println(result);
    }

    private static void aiReorderEmail() {
        System.out.println("\n========== AI SUPPLIER REORDER EMAIL GENERATOR ==========");
        int id = readInt("Enter Resource ID to reorder: ");
        var found = inventory.findById(id);
        if (found.isEmpty()) {
            System.out.println("Resource not found.");
            return;
        }
        Resource r = found.get();
        System.out.print("Supplier name/hint (optional): ");
        String supplier = sc.nextLine();
        int suggestedQty = Math.max(r.getReorderLevel() * 3, 10);

        System.out.println("\nGenerating email...\n");
        String email = ai.reorderEmail(supplier, r.getName(), r.getQuantity(), r.getReorderLevel(), suggestedQty);
        System.out.println(email);
    }

    private static void aiNaturalLanguageQuery() {
        System.out.println("\n========== AI SMART NATURAL LANGUAGE QUERY ==========");
        System.out.print("Ask a question about your inventory (plain English): ");
        String question = sc.nextLine();
        System.out.println("\nThinking...\n");
        String answer = ai.naturalLanguageQuery(question, inventory.buildInventorySummaryForAI());
        System.out.println(answer);
    }

    private static void aiAutoCategorize() {
        System.out.println("\n========== AI AUTO-CATEGORIZER & DESCRIPTION WRITER ==========");
        System.out.print("Enter a new item name: ");
        String name = sc.nextLine();
        System.out.println("\nGenerating...\n");
        String result = ai.autoCategorizeAndDescribe(name);
        System.out.println(result);
    }

    private static void aiFraudAudit() {
        System.out.println("\n========== AI FRAUD & STOCK LEAKAGE AUDIT REPORT ==========");
        System.out.println("Analyzing recent transactions...\n");
        String result = ai.fraudAuditReport(inventory.buildTransactionLogForAI(100));
        System.out.println(result);
    }

    // ============================================================ HELPERS

    private static int readInt(String prompt) {
        while (true) {
            System.out.print(prompt);
            String line = sc.nextLine().trim();
            try {
                return Integer.parseInt(line);
            } catch (NumberFormatException e) {
                System.out.println("Please enter a valid whole number.");
            }
        }
    }

    private static double readDouble(String prompt) {
        while (true) {
            System.out.print(prompt);
            String line = sc.nextLine().trim();
            try {
                return Double.parseDouble(line);
            } catch (NumberFormatException e) {
                System.out.println("Please enter a valid number.");
            }
        }
    }

    private static double round2(double value) {
        return Math.round(value * 100.0) / 100.0;
    }
}
