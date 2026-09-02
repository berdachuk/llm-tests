import { Injectable, signal } from '@angular/core';

/**
 * A counter meant to be shared application-wide as a single instance --
 * every component that injects CounterService should see the SAME count,
 * and incrementing it from any one place must be visible everywhere else
 * it's injected.
 */
@Injectable({ providedIn: 'root' })
export class CounterService {
  readonly count = signal(0);

  increment(): void {
    this.count.update((c) => c + 1);
  }
}
