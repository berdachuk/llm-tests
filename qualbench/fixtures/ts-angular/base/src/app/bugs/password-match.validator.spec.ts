import { FormControl, FormGroup } from '@angular/forms';
import { passwordMatchValidator } from './password-match.validator';

describe('passwordMatchValidator', () => {
  function buildGroup(password: string, confirmPassword: string): FormGroup {
    return new FormGroup(
      {
        password: new FormControl(password),
        confirmPassword: new FormControl(confirmPassword),
      },
      { validators: passwordMatchValidator() },
    );
  }

  it('reports no error when passwords match', () => {
    const group = buildGroup('secret123', 'secret123');
    expect(group.errors).toBeNull();
    expect(group.get('confirmPassword')?.hasError('passwordMismatch')).toBe(false);
  });

  it('reports a passwordMismatch error when passwords differ', () => {
    const group = buildGroup('secret123', 'different456');
    expect(group.hasError('passwordMismatch')).toBe(true);
    expect(group.get('confirmPassword')?.hasError('passwordMismatch')).toBe(true);
  });

  it('clears the error once the user corrects confirmPassword to match', () => {
    const group = buildGroup('secret123', 'different456');
    expect(group.hasError('passwordMismatch')).toBe(true);

    group.get('confirmPassword')?.setValue('secret123');
    group.updateValueAndValidity();

    expect(group.errors).toBeNull();
    expect(group.get('confirmPassword')?.hasError('passwordMismatch')).toBe(false);
  });
});
