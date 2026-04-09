import { useState, useCallback, useMemo } from 'react';
import { useSearchParams } from 'react-router-dom';

interface UsePaginationOptions {
  initialPage?: number;
  initialPerPage?: number;
  syncWithUrl?: boolean;
}

interface UsePaginationReturn {
  page: number;
  perPage: number;
  setPage: (page: number) => void;
  setPerPage: (perPage: number) => void;
  nextPage: () => void;
  prevPage: () => void;
  totalPages: number;
  setTotal: (total: number) => void;
  offset: number;
  hasNextPage: boolean;
  hasPrevPage: boolean;
  reset: () => void;
}

/**
 * Hook to manage pagination state.
 * Optionally syncs with URL query parameters.
 *
 * @param options - Pagination options
 * @returns Pagination state and control functions
 */
export function usePagination(options: UsePaginationOptions = {}): UsePaginationReturn {
  const {
    initialPage = 1,
    initialPerPage = 20,
    syncWithUrl = false,
  } = options;

  const [searchParams, setSearchParams] = useSearchParams();

  const urlPage = syncWithUrl ? parseInt(searchParams.get('page') || '') : NaN;
  const urlPerPage = syncWithUrl ? parseInt(searchParams.get('per_page') || '') : NaN;

  const [page, setPageState] = useState(isNaN(urlPage) ? initialPage : urlPage);
  const [perPage, setPerPageState] = useState(isNaN(urlPerPage) ? initialPerPage : urlPerPage);
  const [total, setTotal] = useState(0);

  const totalPages = useMemo(() => Math.ceil(total / perPage), [total, perPage]);
  const offset = useMemo(() => (page - 1) * perPage, [page, perPage]);
  const hasNextPage = page < totalPages;
  const hasPrevPage = page > 1;

  const setPage = useCallback((newPage: number) => {
    const validPage = Math.max(1, Math.min(newPage, totalPages || 1));
    setPageState(validPage);

    if (syncWithUrl) {
      setSearchParams((params) => {
        if (validPage === 1) {
          params.delete('page');
        } else {
          params.set('page', validPage.toString());
        }
        return params;
      });
    }
  }, [totalPages, syncWithUrl, setSearchParams]);

  const setPerPage = useCallback((newPerPage: number) => {
    setPerPageState(newPerPage);
    setPageState(1); // Reset to first page when changing per page

    if (syncWithUrl) {
      setSearchParams((params) => {
        params.set('per_page', newPerPage.toString());
        params.delete('page');
        return params;
      });
    }
  }, [syncWithUrl, setSearchParams]);

  const nextPage = useCallback(() => {
    if (hasNextPage) {
      setPage(page + 1);
    }
  }, [page, hasNextPage, setPage]);

  const prevPage = useCallback(() => {
    if (hasPrevPage) {
      setPage(page - 1);
    }
  }, [page, hasPrevPage, setPage]);

  const reset = useCallback(() => {
    setPageState(initialPage);
    setPerPageState(initialPerPage);
    setTotal(0);

    if (syncWithUrl) {
      setSearchParams((params) => {
        params.delete('page');
        params.delete('per_page');
        return params;
      });
    }
  }, [initialPage, initialPerPage, syncWithUrl, setSearchParams]);

  return {
    page,
    perPage,
    setPage,
    setPerPage,
    nextPage,
    prevPage,
    totalPages,
    setTotal,
    offset,
    hasNextPage,
    hasPrevPage,
    reset,
  };
}
