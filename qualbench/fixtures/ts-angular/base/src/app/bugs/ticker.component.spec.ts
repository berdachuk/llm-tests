import { TestBed } from '@angular/core/testing';
import { TickerComponent } from './ticker.component';

describe('TickerComponent', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    TestBed.configureTestingModule({ imports: [TickerComponent] });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('increments the count once per second while alive', () => {
    const fixture = TestBed.createComponent(TickerComponent);
    fixture.detectChanges();

    vi.advanceTimersByTime(3000);
    expect(fixture.componentInstance.count()).toBe(3);

    fixture.destroy();
  });

  it('stops ticking after the component is destroyed', () => {
    const fixture = TestBed.createComponent(TickerComponent);
    fixture.detectChanges();

    vi.advanceTimersByTime(2000);
    expect(fixture.componentInstance.count()).toBe(2);

    fixture.destroy();

    // After destroy, the interval must no longer be firing -- the count
    // signal must not change even though timers keep advancing.
    vi.advanceTimersByTime(5000);
    expect(fixture.componentInstance.count()).toBe(2);
  });
});
