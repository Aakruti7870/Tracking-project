// API client for TrackMyRMC. Base URL from env; all routes under /api.
const RAW_BACKEND = process.env.EXPO_PUBLIC_BACKEND_URL?.trim();

function apiBase(): string {
  if (!RAW_BACKEND) {
    throw {
      status: 0,
      detail: "TrackMyRMC backend is not configured for this build",
    } as ApiError;
  }
  return `${RAW_BACKEND.replace(/\/$/, "")}/api`;
}

export type ApiError = { status: number; detail: string };

export function apiErrorDetail(error: unknown, fallback: string): string {
  return typeof error === "object" && error !== null && "detail" in error && typeof error.detail === "string"
    ? error.detail
    : fallback;
}

export type AuthSessionResponse = {
  access_token: string;
  token_type: string;
  expires_at: string;
  role: string;
  name: string;
};

export type OtpRequestResponse = {
  status: string;
  channel: string;
  expires_in?: number;
  email?: string;
  message?: string;
  dev_otp?: string;
  mfa_setup_required?: boolean;
  passkey_available?: boolean;
  delivery?: { adapter: string; configured: boolean };
};

export type StaffAuthMethodResponse = {
  status: "AUTHENTICATOR_REQUIRED" | "EMAIL_OTP_REQUIRED";
  email: string;
  method: "totp" | "email_otp";
  recovery_available?: boolean;
  message?: string;
};

export type MfaEnrollmentStartResponse = {
  status: "MFA_ENROLLMENT_STARTED";
  issuer: string;
  account: string;
  manual_key: string;
  otpauth_uri: string;
  qr_data_uri?: string | null;
  expires_in: number;
};

export type MfaEnrollmentConfirmResponse = {
  status: "MFA_ENABLED";
  recovery_codes: string[];
  message: string;
};

export type PasskeyReturnMode = "app" | "web";
export type PasskeyStartResponse = {
  request_id: string;
  authorization_url: string;
  expires_in: number;
  email?: string;
};
export type WebAuthnOptionsResponse = Record<string, any> & { ceremony_id: string };
export type PasskeyVerifyResponse = {
  status: "PASSKEY_VERIFIED";
  handoff_code: string;
  return_mode: PasskeyReturnMode;
  expires_in: number;
};
export type PasskeyRegisterResponse = {
  status: "PASSKEY_REGISTERED";
  return_mode: PasskeyReturnMode;
  passkey_count: number;
};

export type PlayReviewRole = "customer" | "plant_owner" | "authority" | "driver";

async function handle<T>(res: Response): Promise<T> {
  let body: any = null;
  try {
    body = await res.json();
  } catch {
    body = null;
  }
  if (!res.ok) {
    const detail =
      (body && (body.detail || body.message)) || `Request failed (${res.status})`;
    throw { status: res.status, detail } as ApiError;
  }
  return body as T;
}

function authHeaders(token: string) {
  return {
    "Content-Type": "application/json",
    Authorization: `Bearer ${token}`,
  };
}

export async function apiPublicGet<T>(path: string): Promise<T> {
  const res = await fetch(`${apiBase()}${path}`);
  return handle<T>(res);
}

