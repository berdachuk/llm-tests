package com.qualbench.bugs;

import org.junit.jupiter.api.Test;
import java.math.BigDecimal;
import java.util.HashSet;
import java.util.Set;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

class MoneyTest {

    @Test
    void equalAmountsDifferentScaleAreEqual() {
        Money a = new Money(new BigDecimal("2.50"), "USD");
        Money b = new Money(new BigDecimal("2.5"), "USD");
        assertEquals(a, b);
    }

    @Test
    void equalObjectsMustHaveEqualHashCodes() {
        Money a = new Money(new BigDecimal("2.50"), "USD");
        Money b = new Money(new BigDecimal("2.5"), "USD");
        assertEquals(a, b, "precondition: must be equal for this test to be meaningful");
        assertEquals(a.hashCode(), b.hashCode(),
                "equal objects must have equal hashCodes per the equals/hashCode contract");
    }

    @Test
    void hashSetDeduplicatesDifferentlyScaledEqualAmounts() {
        Set<Money> set = new HashSet<>();
        set.add(new Money(new BigDecimal("2.50"), "USD"));
        set.add(new Money(new BigDecimal("2.5"), "USD"));
        assertEquals(1, set.size(), "a HashSet must treat equal Money values as duplicates");
    }

    @Test
    void differentCurrenciesAreNotEqual() {
        Money usd = new Money(new BigDecimal("10.00"), "USD");
        Money eur = new Money(new BigDecimal("10.00"), "EUR");
        assertTrue(!usd.equals(eur));
    }
}
