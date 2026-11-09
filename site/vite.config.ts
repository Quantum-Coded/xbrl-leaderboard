import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Relative base so the build works on GitHub Pages, an HF Space or any sub-path.
export default defineConfig({ plugins: [react()], base: "./" });