export async function apiPublicPost<T>(path: string, body?: any): Promise<T> {
  const res = await fetch(`${apiBase()}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  return handle<T>(res);
}

export async function requestOtp(identifier: string) {
  return apiPublicPost<OtpRequestResponse>("/auth/request-otp", { identifier });
}

export async function verifyOtp(identifier: string, code: string) {
  return apiPublicPost<AuthSessionResponse>("/auth/verify-otp", { identifier, code });
}

export async function requestStaffOtp(identifier: string) {
  return apiPublicPost<OtpRequestResponse>("/auth/staff/request-otp", { identifier });
}

export async function verifyStaffOtp(identifier: string, code: string) {
  return apiPublicPost<AuthSessionResponse>("/auth/staff/verify-otp", { identifier, code });
}

export async function staffAuthMethod(identifier: string) {
  return apiPublicPost<StaffAuthMethodResponse>("/auth/staff/mfa/method", { identifier });
}

export async function verifyStaffTotp(identifier: string, code: string) {
  return apiPublicPost<AuthSessionResponse>("/auth/staff/mfa/verify-totp", { identifier, code });
}

export async function verifyStaffRecovery(identifier: string, recoveryCode: string) {
  return apiPublicPost<AuthSessionResponse>("/auth/staff/mfa/verify-recovery", {
    identifier,
    recovery_code: recoveryCode,
  });
}

export async function startStaffMfaEnrollment(token: string) {
  return apiPost<MfaEnrollmentStartResponse>("/auth/staff/mfa/enroll/start", token);
}

export async function confirmStaffMfaEnrollment(token: string, code: string) {
  return apiPost<MfaEnrollmentConfirmResponse>("/auth/staff/mfa/enroll/confirm", token, { code });
}

export async function startStaffPasskeyAuthentication(
  identifier: string,
  returnMode: PasskeyReturnMode,
) {
  return apiPublicPost<PasskeyStartResponse>("/auth/staff/passkey/authenticate/start", {
    identifier,
    return_mode: returnMode,
  });
}

export async function staffPasskeyAuthenticationOptions(requestId: string) {
  return apiPublicPost<WebAuthnOptionsResponse>("/auth/staff/passkey/authenticate/options", {
    request_id: requestId,
  });
}

export async function verifyStaffPasskeyAuthentication(
  requestId: string,
  ceremonyId: string,
  credential: Record<string, any>,
) {
  return apiPublicPost<PasskeyVerifyResponse>("/auth/staff/passkey/authenticate/verify", {
    request_id: requestId,
    ceremony_id: ceremonyId,
    credential,
  });
}

export async function exchangeStaffPasskeyHandoff(code: string) {
  return apiPublicPost<AuthSessionResponse>("/auth/staff/passkey/exchange", { code });
}

export async function startStaffPasskeyRegistration(
  token: string,
  actorCode: string,
  returnMode: PasskeyReturnMode,
) {
  return apiPost<PasskeyStartResponse>("/auth/staff/passkey/register/start", token, {
    actor_code: actorCode,
    return_mode: returnMode,
  });
}

export async function staffPasskeyRegistrationOptions(requestId: string) {
  return apiPublicPost<WebAuthnOptionsResponse>("/auth/staff/passkey/register/options", {
    request_id: requestId,
  });
}

export async function verifyStaffPasskeyRegistration(
  requestId: string,
  ceremonyId: string,
  credential: Record<string, any>,
) {
  return apiPublicPost<PasskeyRegisterResponse>("/auth/staff/passkey/register/verify", {
    request_id: requestId,
    ceremony_id: ceremonyId,
    credential,
  });
}

export async function removeStaffPasskey(
  token: string,
  credentialId: string,
  actorCode: string,
) {
  return apiPost<{ status: "PASSKEY_REMOVED" }>("/auth/staff/passkey/remove", token, {
    credential_id: credentialId,
    actor_code: actorCode,
  });
}

export async function playReviewLogin(role: PlayReviewRole, accessCode: string) {
  return apiPublicPost<AuthSessionResponse>("/auth/play-review", {
    role,
    access_code: accessCode,
  });
}

export async function startGoogleStaffLogin() {
  return apiPublicGet<{ authorization_url: string }>("/auth/google/start");
}

export async function exchangeGoogleStaffCode(code: string) {
  return apiPublicPost<AuthSessionResponse>("/auth/google/exchange", { code });
}

export async function demoLogin(role: string) {
  return apiPublicPost<AuthSessionResponse>("/auth/demo-login", { role });
}

export async function apiGet<T>(path: string, token: string): Promise<T> {
  const res = await fetch(`${apiBase()}${path}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  return handle<T>(res);
}

export async function apiPost<T>(path: string, token: string, body?: any): Promise<T> {
  const res = await fetch(`${apiBase()}${path}`, {
    method: "POST",
    headers: authHeaders(token),
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  return handle<T>(res);
}

export async function apiPut<T>(path: string, token: string, body?: any): Promise<T> {
  const res = await fetch(`${apiBase()}${path}`, {
    method: "PUT",
    headers: authHeaders(token),
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  return handle<T>(res);
}

export async function apiPatch<T>(path: string, token: string, body?: any): Promise<T> {
  const res = await fetch(`${apiBase()}${path}`, {
    method: "PATCH",
    headers: authHeaders(token),
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  return handle<T>(res);
}

export async function apiDelete<T>(path: string, token: string): Promise<T> {
  const res = await fetch(`${apiBase()}${path}`, {
    method: "DELETE",
    headers: { Authorization: `Bearer ${token}` },
  });
  return handle<T>(res);
}
