package com.qualbench.bugs;

import java.util.concurrent.atomic.AtomicInteger;

/**
 * Thread-safe counter tracking available inventory across concurrent
 * reservation attempts.
 */
public class InventoryCounter {

    // BUG: plain int shared across threads with no synchronization and no
    // atomic operations -- reserve() below has a classic check-then-act
    // race between the read and the decrement, dropping reservations under
    // concurrent load. (Kept as a plain field so the bug is reachable; a
    // correct fix typically introduces an AtomicInteger and a CAS loop, or
    // synchronizes the method.)
    private int available;

    public InventoryCounter(int initialStock) {
        this.available = initialStock;
    }

    /**
     * Attempts to reserve {@code quantity} units. Returns true and
     * decrements available stock if enough units are available; returns
     * false (and leaves stock unchanged) otherwise. Must be safe to call
     * concurrently from many threads without ever allowing available stock
     * to go negative or losing a reservation that should have succeeded.
     */
    public boolean reserve(int quantity) {
        if (available >= quantity) {
            available -= quantity;
            return true;
        }
        return false;
    }

    public int getAvailable() {
        return available;
    }
}
