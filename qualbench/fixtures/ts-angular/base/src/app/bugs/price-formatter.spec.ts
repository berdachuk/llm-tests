import { formatPrice } from './price-formatter';

describe('formatPrice', () => {
  it('formats whole dollars with no cents', () => {
    expect(formatPrice(1000)).toBe('$10.00');
  });

  it('pads single-digit cent remainders with a leading zero', () => {
    expect(formatPrice(5)).toBe('$0.05');
  });

  it('pads ten-cent amounts to two digits', () => {
    expect(formatPrice(1050)).toBe('$10.50');
  });

  it('formats zero', () => {
    expect(formatPrice(0)).toBe('$0.00');
  });

  it('formats amounts under a dollar with no leading dollar digits', () => {
    expect(formatPrice(99)).toBe('$0.99');
  });
});
