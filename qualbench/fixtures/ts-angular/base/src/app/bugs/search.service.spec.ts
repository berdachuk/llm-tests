import { TestBed } from '@angular/core/testing';
import { SearchService } from './search.service';

describe('SearchService', () => {
  let service: SearchService;

  beforeEach(() => {
    vi.useFakeTimers();
    TestBed.configureTestingModule({});
    service = TestBed.inject(SearchService);
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('only ever surfaces results for the most recently issued query', () => {
    const emitted: string[][] = [];
    service.results().subscribe((results) => emitted.push(results));

    // "abcdef" (len 6) takes 60ms to resolve; issued first.
    service.setQuery('abcdef');
    // 10ms later the user has typed more and the query is now "ab" (len 2),
    // which only takes 20ms -- it resolves at t=30ms, well before the
    // slower "abcdef" query (which resolves at t=10+60=70ms).
    vi.advanceTimersByTime(10);
    service.setQuery('ab');

    // Advance past when "ab" resolves (t=30ms) but before "abcdef" would.
    vi.advanceTimersByTime(25); // now at t=35ms
    expect(emitted.length).toBe(1);
    expect(emitted[0]).toEqual(['ab-result-1', 'ab-result-2']);

    // Advance past when the stale "abcdef" query would have resolved
    // (t=70ms). A correct (switchMap-based) implementation must have
    // cancelled it when "ab" was issued, so nothing further should ever
    // be emitted.
    vi.advanceTimersByTime(60); // now at t=95ms
    expect(emitted.length).toBe(1);
    expect(emitted[0]).toEqual(['ab-result-1', 'ab-result-2']);
  });

  it('still resolves a single query normally when nothing supersedes it', () => {
    const emitted: string[][] = [];
    service.results().subscribe((results) => emitted.push(results));

    service.setQuery('hi');
    vi.advanceTimersByTime(20);

    expect(emitted).toEqual([['hi-result-1', 'hi-result-2']]);
  });
});
