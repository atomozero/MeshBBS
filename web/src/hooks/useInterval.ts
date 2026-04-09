import { useEffect, useRef } from 'react';

/**
 * Hook to run a callback at regular intervals.
 * The interval is properly cleaned up on unmount.
 *
 * @param callback - The function to run at each interval
 * @param delay - The interval delay in milliseconds (null to pause)
 */
export function useInterval(callback: () => void, delay: number | null): void {
  const savedCallback = useRef<() => void>(callback);

  // Remember the latest callback
  useEffect(() => {
    savedCallback.current = callback;
  }, [callback]);

  // Set up the interval
  useEffect(() => {
    if (delay === null) {
      return;
    }

    const tick = () => {
      savedCallback.current();
    };

    const id = setInterval(tick, delay);
    return () => clearInterval(id);
  }, [delay]);
}

/**
 * Hook to run a callback after a delay.
 * The timeout is properly cleaned up on unmount.
 *
 * @param callback - The function to run after the delay
 * @param delay - The delay in milliseconds (null to cancel)
 */
export function useTimeout(callback: () => void, delay: number | null): void {
  const savedCallback = useRef<() => void>(callback);

  // Remember the latest callback
  useEffect(() => {
    savedCallback.current = callback;
  }, [callback]);

  // Set up the timeout
  useEffect(() => {
    if (delay === null) {
      return;
    }

    const id = setTimeout(() => savedCallback.current(), delay);
    return () => clearTimeout(id);
  }, [delay]);
}
