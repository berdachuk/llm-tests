package com.qualbench.bugs;

/**
 * Computes pagination metadata for a result set.
 */
public class PaginationCalculator {

    /**
     * Returns the total number of pages needed to display {@code totalItems}
     * items at {@code pageSize} items per page. Must round UP (a partial
     * last page still counts as a full page).
     */
    public int totalPages(int totalItems, int pageSize) {
        if (pageSize <= 0) {
            throw new IllegalArgumentException("pageSize must be positive");
        }
        if (totalItems <= 0) {
            return 0;
        }
        // BUG: integer division truncates instead of rounding up, so a
        // partial last page (e.g. 101 items / 10 per page) is dropped.
        return totalItems / pageSize;
    }
}
