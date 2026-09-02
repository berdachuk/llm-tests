import { TestBed } from '@angular/core/testing';
import { TodoListComponent, Todo } from './todo-list.component';

describe('TodoListComponent', () => {
  it('emits a new array reference without mutating the original input array', () => {
    const fixture = TestBed.createComponent(TodoListComponent);
    const original: Todo[] = [
      { id: 1, text: 'Buy milk', done: false },
      { id: 2, text: 'Walk dog', done: false },
    ];
    fixture.componentInstance.todos = original;
    fixture.detectChanges();

    let emitted: Todo[] | undefined;
    fixture.componentInstance.toggle.subscribe((todos: Todo[]) => (emitted = todos));

    fixture.componentInstance.onToggle(1);

    expect(emitted).toBeDefined();
    expect(emitted).not.toBe(original);

    const originalTodo1 = original.find((t) => t.id === 1)!;
    // The original input array/objects must not be mutated in place.
    expect(originalTodo1.done).toBe(false);

    const emittedTodo1 = emitted!.find((t) => t.id === 1)!;
    expect(emittedTodo1.done).toBe(true);
  });

  it('does not affect other todos when toggling one', () => {
    const fixture = TestBed.createComponent(TodoListComponent);
    fixture.componentInstance.todos = [
      { id: 1, text: 'Buy milk', done: false },
      { id: 2, text: 'Walk dog', done: false },
    ];
    fixture.detectChanges();

    let emitted: Todo[] | undefined;
    fixture.componentInstance.toggle.subscribe((todos: Todo[]) => (emitted = todos));

    fixture.componentInstance.onToggle(2);

    const todo1 = emitted!.find((t) => t.id === 1)!;
    const todo2 = emitted!.find((t) => t.id === 2)!;
    expect(todo1.done).toBe(false);
    expect(todo2.done).toBe(true);
  });
});
