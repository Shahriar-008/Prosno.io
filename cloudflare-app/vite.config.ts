import { defineConfig } from 'vite';
import { resolve } from 'node:path';

export default defineConfig({
  publicDir: false,
  build: {
    outDir: resolve(__dirname, 'public/dist'),
    emptyOutDir: true,
    rollupOptions: {
      input: resolve(__dirname, 'client/print-studio.ts'),
      output: {
        entryFileNames: 'print-studio.js',
        assetFileNames: (assetInfo) => {
          if (assetInfo.name && assetInfo.name.endsWith('.css')) {
            return 'print-studio.css';
          }
          return 'assets/[name][extname]';
        },
      },
    },
  },
});
