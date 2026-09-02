import { AbstractControl, ValidationErrors, ValidatorFn } from '@angular/forms';

/**
 * A cross-field validator to be applied at the FormGroup level, checking
 * that the 'password' and 'confirmPassword' controls have matching
 * values. Should set a `passwordMismatch` error on the confirmPassword
 * control when they differ, and clear it when they match.
 */
export function passwordMatchValidator(): ValidatorFn {
  return (group: AbstractControl): ValidationErrors | null => {
    const password = group.get('password');
    const confirmPassword = group.get('confirmPassword');
    if (!password || !confirmPassword) {
      return null;
    }

    // BUG: compares confirmPassword's value to ITSELF instead of to
    // password's value, so this validator always considers the passwords
    // to "match" (mismatch is never detected) regardless of what the user
    // actually typed.
    if (confirmPassword.value !== confirmPassword.value) {
      confirmPassword.setErrors({ passwordMismatch: true });
      return { passwordMismatch: true };
    }

    if (confirmPassword.hasError('passwordMismatch')) {
      const errors = { ...confirmPassword.errors };
      delete errors['passwordMismatch'];
      confirmPassword.setErrors(Object.keys(errors).length ? errors : null);
    }
    return null;
  };
}
