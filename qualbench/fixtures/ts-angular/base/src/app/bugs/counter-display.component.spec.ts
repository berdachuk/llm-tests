import { Component } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { CounterDisplayComponent } from './counter-display.component';
import { CounterService } from './counter.service';

@Component({
  selector: 'app-host',
  standalone: true,
  imports: [CounterDisplayComponent],
  template: `<app-counter-display></app-counter-display><app-counter-display></app-counter-display>`,
})
class HostComponent {}

describe('CounterDisplayComponent DI scope', () => {
  it('shares a single root-scoped counter across two sibling instances', () => {
    const fixture = TestBed.createComponent(HostComponent);
    fixture.detectChanges();

    const buttons: NodeListOf<HTMLButtonElement> =
      fixture.nativeElement.querySelectorAll('button');
    expect(buttons.length).toBe(2);

    buttons[0].click();
    fixture.detectChanges();

    const rootCounter = TestBed.inject(CounterService);
    expect(rootCounter.count()).toBe(1);

    const spans: NodeListOf<HTMLSpanElement> = fixture.nativeElement.querySelectorAll('span');
    // Both sibling instances must reflect the SAME shared count, since
    // CounterService is providedIn: 'root'.
    expect(spans[0].textContent).toContain('1');
    expect(spans[1].textContent).toContain('1');
  });
});
