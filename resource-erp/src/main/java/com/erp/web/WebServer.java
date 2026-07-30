package com.erp.web;

import com.erp.utils.EnvLoader;
import com.sun.net.httpserver.HttpServer;

import java.io.IOException;
import java.net.InetSocketAddress;
import java.util.concurrent.Executors;

/**
 * Entry point for the web version of the Universal Resource & Budget ERP.
 * Uses only {@code com.sun.net.httpserver.HttpServer} (bundled with the JDK)
 * — no Spring, no Javalin — consistent with the console app's "pure Java,
 * zero external dependencies" goal.
 *
 * Run with: java -cp out com.erp.web.WebServer
 * Then open: http://localhost:8080
 */
public class WebServer {

    public static void main(String[] args) throws IOException {
        int port = Integer.parseInt(EnvLoader.get("PORT", "8080"));

        SessionManager sessions = new SessionManager();

        HttpServer server = HttpServer.create(new InetSocketAddress(port), 0);
        server.createContext("/api", new ApiHandler(sessions));
        server.createContext("/", new StaticFileHandler("public"));
        server.setExecutor(Executors.newFixedThreadPool(8));
        server.start();

        System.out.println("==================================================================");
        System.out.println("  UNIVERSAL AI-POWERED RESOURCE & BUDGET ERP SYSTEM  (Web Server)");
        System.out.println("  Listening on: http://localhost:" + port);
        System.out.println("  Serving frontend from: ./public/");
        System.out.println("==================================================================");
    }
}
