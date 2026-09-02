import { Injectable, computed, signal } from '@angular/core';

export interface CartItem {
  id: string;
  price: number; // in cents
  quantity: number;
}

/**
 * Signal-based shopping cart. `total` must always reflect the current sum
 * of price * quantity across all items, recomputed reactively whenever
 * items change.
 */
@Injectable({ providedIn: 'root' })
export class ShoppingCart {
  private readonly _items = signal<CartItem[]>([]);
  readonly items = this._items.asReadonly();

  // BUG: total is computed once from the signal's value at construction
  // time via a plain reduce over items() -- but because it is stored as
  // a plain field (not wrapped in computed()), it never recalculates when
  // _items changes afterward. It becomes permanently stale after the
  // first read.
  readonly total = this._items().reduce((sum, item) => sum + item.price * item.quantity, 0);

  addItem(item: CartItem): void {
    this._items.update((items) => [...items, item]);
  }

  removeItem(id: string): void {
    this._items.update((items) => items.filter((i) => i.id !== id));
  }
}
