package com.erp.web;

import com.erp.engine.BudgetEngine;
import com.erp.engine.InventoryEngine;
import com.erp.models.IndustryProfile;
import com.erp.services.AIService;

/**
 * Holds all mutable state for one browser session: the active industry
 * profile, its InventoryEngine/BudgetEngine, and an AIService bound to
 * that profile's context. Mirrors exactly what the console Main.java
 * holds as static fields, just scoped per session instead of per process.
 */
public class AppSession {

    private final String id;
    private IndustryProfile profile;
    private final InventoryEngine inventory = new InventoryEngine();
    private BudgetEngine budget;
    private final AIService ai;

    public AppSession(String id, IndustryProfile profile, double budgetCap, int budgetDays) {
        this.id = id;
        this.profile = profile;
        this.budget = new BudgetEngine(budgetCap, Math.max(1, budgetDays));
        this.ai = new AIService(profile);
        seedSampleData();
    }

    private void seedSampleData() {
        String[] items = profile.getSampleItems();
        String unit = profile.getDefaultUnit();
        for (String item : items) {
            int qty = 20 + (int) (Math.random() * 80);
            double buy = 50 + Math.random() * 500;
            double sell = buy * (1.15 + Math.random() * 0.35);
            inventory.addResource(item, profile.getDisplayName(), "Sample seeded item", unit,
                    qty, round2(buy), round2(sell), 15);
        }
    }

    public String getId() {
        return id;
    }

    public IndustryProfile getProfile() {
        return profile;
    }

    public void switchProfile(IndustryProfile profile) {
        this.profile = profile;
        this.ai.setActiveProfile(profile);
    }

    public InventoryEngine getInventory() {
        return inventory;
    }

    public BudgetEngine getBudget() {
        return budget;
    }

    public AIService getAi() {
        return ai;
    }

    private static double round2(double value) {
        return Math.round(value * 100.0) / 100.0;
    }
}
