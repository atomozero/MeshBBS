import { useState } from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Radio, Eye, EyeOff } from 'lucide-react';
import { useAuth } from '@/contexts';
import { Button, Input, Alert } from '@/components/ui';

export function LoginPage() {
  const { t } = useTranslation();
  const { login, isAuthenticated, isLoading } = useAuth();
  const location = useLocation();

  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Redirect if already authenticated
  if (isAuthenticated && !isLoading) {
    const from = (location.state as { from?: { pathname: string } })?.from?.pathname || '/';
    return <Navigate to={from} replace />;
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setIsSubmitting(true);

    try {
      await login(username, password);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : t('auth.invalidCredentials')
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-gray-950 px-4">
      <div className="w-full max-w-md">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-primary-500/10 mb-4">
            <Radio className="w-8 h-8 text-primary-500" />
          </div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
            {t('app.name')}
          </h1>
          <p className="text-gray-500 dark:text-gray-400 mt-2">
            {t('auth.signInDescription')}
          </p>
        </div>

        {/* Login form */}
        <div className="card p-6">
          <form onSubmit={handleSubmit} className="space-y-4">
            {error && (
              <Alert variant="error" dismissible onDismiss={() => setError('')}>
                {error}
              </Alert>
            )}

            <Input
              label={t('auth.username')}
              name="username"
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder={t('auth.username')}
              autoComplete="username"
              required
              disabled={isSubmitting}
            />

            <Input
              label={t('auth.password')}
              name="password"
              type={showPassword ? 'text' : 'password'}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder={t('auth.password')}
              autoComplete="current-password"
              required
              disabled={isSubmitting}
              rightIcon={
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="cursor-pointer hover:text-gray-600"
                  tabIndex={-1}
                >
                  {showPassword ? (
                    <EyeOff className="w-4 h-4" />
                  ) : (
                    <Eye className="w-4 h-4" />
                  )}
                </button>
              }
            />

            <Button
              type="submit"
              variant="primary"
              loading={isSubmitting}
              className="w-full"
            >
              {t('auth.signIn')}
            </Button>
          </form>
        </div>

        {/* Footer */}
        <p className="text-center text-sm text-gray-500 dark:text-gray-400 mt-6">
          {t('app.name')} &copy; {new Date().getFullYear()}
        </p>
      </div>
    </div>
  );
}
