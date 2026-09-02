import { Component, OnDestroy, OnInit, signal } from '@angular/core';
import { Subscription, interval } from 'rxjs';

/**
 * Displays a tick counter that increments once per second while the
 * component is alive. The subscription to the ticking interval MUST be
 * torn down when the component is destroyed -- otherwise the interval
 * keeps firing and updating state forever, leaking memory/CPU for every
 * instance ever created (a very common Angular component bug).
 */
@Component({
  selector: 'app-ticker',
  standalone: true,
  template: `<span>{{ count() }}</span>`,
})
export class TickerComponent implements OnInit, OnDestroy {
  readonly count = signal(0);

  private subscription?: Subscription;

  ngOnInit(): void {
    // BUG: the subscription returned by interval(...).subscribe(...) is
    // never stored/torn down in ngOnDestroy -- this component leaks a
    // live timer subscription for the lifetime of the whole application
    // every time it is created and destroyed.
    interval(1000).subscribe(() => {
      this.count.update((c) => c + 1);
    });
  }

  ngOnDestroy(): void {
    this.subscription?.unsubscribe();
  }
}
