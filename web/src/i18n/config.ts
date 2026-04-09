import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import LanguageDetector from 'i18next-browser-languagedetector';
import HttpBackend from 'i18next-http-backend';

// Initialize i18next
i18n
  // Load translations from public/locales folder
  .use(HttpBackend)
  // Detect user language
  .use(LanguageDetector)
  // Pass i18n instance to react-i18next
  .use(initReactI18next)
  // Init i18next
  .init({
    // Fallback language
    fallbackLng: 'en',

    // Supported languages
    supportedLngs: ['en', 'it'],

    // Default namespace
    defaultNS: 'common',

    // Namespaces to load
    ns: ['common', 'dashboard', 'users', 'areas', 'messages', 'logs', 'settings'],

    // Debug mode (disable in production)
    debug: import.meta.env.DEV,

    // Interpolation options
    interpolation: {
      // React already does escaping
      escapeValue: false,
    },

    // Detection options
    detection: {
      // Order of language detection
      order: ['localStorage', 'navigator', 'htmlTag'],
      // Cache user language selection
      caches: ['localStorage'],
      // LocalStorage key
      lookupLocalStorage: 'meshbbs-lang',
    },

    // Backend options for loading translations
    backend: {
      // Path to translation files
      loadPath: '/locales/{{lng}}/{{ns}}.json',
    },

    // React options
    react: {
      // Wait for all translations to be loaded before rendering
      useSuspense: true,
    },
  });

export default i18n;

// Helper to get current language
export const getCurrentLanguage = (): string => {
  return i18n.language || 'en';
};

// Helper to change language
export const changeLanguage = async (lang: string): Promise<void> => {
  await i18n.changeLanguage(lang);
};

// Available languages
export const languages = [
  { code: 'en', name: 'English', flag: '🇬🇧' },
  { code: 'it', name: 'Italiano', flag: '🇮🇹' },
] as const;

export type LanguageCode = typeof languages[number]['code'];
