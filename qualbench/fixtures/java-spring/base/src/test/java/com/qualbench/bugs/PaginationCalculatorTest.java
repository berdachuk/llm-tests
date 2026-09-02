package com.qualbench.bugs;

import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.assertEquals;

class PaginationCalculatorTest {

    private final PaginationCalculator calc = new PaginationCalculator();

    @Test
    void exactMultipleNeedsExactPages() {
        assertEquals(10, calc.totalPages(100, 10));
    }

    @Test
    void partialLastPageRoundsUp() {
        assertEquals(11, calc.totalPages(101, 10));
    }

    @Test
    void singleItemNeedsOnePage() {
        assertEquals(1, calc.totalPages(1, 10));
    }

    @Test
    void zeroItemsNeedsZeroPages() {
        assertEquals(0, calc.totalPages(0, 10));
    }

    @Test
    void rejectsNonPositivePageSize() {
        org.junit.jupiter.api.Assertions.assertThrows(IllegalArgumentException.class,
                () -> calc.totalPages(10, 0));
    }
}
