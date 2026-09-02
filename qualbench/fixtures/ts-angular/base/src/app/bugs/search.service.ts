import { Injectable } from '@angular/core';
import { Observable, Subject } from 'rxjs';
import { map, mergeMap } from 'rxjs/operators';

/**
 * A minimal "search as you type" service: emits the latest search results
 * for the most recently issued query term, discarding results from any
 * earlier, now-superseded queries (a classic race condition when a slow
 * earlier request resolves AFTER a fast later request).
 */
@Injectable({ providedIn: 'root' })
export class SearchService {
  private readonly queries = new Subject<string>();

  /** Simulates a backend call whose latency depends on the query string. */
  search(term: string): Observable<string[]> {
    return new Observable<string[]>((subscriber) => {
      const delayMs = term.length * 10;
      const timer = setTimeout(() => {
        subscriber.next([`${term}-result-1`, `${term}-result-2`]);
        subscriber.complete();
      }, delayMs);
      return () => clearTimeout(timer);
    });
  }

  /** Call this whenever the user types a new query term. */
  setQuery(term: string): void {
    this.queries.next(term);
  }

  /**
   * Stream of results for the LATEST issued query only. If an older query
   * is still in flight when a newer one is issued, the older query's
   * results must never be emitted here -- only the newest query's results
   * should ever reach subscribers.
   */
  results(): Observable<string[]> {
    // BUG: uses mergeMap, which runs every inner search() concurrently and
    // emits each one's results as it resolves -- it does NOT cancel
    // in-flight requests for superseded queries. If an earlier (slower)
    // query resolves after a later (faster) one, its stale results are
    // emitted last and overwrite the correct, newer results downstream.
    // This should use switchMap instead.
    return this.queries.pipe(
      mergeMap((term) => this.search(term)),
      map((results) => results),
    );
  }
}
