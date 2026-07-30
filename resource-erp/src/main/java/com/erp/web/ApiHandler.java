package com.erp.web;

import com.erp.engine.BudgetEngine;
import com.erp.engine.InventoryEngine;
import com.erp.models.IndustryProfile;
import com.erp.models.Resource;
import com.erp.models.Transaction;
import com.erp.services.AIService;
import com.erp.utils.JsonUtil;
import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpHandler;

import java.io.IOException;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;

/**
 * Routes every {@code /api/*} request to the right engine call and writes
 * back a small hand-built JSON response (via {@link JsonUtil}). One handler,
 * manual routing by path + method — no framework, per the project's
 * "pure Java" constraint.
 */
public class ApiHandler implements HttpHandler {

    private final SessionManager sessions;

    public ApiHandler(SessionManager sessions) {
        this.sessions = sessions;
    }

    @Override
    public void handle(HttpExchange exchange) throws IOException {
        try {
            String path = exchange.getRequestURI().getPath();
            String method = exchange.getRequestMethod();
            Map<String, String> query = parseQuery(exchange.getRequestURI().getRawQuery());
            String body = readBody(exchange);

            // ---- Endpoints that don't require an existing session ----
            if (path.equals("/api/profiles") && method.equals("GET")) {
                respond(exchange, 200, profilesJson());
                return;
            }
            if (path.equals("/api/session") && method.equals("POST")) {
                handleCreateSession(exchange, body);
                return;
            }

            // ---- Everything below requires a valid sessionId ----
            String sessionId = query.get("sessionId");
            AppSession session = sessions.get(sessionId);
            if (session == null) {
                respond(exchange, 401, error("No active session. Start a new session first."));
                return;
            }

            InventoryEngine inv = session.getInventory();
            BudgetEngine budget = session.getBudget();
            AIService ai = session.getAi();

            if (path.equals("/api/state") && method.equals("GET")) {
                respond(exchange, 200, stateJson(session));

            } else if (path.equals("/api/profile/switch") && method.equals("POST")) {
                Integer profileId = JsonUtil.extractInt(body, "profileId");
                IndustryProfile p = profileId != null ? IndustryProfile.fromChoice(profileId) : null;
                if (p == null) {
                    respond(exchange, 400, error("Invalid profileId"));
                } else {
                    session.switchProfile(p);
                    respond(exchange, 200, stateJson(session));
                }

            } else if (path.equals("/api/resources") && method.equals("GET")) {
                respond(exchange, 200, resourcesJson(inv.getAll()));

            } else if (path.equals("/api/resources") && method.equals("POST")) {
                handleAddResource(exchange, body, inv, ai);

            } else if (path.startsWith("/api/resources/") && path.endsWith("/stock-in") && method.equals("POST")) {
                int id = extractIdSegment(path, "/api/resources/", "/stock-in");
                Integer qty = JsonUtil.extractInt(body, "quantity");
                boolean ok = qty != null && inv.stockIn(id, qty, "Web stock-in");
                respond(exchange, ok ? 200 : 400, ok ? resourceJsonOr404(inv, id) : error("Invalid resource ID or quantity"));

            } else if (path.startsWith("/api/resources/") && path.endsWith("/stock-out") && method.equals("POST")) {
                int id = extractIdSegment(path, "/api/resources/", "/stock-out");
                Integer qty = JsonUtil.extractInt(body, "quantity");
                int result = qty != null ? inv.stockOut(id, qty, "Web stock-out") : -2;
                if (result == -1) {
                    respond(exchange, 404, error("Resource not found"));
                } else if (result == -2) {
                    respond(exchange, 400, error("Invalid quantity or insufficient stock"));
                } else {
                    respond(exchange, 200, resourceJsonOr404(inv, id));
                }

            } else if (path.startsWith("/api/resources/") && method.equals("PUT")) {
                int id = extractIdSegment(path, "/api/resources/", null);
                handleUpdateResource(exchange, body, inv, id);

            } else if (path.startsWith("/api/resources/") && method.equals("DELETE")) {
                int id = extractIdSegment(path, "/api/resources/", null);
                boolean ok = inv.deleteResource(id);
                respond(exchange, ok ? 200 : 404, ok ? "{\"deleted\":true}" : error("Resource not found"));

            } else if (path.equals("/api/transactions") && method.equals("GET")) {
                respond(exchange, 200, transactionsJson(inv.getTransactions()));

            } else if (path.equals("/api/lowstock") && method.equals("GET")) {
                respond(exchange, 200, resourcesJson(inv.getLowStock()));

            } else if (path.equals("/api/stats") && method.equals("GET")) {
                respond(exchange, 200, statsJson(inv));

            } else if (path.equals("/api/budget") && method.equals("GET")) {
                respond(exchange, 200, budgetJson(budget));

            } else if (path.equals("/api/budget/purchase") && method.equals("POST")) {
                handlePurchase(exchange, body, budget, ai);

            } else if (path.equals("/api/budget/eoq") && method.equals("POST")) {
                handleEoq(exchange, body, ai);

            } else if (path.equals("/api/ai/advisor") && method.equals("POST")) {
                String result = ai.businessAdvisor(inv.buildInventorySummaryForAI());
                respond(exchange, 200, "{\"result\":\"" + JsonUtil.escape(result) + "\"}");

            } else if (path.equals("/api/ai/reorder-email") && method.equals("POST")) {
                handleReorderEmail(exchange, body, inv, ai);

            } else if (path.equals("/api/ai/query") && method.equals("POST")) {
                String question = JsonUtil.extractField(body, "question");
                if (question == null || question.isBlank()) {
                    respond(exchange, 400, error("Missing 'question'"));
                } else {
                    String result = ai.naturalLanguageQuery(question, inv.buildInventorySummaryForAI());
                    respond(exchange, 200, "{\"result\":\"" + JsonUtil.escape(result) + "\"}");
                }

            } else if (path.equals("/api/ai/categorize") && method.equals("POST")) {
                String name = JsonUtil.extractField(body, "name");
                if (name == null || name.isBlank()) {
                    respond(exchange, 400, error("Missing 'name'"));
                } else {
                    String result = ai.autoCategorizeAndDescribe(name);
                    respond(exchange, 200, "{\"result\":\"" + JsonUtil.escape(result) + "\"}");
                }

            } else if (path.equals("/api/ai/fraud-audit") && method.equals("POST")) {
                String result = ai.fraudAuditReport(inv.buildTransactionLogForAI(100));
                respond(exchange, 200, "{\"result\":\"" + JsonUtil.escape(result) + "\"}");

            } else {
                respond(exchange, 404, error("No such endpoint: " + method + " " + path));
            }

        } catch (Exception e) {
            respond(exchange, 500, error("Server error: " + e.getMessage()));
        }
    }

