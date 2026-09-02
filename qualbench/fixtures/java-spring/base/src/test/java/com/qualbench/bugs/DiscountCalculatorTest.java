package com.qualbench.bugs;

import org.junit.jupiter.api.Test;
import java.math.BigDecimal;
import static org.junit.jupiter.api.Assertions.assertEquals;

class DiscountCalculatorTest {

    private final DiscountCalculator calc = new DiscountCalculator();

    @Test
    void fifteenPercentOffHundred() {
        assertEquals(new BigDecimal("85.00"), calc.applyDiscount(new BigDecimal("100.00"), new BigDecimal("15")));
    }

    @Test
    void zeroPercentKeepsPriceUnchanged() {
        assertEquals(new BigDecimal("42.50"), calc.applyDiscount(new BigDecimal("42.50"), BigDecimal.ZERO));
    }

    @Test
    void hundredPercentOffIsFree() {
        assertEquals(new BigDecimal("0.00"), calc.applyDiscount(new BigDecimal("59.99"), new BigDecimal("100")));
    }

    @Test
    void roundsHalfUpToTwoDecimals() {
        assertEquals(new BigDecimal("9.67"), calc.applyDiscount(new BigDecimal("10.00"), new BigDecimal("3.33")));
    }

    @Test
    void rejectsNullArgs() {
        org.junit.jupiter.api.Assertions.assertThrows(IllegalArgumentException.class,
                () -> calc.applyDiscount(null, BigDecimal.TEN));
    }
}
