import { useEffect, RefObject } from 'react';

/**
 * Hook to detect clicks outside of a referenced element.
 * Useful for modals, dropdowns, and popovers.
 *
 * @param ref - The ref of the element to detect outside clicks for
 * @param handler - The callback to run when clicking outside
 */
export function useOnClickOutside<T extends HTMLElement = HTMLElement>(
  ref: RefObject<T>,
  handler: (event: MouseEvent | TouchEvent) => void
): void {
  useEffect(() => {
    const listener = (event: MouseEvent | TouchEvent) => {
      const el = ref?.current;
      // Do nothing if clicking ref's element or its descendants
      if (!el || el.contains(event.target as Node)) {
        return;
      }

      handler(event);
    };

    document.addEventListener('mousedown', listener);
    document.addEventListener('touchstart', listener);

    return () => {
      document.removeEventListener('mousedown', listener);
      document.removeEventListener('touchstart', listener);
    };
  }, [ref, handler]);
}
