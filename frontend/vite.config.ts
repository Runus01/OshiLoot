import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// In development, Vite forwards API calls to the FastAPI backend on port 8080.
// In production, CloudFront routes /api/* and /go/* to the Lambda function instead.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": "http://localhost:8080",
      "/go": "http://localhost:8080",
    },
  },
  test: {
    environment: "node",
  },
});
