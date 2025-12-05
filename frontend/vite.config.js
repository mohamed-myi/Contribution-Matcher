import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  build: {
    // Enable source maps for debugging (disable in production if needed)
    sourcemap: false,
    // Chunk size warning threshold (400kb)
    chunkSizeWarningLimit: 400,
    // Minification options
    minify: 'esbuild',
    // Target modern browsers for smaller bundle
    target: 'es2020',
    // CSS code splitting
    cssCodeSplit: true,
    rollupOptions: {
      // Tree shaking for smaller bundles
      treeshake: {
        moduleSideEffects: false,
        propertyReadSideEffects: false,
      },
      output: {
        // Manual chunk splitting for optimal caching
        manualChunks: (id) => {
          // Vendor chunks - rarely change, cache long-term
          if (id.includes('node_modules')) {
            // React core - most stable
            if (id.includes('react') || id.includes('react-dom')) {
              return 'react-vendor';
            }
            // React Router
            if (id.includes('react-router')) {
              return 'router';
            }
            // React Query
            if (id.includes('@tanstack/react-query')) {
              return 'query';
            }
            // HTTP client
            if (id.includes('axios')) {
              return 'http';
            }
            // Other vendors
            return 'vendor';
          }
          
          // Don't split pages - let Vite handle them naturally for lazy loading
          // This avoids circular dependency issues with Layout component
          
          // Split common components into shared chunk if they're large
          if (id.includes('/components/common/') && id.includes('Skeleton')) {
            return 'components-skeleton';
          }
          
          // Split hooks into shared chunk
          if (id.includes('/hooks/')) {
            return 'hooks';
          }
          
          // Keep utils together
          if (id.includes('/utils/')) {
            return 'utils';
          }
        },
        // Clean chunk naming with content hash for cache busting
        chunkFileNames: (chunkInfo) => {
          // Use shorter names for better debugging
          const name = chunkInfo.name;
          if (name.includes('vendor') || name === 'router' || name === 'query' || name === 'http') {
            return 'assets/vendor/[name]-[hash].js';
          }
          return 'assets/[name]-[hash].js';
        },
        entryFileNames: 'assets/[name]-[hash].js',
        assetFileNames: (assetInfo) => {
          // Organize assets by type
          const name = assetInfo.name || '';
          if (/\.(png|jpe?g|gif|svg|webp|ico)$/i.test(name)) {
            return 'assets/images/[name]-[hash][extname]';
          }
          if (/\.(woff2?|eot|ttf|otf)$/i.test(name)) {
            return 'assets/fonts/[name]-[hash][extname]';
          }
          if (/\.css$/i.test(name)) {
            return 'assets/css/[name]-[hash][extname]';
          }
          return 'assets/[name]-[hash][extname]';
        },
      },
    },
  },
  // Optimize dependencies
  optimizeDeps: {
    include: [
      'react',
      'react-dom',
      'react-router-dom',
      '@tanstack/react-query',
      'axios'
    ],
    // Exclude large dependencies that should be lazy loaded
    exclude: [],
  },
  // Enable esbuild for faster builds
  esbuild: {
    // Minify identifiers for production
    minifyIdentifiers: true,
    minifySyntax: true,
    minifyWhitespace: true,
  },
  // Server config for development
  server: {
    // Enable compression
    compress: true,
    // Port
    port: 5173,
    // Open browser automatically
    open: false,
  },
})
