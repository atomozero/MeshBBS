import { lazy, Suspense } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AuthProvider, useAuth, WebSocketProvider, ThemeProvider } from '@/contexts';
import { ToastProvider, LoadingPage, LoadingInline } from '@/components/ui';
import { ErrorBoundary } from '@/components/error';
import { MainLayout } from '@/components/layout';

// Lazy load pages for better initial bundle size
const LoginPage = lazy(() => import('@/pages/LoginPage').then(m => ({ default: m.LoginPage })));
const DashboardPage = lazy(() => import('@/pages/DashboardPage').then(m => ({ default: m.DashboardPage })));
const UsersPage = lazy(() => import('@/pages/UsersPage').then(m => ({ default: m.UsersPage })));
const AreasPage = lazy(() => import('@/pages/AreasPage').then(m => ({ default: m.AreasPage })));
const MessagesPage = lazy(() => import('@/pages/MessagesPage').then(m => ({ default: m.MessagesPage })));
const LogsPage = lazy(() => import('@/pages/LogsPage').then(m => ({ default: m.LogsPage })));
const SettingsPage = lazy(() => import('@/pages/SettingsPage').then(m => ({ default: m.SettingsPage })));

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000, // 5 minutes
      retry: 1,
    },
  },
});

// Page loading fallback
function PageLoader() {
  return (
    <div className="flex items-center justify-center min-h-[50vh]">
      <LoadingInline text="Loading page..." />
    </div>
  );
}

// Protected route wrapper
function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return <LoadingPage message="Checking authentication..." />;
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return <>{children}</>;
}

// App routes with lazy loaded pages
function AppRoutes() {
  return (
    <Routes>
      <Route
        path="/login"
        element={
          <Suspense fallback={<LoadingPage message="Loading..." />}>
            <LoginPage />
          </Suspense>
        }
      />
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <MainLayout />
          </ProtectedRoute>
        }
      >
        <Route
          index
          element={
            <Suspense fallback={<PageLoader />}>
              <DashboardPage />
            </Suspense>
          }
        />
        <Route
          path="users"
          element={
            <Suspense fallback={<PageLoader />}>
              <UsersPage />
            </Suspense>
          }
        />
        <Route
          path="areas"
          element={
            <Suspense fallback={<PageLoader />}>
              <AreasPage />
            </Suspense>
          }
        />
        <Route
          path="messages"
          element={
            <Suspense fallback={<PageLoader />}>
              <MessagesPage />
            </Suspense>
          }
        />
        <Route
          path="logs"
          element={
            <Suspense fallback={<PageLoader />}>
              <LogsPage />
            </Suspense>
          }
        />
        <Route
          path="settings"
          element={
            <Suspense fallback={<PageLoader />}>
              <SettingsPage />
            </Suspense>
          }
        />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

// Main App component
export function App() {
  return (
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <ThemeProvider defaultTheme="system">
            <ToastProvider>
              <AuthProvider>
                <WebSocketProvider>
                  <AppRoutes />
                </WebSocketProvider>
              </AuthProvider>
            </ToastProvider>
          </ThemeProvider>
        </BrowserRouter>
      </QueryClientProvider>
    </ErrorBoundary>
  );
}
