package com.erp.utils;

/**
 * A deliberately tiny, dependency-free JSON helper.
 *
 * This project intentionally avoids pulling in Jackson/Gson so that the
 * whole ERP compiles and runs with nothing but the JDK (per the "Pure Java"
 * requirement). It only implements the two operations this project needs:
 *   - escaping a string for safe embedding into a JSON request body
 *   - pulling the first "text" field out of a Gemini JSON response
 *
 * It is NOT a general-purpose JSON parser.
 */
public final class JsonUtil {

    private JsonUtil() {
    }

    /** Escapes a string so it can be safely placed inside a JSON string literal. */
    public static String escape(String raw) {
        if (raw == null) {
            return "";
        }
        StringBuilder sb = new StringBuilder(raw.length() + 16);
        for (int i = 0; i < raw.length(); i++) {
            char c = raw.charAt(i);
            switch (c) {
                case '"': sb.append("\\\""); break;
                case '\\': sb.append("\\\\"); break;
                case '\n': sb.append("\\n"); break;
                case '\r': sb.append("\\r"); break;
                case '\t': sb.append("\\t"); break;
                default:
                    if (c < 0x20) {
                        sb.append(String.format("\\u%04x", (int) c));
                    } else {
                        sb.append(c);
                    }
            }
        }
        return sb.toString();
    }

    /**
     * Extracts the value of the first {@code "text": "..."} field found in a
     * JSON response body (used for Gemini-style responses). Equivalent to
     * {@code extractField(json, "text")}.
     */
    public static String extractFirstText(String json) {
        return extractField(json, "text");
    }

    /**
     * Extracts the string value of the first {@code "field": "..."} occurrence
     * found in the given JSON text (e.g. {@code extractField(json, "content")}
     * for Groq/OpenAI-style responses, or {@code extractField(json, "message")}
     * for error bodies). Handles escaped quotes/backslashes inside the value.
     * Returns {@code null} if the field isn't found or isn't a plain string.
     */
    public static String extractField(String json, String field) {
        if (json == null) {
            return null;
        }
        String marker = "\"" + field + "\"";
        int markerIdx = json.indexOf(marker);
        if (markerIdx == -1) {
            return null;
        }
        int colonIdx = json.indexOf(':', markerIdx + marker.length());
        if (colonIdx == -1) {
            return null;
        }
        int i = colonIdx + 1;
        // Skip whitespace up to opening quote.
        while (i < json.length() && Character.isWhitespace(json.charAt(i))) {
            i++;
        }
        if (i >= json.length() || json.charAt(i) != '"') {
            return null; // value isn't a plain string (e.g. null, number, object)
        }
        i++; // move past opening quote
        StringBuilder value = new StringBuilder();
        while (i < json.length()) {
            char c = json.charAt(i);
            if (c == '\\' && i + 1 < json.length()) {
                char next = json.charAt(i + 1);
                switch (next) {
                    case 'n': value.append('\n'); break;
                    case 'r': value.append('\r'); break;
                    case 't': value.append('\t'); break;
                    case '"': value.append('"'); break;
                    case '\\': value.append('\\'); break;
                    case '/': value.append('/'); break;
                    case 'u':
                        if (i + 5 < json.length()) {
                            String hex = json.substring(i + 2, i + 6);
                            try {
                                value.append((char) Integer.parseInt(hex, 16));
                            } catch (NumberFormatException ignored) {
                                // skip malformed unicode escape
                            }
                            i += 4;
                        }
                        break;
                    default: value.append(next);
                }
                i += 2;
            } else if (c == '"') {
                break; // closing quote found
            } else {
                value.append(c);
                i++;
            }
        }
        return value.toString();
    }

    /**
     * Extracts a numeric field's value (int, double, negative, exponent forms),
     * e.g. {@code extractNumber(json, "quantity")}. Returns {@code null} if the
     * field isn't found or isn't a plain number.
     */
    public static Double extractNumber(String json, String field) {
        if (json == null) {
            return null;
        }
        String marker = "\"" + field + "\"";
        int markerIdx = json.indexOf(marker);
        if (markerIdx == -1) {
            return null;
        }
        int colonIdx = json.indexOf(':', markerIdx + marker.length());
        if (colonIdx == -1) {
            return null;
        }
        int i = colonIdx + 1;
        while (i < json.length() && Character.isWhitespace(json.charAt(i))) {
            i++;
        }
        int start = i;
        while (i < json.length()) {
            char c = json.charAt(i);
            if (Character.isDigit(c) || c == '-' || c == '+' || c == '.' || c == 'e' || c == 'E') {
                i++;
            } else {
                break;
            }
        }
        if (i == start) {
            return null;
        }
        try {
            return Double.parseDouble(json.substring(start, i));
        } catch (NumberFormatException e) {
            return null;
        }
    }

    /** Convenience wrapper around {@link #extractNumber} that rounds to an int. */
    public static Integer extractInt(String json, String field) {
        Double d = extractNumber(json, field);
        return d != null ? (int) Math.round(d) : null;
    }

    /** Extracts a boolean field's value, e.g. {@code extractBoolean(json, "override")}. */
    public static Boolean extractBoolean(String json, String field) {
        if (json == null) {
            return null;
        }
        String marker = "\"" + field + "\"";
        int markerIdx = json.indexOf(marker);
        if (markerIdx == -1) {
            return null;
        }
        int colonIdx = json.indexOf(':', markerIdx + marker.length());
        if (colonIdx == -1) {
            return null;
        }
        int i = colonIdx + 1;
        while (i < json.length() && Character.isWhitespace(json.charAt(i))) {
            i++;
        }
        if (json.startsWith("true", i)) {
            return true;
        }
        if (json.startsWith("false", i)) {
            return false;
        }
        return null;
    }

    /** Joins already-serialized JSON object/value strings into a JSON array literal. */
    public static String toJsonArray(Iterable<String> jsonValues) {
        StringBuilder sb = new StringBuilder("[");
        boolean first = true;
        for (String v : jsonValues) {
            if (!first) {
                sb.append(',');
            }
            sb.append(v);
            first = false;
        }
        sb.append(']');
        return sb.toString();
    }
}
