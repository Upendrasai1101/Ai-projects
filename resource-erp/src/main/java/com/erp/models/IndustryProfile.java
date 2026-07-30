package com.erp.models;

/**
 * Represents an active industry/domain profile. Every AI prompt sent to
 * Gemini is enriched with the {@link #getAiContext()} description so that
 * the model's responses stay relevant to the selected business domain.
 */
public enum IndustryProfile {

    RETAIL_IT(
            "Retail / IT Hardware Store",
            "a Retail and IT Hardware store selling electronics, computer components, " +
            "accessories and consumer gadgets. Resources are typically tracked in 'units' or 'pieces'. " +
            "Consider fast-moving consumer electronics trends, warranty cycles, and seasonal demand " +
            "(festive sales, back-to-school) when giving advice.",
            new String[] { "Laptop", "Mouse", "Keyboard", "Monitor", "SSD Drive" },
            "units"
    ),
    PHARMACY(
            "Pharmacy & Healthcare",
            "a Pharmacy and Healthcare supplies business managing medicines, medical " +
            "consumables and healthcare equipment. Resources are tracked in 'strips', 'bottles', 'boxes' " +
            "or 'units'. Consider expiry dates, batch/lot tracking, drug scheduling, cold-chain storage " +
            "requirements and regulatory compliance (e.g. controlled substances) when giving advice.",
            new String[] { "Paracetamol 500mg", "Amoxicillin Syrup", "Insulin Vial", "Surgical Gloves (Box)" },
            "strips/units"
    ),
    CONSTRUCTION(
            "Construction Engineering",
            "a Construction Engineering firm managing bulk building materials and site " +
            "resources such as cement, steel, sand, bricks, and heavy equipment. Resources are tracked in " +
            "'bags', 'tons', 'cubic meters' or 'units'. Consider project-based budgeting, material wastage " +
            "rates, site logistics, and bulk-vendor negotiation when giving advice.",
            new String[] { "Cement (OPC 53 Grade)", "TMT Steel Bars", "River Sand", "Red Bricks" },
            "bags/tons"
    ),
    RESTAURANT(
            "Restaurant & Cloud Kitchen",
            "a Restaurant and Cloud Kitchen business managing perishable raw ingredients, " +
            "packaging material and kitchen supplies. Resources are tracked in 'kg', 'liters', 'packets' " +
            "or 'units'. Consider perishability and shelf life, daily consumption patterns, food-cost " +
            "percentage targets, and supplier freshness guarantees when giving advice.",
            new String[] { "Basmati Rice", "Chicken Breast", "Cooking Oil", "Takeaway Boxes" },
            "kg/liters"
    );

    private final String displayName;
    private final String aiContext;
    private final String[] sampleItems;
    private final String defaultUnit;

    IndustryProfile(String displayName, String aiContext, String[] sampleItems, String defaultUnit) {
        this.displayName = displayName;
        this.aiContext = aiContext;
        this.sampleItems = sampleItems;
        this.defaultUnit = defaultUnit;
    }

    public String getDisplayName() {
        return displayName;
    }

    /** Domain description injected into every Gemini prompt for context grounding. */
    public String getAiContext() {
        return aiContext;
    }

    public String[] getSampleItems() {
        return sampleItems;
    }

    public String getDefaultUnit() {
        return defaultUnit;
    }

    public static void printMenu() {
        System.out.println("\nSelect your Industry Profile:");
        IndustryProfile[] values = values();
        for (int i = 0; i < values.length; i++) {
            System.out.println("  " + (i + 1) + ". " + values[i].getDisplayName());
        }
    }

    public static IndustryProfile fromChoice(int choice) {
        IndustryProfile[] values = values();
        if (choice < 1 || choice > values.length) {
            return null;
        }
        return values[choice - 1];
    }
}
