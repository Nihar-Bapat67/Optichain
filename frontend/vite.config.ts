import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],

  server: {
    // Dev requests to /api are proxied to the FastAPI backend, so the app runs
    // same-origin and VITE_API_URL can be left unset.
    //
    // Note: a `define` for import.meta.env.VITE_API_URL used to live here. It
    // hardcoded http://localhost:8000 into the bundle whenever the env var was
    // absent, which bypassed this proxy in dev and pointed deployed builds at
    // the visitor's own machine. Vite already exposes VITE_-prefixed variables,
    // so the define was both redundant and harmful.
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },

  build: {
    target: 'es2022',
    sourcemap: false,
    reportCompressedSize: true,
    chunkSizeWarningLimit: 400,
    rollupOptions: {
      output: {
        // Split the heavy, rarely-changing vendors so shipping app code does not
        // invalidate the user's cached copy of React or Recharts.
        manualChunks(id: string) {
          if (!id.includes('node_modules')) return;
          if (/[\\/]node_modules[\\/](react|react-dom|scheduler)[\\/]/.test(id)) {
            return 'vendor-react';
          }
          if (/[\\/]node_modules[\\/](recharts|d3-|victory-|internmap|delaunator|robust-predicates)/.test(id)) {
            return 'vendor-charts';
          }
          if (/[\\/]node_modules[\\/](framer-motion|motion-dom|motion-utils)[\\/]/.test(id)) {
            return 'vendor-motion';
          }
          if (/[\\/]node_modules[\\/]@tanstack[\\/]/.test(id)) {
            return 'vendor-table';
          }
        },
      },
    },
  },
});
