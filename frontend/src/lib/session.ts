export const SESSION_STORAGE_KEY = "meydanai:session";

export function getSessionToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(SESSION_STORAGE_KEY);
}

export function setSessionToken(token: string | null): void {
  if (typeof window === "undefined") return;
  if (token) window.localStorage.setItem(SESSION_STORAGE_KEY, token);
  else window.localStorage.removeItem(SESSION_STORAGE_KEY);
}
