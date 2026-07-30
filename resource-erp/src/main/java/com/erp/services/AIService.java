package com.erp.services;

import com.erp.models.IndustryProfile;
import com.erp.utils.EnvLoader;
import com.erp.utils.JsonUtil;

import java.io.IOException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;

/**
 * Thin wrapper around Groq's OpenAI-compatible "chat/completions" REST
 * endpoint using only {@code java.net.http.HttpClient} — no external SDK
 * or JSON library.
 *
 * Every prompt is automatically prefixed with the active {@link IndustryProfile}
 * context (sent as a system message) so that responses stay grounded in the
 * correct business domain.
 */
public class AIService {

    private static final String API_URL = "https://api.groq.com/openai/v1/chat/completions";

    private final HttpClient httpClient;
    private final String apiKey;
    private final String model;
    private IndustryProfile activeProfile;

    public AIService(IndustryProfile activeProfile) {
        this.activeProfile = activeProfile;
        this.apiKey = EnvLoader.get("GROQ_API_KEY");
        this.model = EnvLoader.get("GROQ_MODEL", "openai/gpt-oss-20b");
        this.httpClient = HttpClient.newBuilder()
                .connectTimeout(Duration.ofSeconds(15))
                .build();
    }

    public void setActiveProfile(IndustryProfile profile) {
        this.activeProfile = profile;
    }

    public boolean isConfigured() {
        return apiKey != null && !apiKey.isBlank();
    }

    /**
     * Sends a domain-grounded prompt to Groq and returns the plain-text reply.
     * Never throws for API/network failures — instead returns a clear,
     * human-readable error string so console menus stay robust.
     */
    public String ask(String userPrompt) {
        if (!isConfigured()) {
            return "AI features are disabled: GROQ_API_KEY is not set. " +
                   "Copy .env.example to .env and add your key.";
        }

        String systemPrompt = buildSystemPrompt();

        String requestBody = "{"
                + "\"model\":\"" + JsonUtil.escape(model) + "\","
                + "\"messages\":[" +
                    "{\"role\":\"system\",\"content\":\"" + JsonUtil.escape(systemPrompt) + "\"}," +
                    "{\"role\":\"user\",\"content\":\"" + JsonUtil.escape(userPrompt) + "\"}" +
                  "],"
                + "\"temperature\":0.4,"
                + "\"max_tokens\":1024"
                + "}";

        try {
            HttpRequest request = HttpRequest.newBuilder()
                    .uri(URI.create(API_URL))
                    .timeout(Duration.ofSeconds(30))
                    .header("Content-Type", "application/json")
                    .header("Authorization", "Bearer " + apiKey)
                    .POST(HttpRequest.BodyPublishers.ofString(requestBody))
                    .build();

            HttpResponse<String> response = httpClient.send(request, HttpResponse.BodyHandlers.ofString());

            if (response.statusCode() != 200) {
                String errMsg = JsonUtil.extractField(response.body(), "message");
                return "AI request failed (HTTP " + response.statusCode() + "): " +
                        (errMsg != null ? errMsg : response.body());
            }

            String text = JsonUtil.extractField(response.body(), "content");
            return text != null ? text.trim() : "AI returned an empty response.";

        } catch (IOException e) {
            return "AI request failed: network error (" + e.getMessage() + ")";
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            return "AI request was interrupted.";
        }
    }

    private String buildSystemPrompt() {
        String domainContext = activeProfile != null
                ? "You are an AI operations advisor embedded inside an ERP system for " + activeProfile.getAiContext()
                : "You are an AI operations advisor embedded inside a general-purpose resource management ERP system.";

        return domainContext + "\n\n" +
                "Respond concisely and practically, formatted for a plain-text console (no markdown tables, " +
                "light use of '-' bullets is fine). Avoid unnecessary preamble.";
    }

    // ===================== Feature-specific prompt builders =====================

    public String businessAdvisor(String inventorySummary) {
        return ask("Act as a Business Advisor. Analyze this inventory snapshot and provide: " +
                "(1) 3 key business insights, (2) stock clearance suggestions for slow movers, " +
                "(3) one growth opportunity.\n\nInventory Snapshot:\n" + inventorySummary);
    }

    public String reorderEmail(String supplierHint, String itemName, int currentQty, int reorderLevel, int suggestedOrderQty) {
        return ask("Draft a formal, ready-to-send purchase order email to a supplier" +
                (supplierHint != null && !supplierHint.isBlank() ? " (" + supplierHint + ")" : "") +
                " to reorder stock. Item: " + itemName + ", current stock: " + currentQty +
                ", reorder level: " + reorderLevel + ", suggested order quantity: " + suggestedOrderQty +
                ". Include a subject line, professional greeting, item details table in plain text, and sign-off " +
                "as 'Procurement Team'.");
    }

    public String naturalLanguageQuery(String question, String inventorySummary) {
        return ask("Answer this natural-language inventory question using ONLY the data provided below. " +
                "If the data doesn't contain the answer, say so plainly.\n\n" +
                "Question: " + question + "\n\nInventory Data:\n" + inventorySummary);
    }

    public String autoCategorizeAndDescribe(String itemName) {
        return ask("For the new item named \"" + itemName + "\", respond in exactly two lines:\n" +
                "Category: <one short category name>\n" +
                "Description: <one concise 15-25 word product description>");
    }

    public String fraudAuditReport(String transactionLog) {
        return ask("Act as an internal auditor. Analyze this transaction log for signs of stock leakage, " +
                "unexpected stock-outs, unusual quantity patterns, or margin anomalies. List concrete red flags " +
                "with the specific transaction referenced, then give an overall risk rating (Low/Medium/High).\n\n" +
                "Transaction Log:\n" + transactionLog);
    }

    public String purchaseGuardStrategy(String itemName, double orderCost, double remainingBudget, double budgetCap) {
        return ask("A planned purchase of \"" + itemName + "\" costing Rs." + String.format("%.2f", orderCost) +
                " would exceed the available budget. Remaining budget: Rs." + String.format("%.2f", remainingBudget) +
                " out of a cap of Rs." + String.format("%.2f", budgetCap) + ". " +
                "Suggest 3 concrete AI auto-reallocation strategies (e.g. partial order, alternate vendor, " +
                "phased delivery, budget reallocation from another category) to resolve this responsibly.");
    }

    public String costOptimizer(String itemName, int annualDemand, double orderingCost, double holdingCostPerUnit) {
        double eoq = 0;
        if (holdingCostPerUnit > 0) {
            eoq = Math.sqrt((2.0 * annualDemand * orderingCost) / holdingCostPerUnit);
        }
        return ask("For item \"" + itemName + "\": estimated annual demand = " + annualDemand +
                " units, ordering cost per order = Rs." + orderingCost + ", holding cost per unit/year = Rs." +
                holdingCostPerUnit + ". A calculated Economic Order Quantity (EOQ) of approximately " +
                String.format("%.1f", eoq) + " units was derived. Explain what this EOQ means in practice, and " +
                "give 2 alternate-vendor negotiation insights to reduce total cost.");
    }
}
