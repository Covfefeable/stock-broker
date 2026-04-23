const ACCESS_TOKEN_KEY = "stock-broker.access-token";

export type AuthUser = {
  id: number;
  email: string;
  username: string;
  is_active: boolean;
  created_at: string | null;
  last_login_at: string | null;
};

export function getAccessToken(): string | null {
  if (typeof window === "undefined") {
    return null;
  }

  return window.localStorage.getItem(ACCESS_TOKEN_KEY);
}


export function setAccessToken(token: string): void {
  if (typeof window === "undefined") {
    return;
  }

  window.localStorage.setItem(ACCESS_TOKEN_KEY, token);
}


export function clearAccessToken(): void {
  if (typeof window === "undefined") {
    return;
  }

  window.localStorage.removeItem(ACCESS_TOKEN_KEY);
}