    // ============================================================ HANDLERS

    private void handleCreateSession(HttpExchange exchange, String body) throws IOException {
        Integer profileId = JsonUtil.extractInt(body, "profileId");
        Double budgetCap = JsonUtil.extractNumber(body, "budgetCap");
        Integer budgetDays = JsonUtil.extractInt(body, "budgetDays");

        IndustryProfile profile = profileId != null ? IndustryProfile.fromChoice(profileId) : null;
        if (profile == null) {
            respond(exchange, 400, error("Invalid profileId"));
            return;
        }
        double cap = budgetCap != null ? budgetCap : 0;
        int days = budgetDays != null ? budgetDays : 30;

        AppSession session = sessions.create(profile, cap, days);
        respond(exchange, 200, "{\"sessionId\":\"" + session.getId() + "\"," +
                "\"state\":" + stateJson(session) + "}");
    }

    private void handleAddResource(HttpExchange exchange, String body, InventoryEngine inv, AIService ai) throws IOException {
        String name = JsonUtil.extractField(body, "name");
        String category = JsonUtil.extractField(body, "category");
        String unit = JsonUtil.extractField(body, "unit");
        String description = JsonUtil.extractField(body, "description");
        Integer quantity = JsonUtil.extractInt(body, "quantity");
        Double buyPrice = JsonUtil.extractNumber(body, "buyPrice");
        Double sellPrice = JsonUtil.extractNumber(body, "sellPrice");
        Integer reorderLevel = JsonUtil.extractInt(body, "reorderLevel");

        if (name == null || name.isBlank() || quantity == null || buyPrice == null ||
                sellPrice == null || reorderLevel == null) {
            respond(exchange, 400, error("Missing required fields"));
            return;
        }
        if (description == null || description.isBlank()) {
            description = ai.autoCategorizeAndDescribe(name);
        }
        Resource r = inv.addResource(name, category != null ? category : "General", description,
                unit != null ? unit : "units", quantity, buyPrice, sellPrice, reorderLevel);
        respond(exchange, 200, r.toJson());
    }

