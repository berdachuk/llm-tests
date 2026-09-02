package com.qualbench.bugs;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;

class MovingAverageTest {

    @Test
    void firstValueAverageEqualsItself() {
        MovingAverage avg = new MovingAverage(3);
        assertEquals(10.0, avg.add(10.0), 1e-9);
    }

    @Test
    void warmupPeriodAveragesOnlyValuesSeenSoFar() {
        MovingAverage avg = new MovingAverage(3);
        avg.add(10.0);
        // Only two values added so far into a window of 3 -- average of
        // {10, 20} is 15, not (10+20)/3.
        assertEquals(15.0, avg.add(20.0), 1e-9);
    }

    @Test
    void fullWindowAveragesAllThree() {
        MovingAverage avg = new MovingAverage(3);
        avg.add(10.0);
        avg.add(20.0);
        assertEquals(20.0, avg.add(30.0), 1e-9);
    }

    @Test
    void slidingWindowEvictsOldestValue() {
        MovingAverage avg = new MovingAverage(2);
        avg.add(10.0);
        avg.add(20.0);
        // Window is now full at {10, 20}; adding 30 evicts 10 -> {20, 30}.
        assertEquals(25.0, avg.add(30.0), 1e-9);
    }

    @Test
    void rejectsNonPositiveWindowSize() {
        org.junit.jupiter.api.Assertions.assertThrows(IllegalArgumentException.class,
                () -> new MovingAverage(0));
    }
}
