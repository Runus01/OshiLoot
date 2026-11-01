import react from "@vitejs/plugin-react";
import { loadEnv, type Plugin } from "vite";
import { defineConfig } from "vitest/config";

/**
 * Counts visits with Cloudflare Web Analytics, which sets no cookies. Only added when
 * VITE_CF_ANALYTICS_TOKEN is set at build time: the deploy workflow passes the
 * CF_ANALYTICS_TOKEN repository variable, so copies of the repo send nothing.
 */
function cloudflareWebAnalytics(token: string | undefined): Plugin {
  if (token && !/^[A-Za-z0-9]+$/.test(token)) {
    throw new Error("VITE_CF_ANALYTICS_TOKEN should be the letters and digits from Cloudflare's snippet.");
  }
  return {
    name: "cloudflare-web-analytics",
    apply: "build",
    transformIndexHtml: () =>
      token
        ? [
            {
              tag: "script",
              attrs: {
                defer: true,
                src: "https://static.cloudflareinsights.com/beacon.min.js",
                "data-cf-beacon": JSON.stringify({ token }),
              },
              injectTo: "body",
            },
          ]
        : [],
  };
}

/**
 * Link previews need the image's full address. The deploy sets VITE_SITE_URL to the site's
 * address (https://oshiloot.com); without it the address stays relative.
 */
function absoluteSocialImage(siteUrl: string | undefined): Plugin {
  if (siteUrl && !/^https:\/\/[A-Za-z0-9.-]+$/.test(siteUrl)) {
    throw new Error(`VITE_SITE_URL should look like https://example.com, not "${siteUrl}".`);
  }
  return {
    name: "absolute-social-image",
    apply: "build",
    transformIndexHtml: (html) =>
      siteUrl
        ? html
            .replace('content="/og-image.png"', `content="${siteUrl}/og-image.png"`)
            .replace("</title>", `</title>\n    <meta property="og:url" content="${siteUrl}/" />`)
        : html,
  };
}

// In development, Vite forwards API calls to the FastAPI backend on port 8080.
// In production, CloudFront routes /api/* and /go/* to the Lambda function instead.
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, ".", "VITE_");
  return {
    plugins: [
      react(),
      cloudflareWebAnalytics(env.VITE_CF_ANALYTICS_TOKEN),
      absoluteSocialImage(env.VITE_SITE_URL),
    ],
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
  };
});
