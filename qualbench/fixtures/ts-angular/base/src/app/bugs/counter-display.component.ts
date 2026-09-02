import { Component } from '@angular/core';
import { CounterService } from './counter.service';

/**
 * Displays and increments the shared app-wide counter. Every instance of
 * this component (e.g. two siblings on the same page) must read/write the
 * SAME underlying counter, since CounterService is `providedIn: 'root'`.
 */
@Component({
  selector: 'app-counter-display',
  standalone: true,
  // BUG: re-declaring CounterService in this component's own `providers`
  // array creates a NEW, component-scoped instance of the service for
  // every instance of CounterDisplayComponent, shadowing the root
  // singleton. Two sibling instances of this component on the same page
  // end up with completely independent counters instead of sharing one,
  // and incrementing one never affects the other.
  providers: [CounterService],
  template: `
    <button (click)="counter.increment()">+1</button>
    <span>{{ counter.count() }}</span>
  `,
})
export class CounterDisplayComponent {
  constructor(readonly counter: CounterService) {}
}