    private void handleUpdateResource(HttpExchange exchange, String body, InventoryEngine inv, int id) throws IOException {
        String name = JsonUtil.extractField(body, "name");
        String category = JsonUtil.extractField(body, "category");
        String description = JsonUtil.extractField(body, "description");
        String unit = JsonUtil.extractField(body, "unit");
        Double buyPrice = JsonUtil.extractNumber(body, "buyPrice");
        Double sellPrice = JsonUtil.extractNumber(body, "sellPrice");
        Integer reorderLevel = JsonUtil.extractInt(body, "reorderLevel");

        boolean ok = inv.updateResource(id, name, category, description, unit,
                buyPrice != null ? buyPrice : -1, sellPrice != null ? sellPrice : -1,
                reorderLevel != null ? reorderLevel : -1);
        respond(exchange, ok ? 200 : 404, ok ? resourceJsonOr404(inv, id) : error("Resource not found"));
    }

    private void handlePurchase(HttpExchange exchange, String body, BudgetEngine budget, AIService ai) throws IOException {
        String desc = JsonUtil.extractField(body, "description");
        Double cost = JsonUtil.extractNumber(body, "cost");
        Boolean override = JsonUtil.extractBoolean(body, "override");
        if (desc == null || cost == null) {
            respond(exchange, 400, error("Missing 'description' or 'cost'"));
            return;
        }
        boolean afford = budget.canAfford(cost);
        if (afford || Boolean.TRUE.equals(override)) {
            budget.recordExpense(desc, cost);
            respond(exchange, 200, "{\"recorded\":true,\"blocked\":false,\"budget\":" + budgetJson(budget) + "}");
        } else {
            String advice = ai.purchaseGuardStrategy(desc, cost, budget.getRemainingBudget(), budget.getBudgetCap());
            respond(exchange, 200, "{\"recorded\":false,\"blocked\":true,\"aiAdvice\":\"" +
                    JsonUtil.escape(advice) + "\",\"budget\":" + budgetJson(budget) + "}");
        }
    }

    private void handleEoq(HttpExchange exchange, String body, AIService ai) throws IOException {
        String name = JsonUtil.extractField(body, "name");
        Integer annualDemand = JsonUtil.extractInt(body, "annualDemand");
        Double orderingCost = JsonUtil.extractNumber(body, "orderingCost");
        Double holdingCost = JsonUtil.extractNumber(body, "holdingCost");
        if (name == null || annualDemand == null || orderingCost == null || holdingCost == null) {
            respond(exchange, 400, error("Missing required fields"));
            return;
        }
        double eoq = BudgetEngine.calculateEOQ(annualDemand, orderingCost, holdingCost);
        String advice = ai.costOptimizer(name, annualDemand, orderingCost, holdingCost);
        respond(exchange, 200, "{\"eoq\":" + eoq + ",\"aiAdvice\":\"" + JsonUtil.escape(advice) + "\"}");
    }

    private void handleReorderEmail(HttpExchange exchange, String body, InventoryEngine inv, AIService ai) throws IOException {
        Integer resourceId = JsonUtil.extractInt(body, "resourceId");
        String supplier = JsonUtil.extractField(body, "supplier");
        if (resourceId == null) {
            respond(exchange, 400, error("Missing 'resourceId'"));
            return;
        }
        Optional<Resource> found = inv.findById(resourceId);
        if (found.isEmpty()) {
            respond(exchange, 404, error("Resource not found"));
            return;
        }
        Resource r = found.get();
        int suggestedQty = Math.max(r.getReorderLevel() * 3, 10);
        String email = ai.reorderEmail(supplier, r.getName(), r.getQuantity(), r.getReorderLevel(), suggestedQty);
        respond(exchange, 200, "{\"result\":\"" + JsonUtil.escape(email) + "\"}");
    }

    // ============================================================ JSON BUILDERS

    private String profilesJson() {
        List<String> items = new ArrayList<>();
        IndustryProfile[] values = IndustryProfile.values();
        for (int i = 0; i < values.length; i++) {
            items.add("{\"id\":" + (i + 1) + ",\"name\":\"" + JsonUtil.escape(values[i].getDisplayName()) + "\"}");
        }
        return JsonUtil.toJsonArray(items);
    }

