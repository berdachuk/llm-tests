package com.qualbench.bugs;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.Timeout;

import java.util.concurrent.CountDownLatch;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

class InventoryCounterTest {

    @Test
    void singleThreadedReservationWorks() {
        InventoryCounter counter = new InventoryCounter(10);
        assertTrue(counter.reserve(4));
        assertEquals(6, counter.getAvailable());
        assertTrue(counter.reserve(6));
        assertEquals(0, counter.getAvailable());
        assertEquals(false, counter.reserve(1));
    }

    @Test
    @Timeout(20)
    void concurrentReservationsNeverOversell() throws InterruptedException {
        int initialStock = 1_000;
        int threads = 50;
        int reservationsPerThread = 100; // 50 * 100 = 5000 attempts of size 1 vs 1000 stock
        InventoryCounter counter = new InventoryCounter(initialStock);
        ExecutorService pool = Executors.newFixedThreadPool(threads);
        CountDownLatch start = new CountDownLatch(1);
        AtomicInteger successfulReservations = new AtomicInteger(0);

        for (int t = 0; t < threads; t++) {
            pool.submit(() -> {
                try {
                    start.await();
                    for (int i = 0; i < reservationsPerThread; i++) {
                        if (counter.reserve(1)) {
                            successfulReservations.incrementAndGet();
                        }
                    }
                } catch (InterruptedException e) {
                    Thread.currentThread().interrupt();
                }
            });
        }
        start.countDown();
        pool.shutdown();
        assertTrue(pool.awaitTermination(15, TimeUnit.SECONDS));

        // Exactly initialStock reservations must succeed -- no more (never
        // oversell) and no fewer (no reservation should be lost to a race).
        assertEquals(initialStock, successfulReservations.get());
        assertEquals(0, counter.getAvailable());
    }
}
