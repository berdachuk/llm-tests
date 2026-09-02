package com.qualbench.bugs;

import org.springframework.stereotype.Component;

/**
 * A singleton Spring bean that generates sequential request IDs of the
 * form "REQ-<currentUserId>-<sequence>" for the currently-processing
 * request. Because this bean is a singleton (Spring's default scope), it
 * is shared across all concurrently-handled HTTP requests in the
 * application -- it must never hold per-request mutable state as an
 * instance field.
 */
@Component
public class RequestIdGenerator {

    // BUG: currentUserId is stored as a mutable instance field on a
    // singleton bean. Under concurrent requests, one thread's call to
    // startRequest(userId) can be overwritten by another thread's call
    // before the first thread reaches generateId(), so a request can end
    // up stamped with a DIFFERENT user's ID than the one that started it.
    private String currentUserId;
    private int sequence = 0;

    /** Called once at the start of handling a request for the given user. */
    public void startRequest(String userId) {
        this.currentUserId = userId;
    }

    /** Called to produce the next ID for the request started above. */
    public synchronized String generateId() {
        sequence++;
        return "REQ-" + currentUserId + "-" + sequence;
    }
}
