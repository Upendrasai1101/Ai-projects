package com.erp.web;

import com.erp.models.IndustryProfile;

import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;

/**
 * Simple in-memory registry of active {@link AppSession}s, keyed by a random
 * session id handed to the browser. This is what makes the web app
 * "multi-user": each browser tab that calls POST /api/session gets its own
 * isolated inventory/budget/AI state, all served by one running process.
 */
public class SessionManager {

    private final Map<String, AppSession> sessions = new ConcurrentHashMap<>();

    public AppSession create(IndustryProfile profile, double budgetCap, int budgetDays) {
        String id = UUID.randomUUID().toString();
        AppSession session = new AppSession(id, profile, budgetCap, budgetDays);
        sessions.put(id, session);
        return session;
    }

    public AppSession get(String sessionId) {
        if (sessionId == null) {
            return null;
        }
        return sessions.get(sessionId);
    }

    public void remove(String sessionId) {
        sessions.remove(sessionId);
    }
}
