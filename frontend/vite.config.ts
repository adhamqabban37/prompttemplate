import path from "node:path";
import { tanstackRouter } from "@tanstack/router-plugin/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// https://vitejs.dev/config/
const proxyTarget = process.env.VITE_IN_DOCKER
  ? "http://backend:8000"
  : "http://localhost:8001";

export default defineConfig({
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  plugins: [
    tanstackRouter({
      target: "react",
      autoCodeSplitting: true,
    }),
    react(),
  ],
  server: {
    host: "localhost",
    port: 5174,
    strictPort: true,
    hmr: {
      host: "localhost",
      clientPort: 5174,
    },
    proxy: {
      "/api": {
        target: proxyTarget,
        changeOrigin: true,
        secure: false,
      },
    },
  },
  // Allow Vite to discover and pre-bundle dependencies
  optimizeDeps: {
    // Explicitly include key dependencies for faster startup
    include: [
      "react",
      "react-dom",
      "@tanstack/react-query",
      "@tanstack/react-router",
      "@chakra-ui/react",
    ],
  },
});
