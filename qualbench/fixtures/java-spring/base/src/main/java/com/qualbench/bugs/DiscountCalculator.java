package com.qualbench.bugs;

import java.math.BigDecimal;
import java.math.RoundingMode;

/**
 * Applies a percentage discount to a price.
 */
public class DiscountCalculator {

    /**
     * Applies {@code discountPercent} (e.g. 15 for 15%) to {@code price} and
     * returns the discounted price, rounded to 2 decimal places (HALF_UP).
     */
    public BigDecimal applyDiscount(BigDecimal price, BigDecimal discountPercent) {
        if (price == null || discountPercent == null) {
            throw new IllegalArgumentException("price and discountPercent must not be null");
        }
        // BUG: divides by 100 using integer-like scale without proper
        // rounding context, and forgets to actually subtract the discount
        // from the price -- it returns the discount amount instead of the
        // discounted price.
        BigDecimal discountAmount = price.multiply(discountPercent).divide(BigDecimal.valueOf(100));
        return discountAmount.setScale(2, RoundingMode.HALF_UP);
    }
}
