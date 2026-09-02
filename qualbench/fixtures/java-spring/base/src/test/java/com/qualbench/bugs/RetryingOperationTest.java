package com.qualbench.bugs;

import org.junit.jupiter.api.Test;

import java.util.concurrent.atomic.AtomicInteger;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

class RetryingOperationTest {

    private final RetryingOperation retrying = new RetryingOperation();

    @Test
    void succeedsImmediatelyIfFirstAttemptSucceeds() {
        AtomicInteger calls = new AtomicInteger();
        String result = retrying.runWithRetry(() -> {
            calls.incrementAndGet();
            return "ok";
        }, 3);
        assertEquals("ok", result);
        assertEquals(1, calls.get());
    }

    @Test
    void succeedsOnThirdAttemptAfterTwoFailures() {
        AtomicInteger calls = new AtomicInteger();
        String result = retrying.runWithRetry(() -> {
            int n = calls.incrementAndGet();
            if (n < 3) {
                throw new RuntimeException("transient failure #" + n);
            }
            return "ok-on-attempt-" + n;
        }, 5);
        assertEquals("ok-on-attempt-3", result);
        assertEquals(3, calls.get());
    }

    @Test
    void reThrowsLastFailureWhenAllAttemptsFail() {
        AtomicInteger calls = new AtomicInteger();
        RuntimeException thrown = assertThrows(RuntimeException.class, () ->
                retrying.runWithRetry(() -> {
                    int n = calls.incrementAndGet();
                    throw new RuntimeException("failure #" + n);
                }, 3));
        assertEquals(3, calls.get());
        // Must surface the LAST failure's message, not a generic message
        // and not silently swallow it as a null return.
        assertEquals("failure #3", thrown.getMessage());
    }

    @Test
    void rejectsNonPositiveMaxAttempts() {
        assertThrows(IllegalArgumentException.class, () -> retrying.runWithRetry(() -> "x", 0));
    }
}
