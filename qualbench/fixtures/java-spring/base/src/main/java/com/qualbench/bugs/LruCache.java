package com.qualbench.bugs;

import java.util.LinkedHashMap;
import java.util.Map;

/**
 * A fixed-capacity cache that evicts the Least Recently Used entry when
 * full. "Recently used" must be updated on both writes (put) AND reads
 * (get) -- reading an entry counts as using it, so it should not be the
 * next one evicted.
 */
public class LruCache<K, V> {

    private final int capacity;
    private final Map<K, V> map;

    public LruCache(int capacity) {
        if (capacity <= 0) {
            throw new IllegalArgumentException("capacity must be positive");
        }
        this.capacity = capacity;
        // BUG: accessOrder is left at its default (false, insertion
        // order), so LinkedHashMap never reorders entries on get() -- only
        // insertion/re-insertion order is tracked, meaning a recently READ
        // entry is treated the same as if it had never been touched, and
        // can be evicted next even though it was just accessed.
        this.map = new LinkedHashMap<>(capacity, 0.75f, false) {
            @Override
            protected boolean removeEldestEntry(Map.Entry<K, V> eldest) {
                return size() > LruCache.this.capacity;
            }
        };
    }

    public void put(K key, V value) {
        map.put(key, value);
    }

    public V get(K key) {
        return map.get(key);
    }

    public boolean containsKey(K key) {
        return map.containsKey(key);
    }

    public int size() {
        return map.size();
    }
}
