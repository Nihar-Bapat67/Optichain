import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';

import App from './App';
import { ErrorBoundary } from './components/ErrorBoundary';
import { ThemeProvider } from './providers/ThemeProvider';
import { ToastProvider } from './providers/ToastProvider';
import './index.css';

const container = document.getElementById('root');
if (!container) throw new Error('Root element #root not found in index.html');

createRoot(container).render(
  <StrictMode>
    <ThemeProvider>
      <ToastProvider>
        <ErrorBoundary>
          <App />
        </ErrorBoundary>
      </ToastProvider>
    </ThemeProvider>
  </StrictMode>,
);
