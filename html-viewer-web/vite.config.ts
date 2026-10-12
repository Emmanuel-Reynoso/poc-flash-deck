import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// In local development, run the app through the SWA CLI (see README):
// it serves /.auth/* (fake login) and proxies /api to the Functions host.
export default defineConfig({
  plugins: [react()],
  server: { port: 5173, strictPort: true },
});
