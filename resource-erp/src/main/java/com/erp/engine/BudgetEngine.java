package com.erp.engine;

import java.time.LocalDate;
import java.time.temporal.ChronoUnit;
import java.util.ArrayList;
import java.util.List;

/**
 * Tracks a monthly/project budget cap against actual spend, and provides
 * the calculations behind the Burn Rate & Cost Variance Matrix, the Smart
 * Purchase Guard, and Economic Order Quantity (EOQ) cost optimization.
 */
public class BudgetEngine {

    /** A single recorded spend event, e.g. a stock purchase. */
    public static class Expense {
        final String description;
        final double amount;
        final LocalDate date;

        public Expense(String description, double amount, LocalDate date) {
            this.description = description;
            this.amount = amount;
            this.date = date;
        }

        public String getDescription() { return description; }
        public double getAmount() { return amount; }
        public LocalDate getDate() { return date; }
    }

    private double budgetCap;
    private final LocalDate periodStart;
    private LocalDate periodEnd;
    private final List<Expense> expenses = new ArrayList<>();

    public BudgetEngine(double budgetCap, int periodLengthDays) {
        this.budgetCap = budgetCap;
        this.periodStart = LocalDate.now();
        this.periodEnd = periodStart.plusDays(periodLengthDays);
    }

    public double getBudgetCap() {
        return budgetCap;
    }

    public void setBudgetCap(double budgetCap) {
        this.budgetCap = budgetCap;
    }

    public LocalDate getPeriodStart() {
        return periodStart;
    }

    public LocalDate getPeriodEnd() {
        return periodEnd;
    }

    public void setPeriodEnd(LocalDate periodEnd) {
        this.periodEnd = periodEnd;
    }

    public void recordExpense(String description, double amount) {
        expenses.add(new Expense(description, amount, LocalDate.now()));
    }

    public List<Expense> getExpenses() {
        return expenses;
    }

    public double getTotalSpent() {
        double total = 0;
        for (Expense e : expenses) total += e.amount;
        return total;
    }

    public double getRemainingBudget() {
        return budgetCap - getTotalSpent();
    }

    public double getUtilizationPercent() {
        if (budgetCap <= 0) return 0;
        return (getTotalSpent() / budgetCap) * 100.0;
    }

    /** Average spend per elapsed day since the period started. */
    public double getDailyBurnRate() {
        long daysElapsed = Math.max(1, ChronoUnit.DAYS.between(periodStart, LocalDate.now()) + 1);
        return getTotalSpent() / daysElapsed;
    }

    /** Projected total spend by period end, based on the current burn rate. */
    public double getProjectedSpendAtCurrentRate() {
        long totalDays = Math.max(1, ChronoUnit.DAYS.between(periodStart, periodEnd));
        return getDailyBurnRate() * totalDays;
    }

    /** Positive = under budget projection, Negative = projected overspend. */
    public double getCostVariance() {
        return budgetCap - getProjectedSpendAtCurrentRate();
    }

    /**
     * Smart Purchase Guard: checks whether a proposed purchase would breach
     * the remaining budget. Returns true if the purchase is SAFE to proceed.
     */
    public boolean canAfford(double proposedCost) {
        return proposedCost <= getRemainingBudget();
    }

    /** Economic Order Quantity: sqrt( (2 * annualDemand * orderingCost) / holdingCostPerUnit ). */
    public static double calculateEOQ(int annualDemand, double orderingCost, double holdingCostPerUnit) {
        if (holdingCostPerUnit <= 0) {
            return 0;
        }
        return Math.sqrt((2.0 * annualDemand * orderingCost) / holdingCostPerUnit);
    }

    public String buildBudgetSummary() {
        return String.format(
                "Budget Cap: Rs.%.2f | Spent: Rs.%.2f (%.1f%%) | Remaining: Rs.%.2f | " +
                "Daily Burn Rate: Rs.%.2f | Projected Period Spend: Rs.%.2f | Variance: Rs.%.2f%s",
                budgetCap, getTotalSpent(), getUtilizationPercent(), getRemainingBudget(),
                getDailyBurnRate(), getProjectedSpendAtCurrentRate(), getCostVariance(),
                getCostVariance() < 0 ? " (PROJECTED OVERSPEND)" : " (on track)"
        );
    }
}
