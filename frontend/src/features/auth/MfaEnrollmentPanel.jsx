import React, { useEffect, useRef, useState } from "react";
import QRCode from "qrcode";
import { authApi } from "../../api/authApi";
import { buildOtpauthUri, formatOtpSecret, normalizeOtpSecret } from "../../auth/otpauth";
import OtpCodeInput, { OTP_LENGTH } from "./OtpCodeInput";
import "./LoginPage.css";

/**
 * TOTP enrolment (US-31): POST /api/v1/auth/mfa/setup, show the secret as a QR code
 * plus copyable text, then confirm with POST /api/v1/auth/mfa/verify.
 *
 * Used for forced admin enrolment (bearerToken = the mfa_setup token) and for
 * voluntary enrolment from /account/security (no bearerToken: the access token is used).
 *
 * @param {Object} props
 * @param {string} [props.bearerToken] mfa_setup token; omit to use the signed-in session
 * @param {string} props.email Account email for the authenticator label
 * @param {(response: Object) => (void|Promise<void>)} props.onVerified Called with the verify response
 * @param {(error: Object) => (string|null)} [props.onError] Maps an error to a message to show,
 *   or returns null when the caller handled it (e.g. navigated away)
 */
export function MfaEnrollmentPanel({ bearerToken, email, onVerified, onError }) {
  const [setupData, setSetupData] = useState(null);
  const [setupError, setSetupError] = useState(null);
  const [setupAttempt, setSetupAttempt] = useState(0);
  const [qrSrc, setQrSrc] = useState("");
  const [isCopied, setIsCopied] = useState(false);
  const [code, setCode] = useState("");
  const [verifyError, setVerifyError] = useState(null);
  const [isVerifying, setIsVerifying] = useState(false);

  // Latest error mapper, read from effects without re-running them
  const onErrorRef = useRef(onError);
  useEffect(() => {
    onErrorRef.current = onError;
  });

  const describeError = (err, fallback) => {
    if (onErrorRef.current) return onErrorRef.current(err);
    return err?.message || fallback;
  };

  // Request (or re-use) the TOTP secret. The backend keeps an unverified secret,
  // so repeating the call does not invalidate an authenticator already scanned.
  useEffect(() => {
    let cancelled = false;
    authApi
      .mfaSetup(bearerToken)
      .then((data) => {
        if (!cancelled) {
          setSetupError(null);
          setSetupData(data);
        }
      })
      .catch((err) => {
        if (cancelled) return;
        const mapper = onErrorRef.current;
        const message = mapper ? mapper(err) : err?.message || "Could not start MFA setup.";
        if (message) setSetupError(message);
      });
    return () => {
      cancelled = true;
    };
  }, [bearerToken, setupAttempt]);

  const otpauthUri = setupData?.secret
    ? buildOtpauthUri({ email, secret: setupData.secret })
    : "";

  useEffect(() => {
    if (!otpauthUri) return undefined;
    let cancelled = false;
    QRCode.toDataURL(otpauthUri, { margin: 1, width: 192, errorCorrectionLevel: "M" })
      .then((src) => {
        if (!cancelled) setQrSrc(src);
      })
      .catch(() => {
        if (!cancelled) setQrSrc("");
      });
    return () => {
      cancelled = true;
    };
  }, [otpauthUri]);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(normalizeOtpSecret(setupData?.secret));
      setIsCopied(true);
      setTimeout(() => setIsCopied(false), 2000);
    } catch {
      setIsCopied(false);
    }
  };

  const submitCode = async (value) => {
    if (isVerifying || value.length !== OTP_LENGTH) return;
    setIsVerifying(true);
    setVerifyError(null);
    try {
      const response = await authApi.mfaVerify(value, bearerToken);
      await onVerified(response);
    } catch (err) {
      const message = describeError(err, "Verification failed. Please try again.");
      if (message) {
        setVerifyError(message);
        setCode("");
      }
    } finally {
      setIsVerifying(false);
    }
  };

  if (setupError) {
    return (
      <div className="login-error-banner" role="alert">
        <span>⚠</span>
        <span style={{ flex: 1 }}>{setupError}</span>
        <button
          type="button"
          className="login-link-btn"
          onClick={() => {
            setSetupError(null);
            setSetupAttempt((n) => n + 1);
          }}
        >
          Retry
        </button>
      </div>
    );
  }

  if (!setupData) {
    return <p className="mfa-muted">Preparing your authenticator secret...</p>;
  }

  return (
    <div className="mfa-enrollment">
      <ol className="mfa-steps">
        <li>Open an authenticator app (Google Authenticator, Microsoft Authenticator, 1Password, Authy).</li>
        <li>Scan the QR code, or enter the secret manually.</li>
        <li>Enter the 6-digit code the app shows.</li>
      </ol>

      <div className="mfa-qr-wrapper">
        {qrSrc ? (
          <img
            src={qrSrc}
            width={192}
            height={192}
            alt="QR code for adding WorkSphere to an authenticator app"
            className="mfa-qr"
          />
        ) : (
          <div className="mfa-qr mfa-qr-placeholder">Generating QR code...</div>
        )}
      </div>

      <div className="form-group">
        <label className="form-label" htmlFor="mfa-secret">
          Secret key
        </label>
        <div className="mfa-secret-row">
          <code id="mfa-secret" className="mfa-secret">
            {formatOtpSecret(setupData.secret)}
          </code>
          <button type="button" className="mfa-copy-btn" onClick={handleCopy}>
            {isCopied ? "✓ Copied" : "Copy"}
          </button>
        </div>
      </div>

      {setupData.current_otp && (
        <div className="mfa-dev-hint" role="note">
          <strong>Dev only:</strong> current code is <code>{setupData.current_otp}</code>
        </div>
      )}

      <form
        className="login-form"
        onSubmit={(e) => {
          e.preventDefault();
          submitCode(code);
        }}
        noValidate
      >
        <div className="form-group">
          <label className="form-label" htmlFor="mfa-enroll-code">
            Verification code
          </label>
          <OtpCodeInput
            id="mfa-enroll-code"
            value={code}
            onChange={(value) => {
              setCode(value);
              if (verifyError) setVerifyError(null);
            }}
            onComplete={submitCode}
            disabled={isVerifying}
            hasError={Boolean(verifyError)}
            autoFocus={false}
          />
          {verifyError && <span className="field-error">{verifyError}</span>}
        </div>

        <button
          type="submit"
          className="login-submit-btn"
          disabled={isVerifying || code.length !== OTP_LENGTH}
        >
          {isVerifying ? "Verifying..." : "Verify and enable MFA"}
        </button>
      </form>
    </div>
  );
}

export default MfaEnrollmentPanel;
