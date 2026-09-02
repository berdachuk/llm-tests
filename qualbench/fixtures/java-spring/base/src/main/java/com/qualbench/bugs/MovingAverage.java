package com.qualbench.bugs;

import java.util.ArrayDeque;
import java.util.Deque;

/**
 * Maintains a simple moving average over the last {@code windowSize}
 * values added.
 */
public class MovingAverage {

    private final int windowSize;
    private final Deque<Double> window = new ArrayDeque<>();
    private double sum = 0.0;

    public MovingAverage(int windowSize) {
        if (windowSize <= 0) {
            throw new IllegalArgumentException("windowSize must be positive");
        }
        this.windowSize = windowSize;
    }

    /**
     * Adds a new value, evicting the oldest value once the window exceeds
     * {@code windowSize} entries, and returns the current average over the
     * values currently in the window.
     */
    public double add(double value) {
        window.addLast(value);
        sum += value;
        if (window.size() > windowSize) {
            double removed = window.removeFirst();
            sum -= removed;
        }
        // BUG: divides by the configured windowSize instead of the actual
        // number of values currently in the window. This is only correct
        // once the window has filled up; during warm-up (fewer than
        // windowSize values added so far), it understates the average by
        // dividing a small sum by a too-large denominator.
        return sum / windowSize;
    }
}
