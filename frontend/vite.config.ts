import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

const target = process.env.BACKEND_URL || "http://127.0.0.1:2024";

export default defineConfig({
  plugins: [vue()],
  base: "./",
  server: {
    port: 5174,
    proxy: {
      "/api": { target, changeOrigin: true },
      "/threads": { target, changeOrigin: true },
      "/assistants": { target, changeOrigin: true },
      "/runs": { target, changeOrigin: true },
    },
  },
});
