package com.qualbench.bugs;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

class LruCacheTest {

    @Test
    void evictsLeastRecentlyInsertedWhenNeverRead() {
        LruCache<String, Integer> cache = new LruCache<>(2);
        cache.put("a", 1);
        cache.put("b", 2);
        cache.put("c", 3); // should evict "a" (never read, oldest)
        assertFalse(cache.containsKey("a"));
        assertTrue(cache.containsKey("b"));
        assertTrue(cache.containsKey("c"));
    }

    @Test
    void readingAnEntryProtectsItFromEviction() {
        LruCache<String, Integer> cache = new LruCache<>(2);
        cache.put("a", 1);
        cache.put("b", 2);
        cache.get("a"); // "a" was just read -- it is now the MOST recently used
        cache.put("c", 3); // must evict "b" (least recently used), not "a"
        assertTrue(cache.containsKey("a"), "'a' was just read and must survive eviction");
        assertFalse(cache.containsKey("b"), "'b' is now the least recently used and should be evicted");
        assertTrue(cache.containsKey("c"));
    }

    @Test
    void capacityIsRespected() {
        LruCache<String, Integer> cache = new LruCache<>(3);
        cache.put("a", 1);
        cache.put("b", 2);
        cache.put("c", 3);
        cache.put("d", 4);
        assertTrue(cache.size() <= 3);
    }

    @Test
    void rejectsNonPositiveCapacity() {
        org.junit.jupiter.api.Assertions.assertThrows(IllegalArgumentException.class,
                () -> new LruCache<String, Integer>(0));
    }
}