    private String stateJson(AppSession session) {
        return "{"
                + "\"sessionId\":\"" + session.getId() + "\","
                + "\"profile\":\"" + JsonUtil.escape(session.getProfile().getDisplayName()) + "\","
                + "\"aiConfigured\":" + session.getAi().isConfigured() + ","
                + "\"resources\":" + resourcesJson(session.getInventory().getAll()) + ","
                + "\"budget\":" + budgetJson(session.getBudget())
                + "}";
    }

    private String resourcesJson(List<Resource> list) {
        List<String> items = new ArrayList<>();
        for (Resource r : list) {
            items.add(r.toJson());
        }
        return JsonUtil.toJsonArray(items);
    }

    private String resourceJsonOr404(InventoryEngine inv, int id) {
        return inv.findById(id).map(Resource::toJson).orElse("null");
    }

    private String transactionsJson(List<Transaction> list) {
        List<String> items = new ArrayList<>();
        for (Transaction t : list) {
            items.add(t.toJson());
        }
        return JsonUtil.toJsonArray(items);
    }

    private String statsJson(InventoryEngine inv) {
        double stockValue = inv.getTotalStockValue();
        double saleValue = inv.getTotalPotentialSaleValue();
        return "{"
                + "\"totalResources\":" + inv.getTotalResourceCount() + ","
                + "\"totalQuantity\":" + inv.getTotalQuantity() + ","
                + "\"categories\":" + inv.getUniqueCategories().size() + ","
                + "\"lowStockCount\":" + inv.getLowStock().size() + ","
                + "\"stockValue\":" + stockValue + ","
                + "\"potentialSaleValue\":" + saleValue + ","
                + "\"potentialProfit\":" + (saleValue - stockValue)
                + "}";
    }

    private String budgetJson(BudgetEngine budget) {
        return "{"
                + "\"budgetCap\":" + budget.getBudgetCap() + ","
                + "\"totalSpent\":" + budget.getTotalSpent() + ","
                + "\"remaining\":" + budget.getRemainingBudget() + ","
                + "\"utilizationPercent\":" + budget.getUtilizationPercent() + ","
                + "\"dailyBurnRate\":" + budget.getDailyBurnRate() + ","
                + "\"projectedSpend\":" + budget.getProjectedSpendAtCurrentRate() + ","
                + "\"variance\":" + budget.getCostVariance() + ","
                + "\"periodStart\":\"" + budget.getPeriodStart() + "\","
                + "\"periodEnd\":\"" + budget.getPeriodEnd() + "\""
                + "}";
    }

    private String error(String message) {
        return "{\"error\":\"" + JsonUtil.escape(message) + "\"}";
    }

    // ============================================================ HELPERS

    private int extractIdSegment(String path, String prefix, String suffix) {
        String remainder = path.substring(prefix.length());
        if (suffix != null && remainder.endsWith(suffix)) {
            remainder = remainder.substring(0, remainder.length() - suffix.length());
        }
        if (remainder.contains("/")) {
            remainder = remainder.substring(0, remainder.indexOf('/'));
        }
        try {
            return Integer.parseInt(remainder);
        } catch (NumberFormatException e) {
            return -1;
        }
    }

    private Map<String, String> parseQuery(String rawQuery) {
        Map<String, String> map = new HashMap<>();
        if (rawQuery == null || rawQuery.isBlank()) {
            return map;
        }
        for (String pair : rawQuery.split("&")) {
            int eq = pair.indexOf('=');
            if (eq > 0) {
                String key = java.net.URLDecoder.decode(pair.substring(0, eq), StandardCharsets.UTF_8);
                String value = java.net.URLDecoder.decode(pair.substring(eq + 1), StandardCharsets.UTF_8);
                map.put(key, value);
            }
        }
        return map;
    }

    private String readBody(HttpExchange exchange) throws IOException {
        byte[] bytes = exchange.getRequestBody().readAllBytes();
        return new String(bytes, StandardCharsets.UTF_8);
    }

    private void respond(HttpExchange exchange, int status, String json) throws IOException {
        byte[] bytes = json.getBytes(StandardCharsets.UTF_8);
        exchange.getResponseHeaders().set("Content-Type", "application/json; charset=UTF-8");
        exchange.sendResponseHeaders(status, bytes.length);
        try (OutputStream os = exchange.getResponseBody()) {
            os.write(bytes);
        }
    }
}
