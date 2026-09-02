package com.qualbench.bugs;

import java.util.concurrent.Callable;

/**
 * Retries a flaky operation up to a fixed number of times, re-throwing the
 * last failure if every attempt fails.
 */
public class RetryingOperation {

    /**
     * Calls {@code operation} up to {@code maxAttempts} times. Returns the
     * first successful result. If every attempt throws, re-throws the
     * exception from the LAST attempt (not the first), wrapped in a
     * RuntimeException if it isn't one already.
     */
    public <T> T runWithRetry(Callable<T> operation, int maxAttempts) {
        if (maxAttempts <= 0) {
            throw new IllegalArgumentException("maxAttempts must be positive");
        }
        Exception lastFailure = null;
        for (int attempt = 1; attempt <= maxAttempts; attempt++) {
            try {
                return operation.call();
            } catch (Exception e) {
                // BUG: silently swallows every failure and never records
                // it, so once all attempts are exhausted there is nothing
                // to re-throw -- the method falls through and returns null
                // instead of surfacing the last failure to the caller.
                continue;
            }
        }
        return null;
    }
}
