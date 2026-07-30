package com.erp.utils;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * Minimal, dependency-free ".env" file reader.
 *
 * Resolution order for any requested key:
 *   1. A real OS environment variable (System.getenv) — always wins, so
 *      the same code works unmodified in CI/CD, Docker, or cloud secrets.
 *   2. A KEY=VALUE line found in a local ".env" file (never commit this file).
 *
 * The .env file is loaded once, lazily, the first time a value is requested.
 */
public final class EnvLoader {

    private static final String DEFAULT_ENV_FILE = ".env";
    private static Map<String, String> cache;

    private EnvLoader() {
    }

    public static String get(String key) {
        return get(key, null);
    }

    public static String get(String key, String defaultValue) {
        // 1) Real environment variable takes priority.
        String fromEnv = System.getenv(key);
        if (fromEnv != null && !fromEnv.isBlank()) {
            return fromEnv;
        }

        // 2) Fall back to values parsed from the .env file.
        ensureLoaded();
        String fromFile = cache.get(key);
        if (fromFile != null && !fromFile.isBlank()) {
            return fromFile;
        }

        return defaultValue;
    }

    public static boolean has(String key) {
        return get(key) != null;
    }

    private static synchronized void ensureLoaded() {
        if (cache != null) {
            return;
        }
        cache = new HashMap<>();
        Path path = Path.of(DEFAULT_ENV_FILE);
        if (!Files.exists(path)) {
            return;
        }
        try {
            List<String> lines = Files.readAllLines(path);
            for (String rawLine : lines) {
                String line = rawLine.trim();
                if (line.isEmpty() || line.startsWith("#")) {
                    continue;
                }
                int eq = line.indexOf('=');
                if (eq <= 0) {
                    continue;
                }
                String key = line.substring(0, eq).trim();
                String value = line.substring(eq + 1).trim();
                // Strip surrounding quotes if present, e.g. KEY="value"
                if (value.length() >= 2 &&
                        ((value.startsWith("\"") && value.endsWith("\"")) ||
                         (value.startsWith("'") && value.endsWith("'")))) {
                    value = value.substring(1, value.length() - 1);
                }
                cache.put(key, value);
            }
        } catch (IOException e) {
            System.err.println("Warning: could not read " + DEFAULT_ENV_FILE + " (" + e.getMessage() + ")");
        }
    }
}
