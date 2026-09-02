package com.qualbench.bugs;

import java.math.BigDecimal;
import java.util.Objects;

/**
 * An immutable value object representing an amount in a given currency.
 * Two Money instances are equal if they have the same currency and the
 * same numeric amount (regardless of trailing zeros / scale, e.g. 2.50 and
 * 2.5 are equal), and must produce equal hashCode()s when equal(), per the
 * general equals/hashCode contract.
 */
public final class Money {

    private final BigDecimal amount;
    private final String currency;

    public Money(BigDecimal amount, String currency) {
        this.amount = Objects.requireNonNull(amount);
        this.currency = Objects.requireNonNull(currency);
    }

    public BigDecimal getAmount() {
        return amount;
    }

    public String getCurrency() {
        return currency;
    }

    @Override
    public boolean equals(Object o) {
        if (this == o) return true;
        if (!(o instanceof Money)) return false;
        Money other = (Money) o;
        // compareTo ignores scale differences (2.50 vs 2.5), matching the
        // documented equality contract above.
        return amount.compareTo(other.amount) == 0 && currency.equals(other.currency);
    }

    @Override
    public int hashCode() {
        // BUG: hashCode uses amount.hashCode(), which (unlike compareTo)
        // DOES take BigDecimal scale into account -- so new
        // Money(2.50, "USD") and new Money(2.5, "USD") are equal() but
        // produce different hashCode()s, violating the equals/hashCode
        // contract and silently breaking HashSet/HashMap lookups.
        return Objects.hash(amount.hashCode(), currency);
    }
}
