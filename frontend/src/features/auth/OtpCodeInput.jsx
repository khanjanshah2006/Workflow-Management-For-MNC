import React from "react";

export const OTP_LENGTH = 6;

/**
 * Single numeric input for a 6-digit TOTP code.
 * Non-digits are dropped, and onComplete fires as soon as the 6th digit is entered.
 */
export function OtpCodeInput({
  id = "otp-code",
  value,
  onChange,
  onComplete,
  disabled = false,
  hasError = false,
  autoFocus = true,
  inputRef,
}) {
  const handleChange = (e) => {
    const digits = e.target.value.replace(/\D/g, "").slice(0, OTP_LENGTH);
    onChange(digits);
    if (digits.length === OTP_LENGTH && digits !== value && onComplete) {
      onComplete(digits);
    }
  };

  return (
    <input
      id={id}
      ref={inputRef}
      type="text"
      inputMode="numeric"
      pattern="[0-9]*"
      autoComplete="one-time-code"
      maxLength={OTP_LENGTH}
      className={`form-input mfa-code-input ${hasError ? "form-input-error" : ""}`}
      placeholder="000000"
      value={value}
      onChange={handleChange}
      disabled={disabled}
      autoFocus={autoFocus}
      aria-invalid={hasError || undefined}
    />
  );
}

export default OtpCodeInput;
