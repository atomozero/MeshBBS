/**
 * API client tests.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { setAccessToken, getAccessToken, clearTokens, clearAccessToken } from '@/api/client';

describe('API Client Token Management', () => {
  beforeEach(() => {
    // Clear localStorage mock
    vi.mocked(localStorage.getItem).mockReturnValue(null);
    vi.mocked(localStorage.setItem).mockClear();
    vi.mocked(localStorage.removeItem).mockClear();

    // Clear any existing token
    clearTokens();
  });

  afterEach(() => {
    clearTokens();
  });

  it('should set and get access token', () => {
    setAccessToken('test-token-123');

    expect(localStorage.setItem).toHaveBeenCalledWith('access_token', 'test-token-123');

    vi.mocked(localStorage.getItem).mockReturnValue('test-token-123');
    expect(getAccessToken()).toBe('test-token-123');
  });

  it('should clear access token', () => {
    setAccessToken('test-token');
    clearAccessToken();

    expect(localStorage.removeItem).toHaveBeenCalledWith('access_token');
  });

  it('should clear all tokens', () => {
    setAccessToken('access-token');

    clearTokens();

    expect(localStorage.removeItem).toHaveBeenCalledWith('access_token');
    expect(localStorage.removeItem).toHaveBeenCalledWith('refresh_token');
  });

  it('should remove token from localStorage when set to null', () => {
    setAccessToken('test-token');
    setAccessToken(null);

    expect(localStorage.removeItem).toHaveBeenCalledWith('access_token');
  });

  it('should return token from localStorage if not in memory', () => {
    vi.mocked(localStorage.getItem).mockReturnValue('stored-token');

    const token = getAccessToken();

    expect(localStorage.getItem).toHaveBeenCalledWith('access_token');
    expect(token).toBe('stored-token');
  });
});
