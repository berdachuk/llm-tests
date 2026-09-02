package com.qualbench.bugs;

import java.time.LocalDate;

/**
 * Checks whether two date ranges (inclusive on both ends) overlap.
 */
public class DateRangeOverlap {

    /**
     * Returns true if [startA, endA] and [startB, endB] share at least one
     * day in common. Both ranges are inclusive of their start and end
     * dates. A range that merely touches at a single shared boundary day
     * counts as overlapping.
     */
    public boolean overlaps(LocalDate startA, LocalDate endA, LocalDate startB, LocalDate endB) {
        // BUG: uses strict isBefore/isAfter on both boundaries, so two
        // ranges that touch at exactly one shared boundary day (e.g. range
        // A ends on the same day range B starts) are incorrectly reported
        // as NOT overlapping, even though that shared day should count.
        return startA.isBefore(endB) && startB.isBefore(endA);
    }
}
