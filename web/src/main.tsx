import React, { Suspense } from 'react';
import ReactDOM from 'react-dom/client';
import { App } from './App';
import './index.css';

// Initialize i18next
import './i18n';

// Loading component for Suspense
const Loading = () => (
  <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-gray-950">
    <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-500"></div>
  </div>
);

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <Suspense fallback={<Loading />}>
      <App />
    </Suspense>
  </React.StrictMode>
);
