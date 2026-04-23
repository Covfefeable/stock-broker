"use client";

import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { AppLoader } from "@/components/app-loader";
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
        <AppLoader message="正在校验登录状态" />
      </div>
    );
  }

  return <>{children(user)}</>;
}
