package com.qualbench.bugs;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.Timeout;

import java.util.concurrent.CountDownLatch;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.TimeUnit;

import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * These tests deterministically force the interleaving that a shared
 * singleton-with-mutable-field bug produces, rather than relying on timing
 * luck: two "requests" are made to race across a fixed barrier sequence so
 * the bug reproduces every single run, not just occasionally.
 */
class RequestIdGeneratorTest {

    @Test
    @Timeout(10)
    void concurrentRequestsMustNotCrossContaminateUserIds() throws Exception {
        RequestIdGenerator generator = new RequestIdGenerator();
        ExecutorService pool = Executors.newFixedThreadPool(2);

        CountDownLatch bothStarted = new CountDownLatch(2);
        CountDownLatch userAStartedRequest = new CountDownLatch(1);

        // "Request" A: starts first, then deliberately waits for request B
        // to also call startRequest() before generating its ID -- this is
        // exactly the interleaving a shared singleton field allows under
        // real concurrent HTTP traffic.
        Future<String> userAId = pool.submit(() -> {
            generator.startRequest("alice");
            userAStartedRequest.countDown();
            bothStarted.countDown();
            bothStarted.await(5, TimeUnit.SECONDS);
            // At this point, if state is shared, currentUserId may have
            // been overwritten by request B's startRequest("bob") call.
            return generator.generateId();
        });

        // "Request" B: waits until A has started, then starts its own
        // request for a different user before A generates its ID.
        Future<String> userBId = pool.submit(() -> {
            userAStartedRequest.await(5, TimeUnit.SECONDS);
            generator.startRequest("bob");
            bothStarted.countDown();
            bothStarted.await(5, TimeUnit.SECONDS);
            return generator.generateId();
        });

        String aliceResult = userAId.get(5, TimeUnit.SECONDS);
        String bobResult = userBId.get(5, TimeUnit.SECONDS);
        pool.shutdown();

        // Request A must produce an ID stamped with "alice", regardless of
        // what request B did concurrently. A shared mutable field breaks
        // this by letting B's startRequest("bob") leak into A's result.
        assertTrue(aliceResult.contains("alice"),
                "expected request A's id to contain 'alice' but was: " + aliceResult);
        assertTrue(bobResult.contains("bob"),
                "expected request B's id to contain 'bob' but was: " + bobResult);
    }
}
