import { TestBed } from '@angular/core/testing';
import { ShoppingCart } from './shopping-cart';

describe('ShoppingCart', () => {
  let cart: ShoppingCart;

  beforeEach(() => {
    TestBed.configureTestingModule({});
    cart = TestBed.inject(ShoppingCart);
  });

  it('starts with a total of zero', () => {
    expect(cart.total).toBe(0);
  });

  it('recomputes the total after adding an item', () => {
    cart.addItem({ id: 'a', price: 500, quantity: 2 });
    expect(cart.total).toBe(1000);
  });

  it('recomputes the total after adding a second item', () => {
    cart.addItem({ id: 'a', price: 500, quantity: 2 });
    cart.addItem({ id: 'b', price: 300, quantity: 1 });
    expect(cart.total).toBe(1300);
  });

  it('recomputes the total after removing an item', () => {
    cart.addItem({ id: 'a', price: 500, quantity: 2 });
    cart.addItem({ id: 'b', price: 300, quantity: 1 });
    cart.removeItem('a');
    expect(cart.total).toBe(300);
  });
});
