package com.qualbench.bugs;

import org.junit.jupiter.api.Test;
import java.time.LocalDate;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

class DateRangeOverlapTest {

    private final DateRangeOverlap checker = new DateRangeOverlap();

    @Test
    void clearlyOverlappingRanges() {
        assertTrue(checker.overlaps(
                LocalDate.of(2026, 1, 1), LocalDate.of(2026, 1, 10),
                LocalDate.of(2026, 1, 5), LocalDate.of(2026, 1, 15)));
    }

    @Test
    void clearlyDisjointRanges() {
        assertFalse(checker.overlaps(
                LocalDate.of(2026, 1, 1), LocalDate.of(2026, 1, 5),
                LocalDate.of(2026, 2, 1), LocalDate.of(2026, 2, 5)));
    }

    @Test
    void touchingAtSharedBoundaryDayCountsAsOverlap() {
        // Range A ends exactly on the day Range B starts -- that shared
        // day must count as an overlap.
        assertTrue(checker.overlaps(
                LocalDate.of(2026, 1, 1), LocalDate.of(2026, 1, 10),
                LocalDate.of(2026, 1, 10), LocalDate.of(2026, 1, 20)));
    }

    @Test
    void oneRangeFullyInsideAnother() {
        assertTrue(checker.overlaps(
                LocalDate.of(2026, 1, 1), LocalDate.of(2026, 1, 31),
                LocalDate.of(2026, 1, 10), LocalDate.of(2026, 1, 15)));
    }

    @Test
    void identicalSingleDayRangesOverlap() {
        LocalDate day = LocalDate.of(2026, 3, 3);
        assertTrue(checker.overlaps(day, day, day, day));
    }
}
