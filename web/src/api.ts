const TOKEN_KEY = "quotacompass-api-token";

export function setApiToken(value: string) {
  const token = value.trim();
  if (token) sessionStorage.setItem(TOKEN_KEY, token);
  else sessionStorage.removeItem(TOKEN_KEY);
}

export function hasApiToken() {
  return Boolean(sessionStorage.getItem(TOKEN_KEY));
}

export function apiFetch(input: RequestInfo | URL, init: RequestInit = {}) {
  const headers = new Headers(init.headers);
  const token = sessionStorage.getItem(TOKEN_KEY);
  if (token) headers.set("Authorization", `Bearer ${token}`);
  return fetch(input, { ...init, headers });
}

export function reauthFetch(input: RequestInfo | URL, token = "") {
  const headers = new Headers({ Accept: "application/json" });
  const value = token.trim();
  if (value) headers.set("Authorization", `Bearer ${value}`);
  return fetch(input, { method: "POST", headers });
}
