import { ChangeDetectionStrategy, Component, EventEmitter, Input, Output } from '@angular/core';

export interface Todo {
  id: number;
  text: string;
  done: boolean;
}

/**
 * An OnPush component that displays a list of todos and lets the parent
 * toggle one via `toggle`. Because it runs OnPush, Angular only checks
 * this component for changes when one of its @Input() REFERENCES changes
 * (or a signal/event fires) -- mutating the existing array/object in
 * place is not enough to trigger a re-render from a parent's perspective,
 * and (worse here) corrupts the parent's original array unexpectedly.
 */
@Component({
  selector: 'app-todo-list',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @for (todo of todos; track todo.id) {
      <label>
        <input type="checkbox" [checked]="todo.done" (change)="onToggle(todo.id)" />
        {{ todo.text }}
      </label>
    }
  `,
})
export class TodoListComponent {
  @Input() todos: Todo[] = [];
  @Output() toggle = new EventEmitter<Todo[]>();

  onToggle(id: number): void {
    // BUG: mutates the existing `todos` array and its element objects in
    // place (find + direct property assignment) instead of producing a
    // new array/object, then emits the SAME array reference back out.
    // Under OnPush, and for any consumer relying on immutable data (e.g.
    // to detect "did anything change" via reference equality), this
    // silently breaks change detection and violates the immutability
    // contract implied by @Input().
    const todo = this.todos.find((t) => t.id === id);
    if (todo) {
      todo.done = !todo.done;
    }
    this.toggle.emit(this.todos);
  }
}
