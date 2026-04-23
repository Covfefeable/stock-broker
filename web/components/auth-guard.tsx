"use client";

import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { Spin } from "antd";
import { clearAccessToken, getAccessToken, type AuthUser } from "@/lib/auth";
import { apiGet } from "@/lib/api";

type AuthGuardProps = {
  children: (user: AuthUser) => React.ReactNode;
};

export function AuthGuard({ children }: AuthGuardProps) {
  const router = useRouter();
  const pathname = usePathname();
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = getAccessToken();
    if (!token) {
      router.replace(`/login?next=${encodeURIComponent(pathname)}`);
      return;
    }

    let cancelled = false;

    apiGet<{ user: AuthUser }>("/auth/me", token)
      .then((payload) => {
        if (!cancelled) {
          setUser(payload.user);
        }
      })
      .catch(() => {
        clearAccessToken();
        if (!cancelled) {
          router.replace(`/login?next=${encodeURIComponent(pathname)}`);
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [pathname, router]);

  if (loading || !user) {
    return (
      <div className="auth-guard-loading">
        <Spin size="large" />
      </div>
    );
  }

  return <>{children(user)}</>;
}

