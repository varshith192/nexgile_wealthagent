"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { Loader2 } from "lucide-react";

import { useAuth } from "@/lib/auth";
import { Logo } from "@/components/layout/logo";

/** Entry point: route each visitor to their own workspace, or to sign-in. */
export default function RootPage() {
  const router = useRouter();
  const { status, user } = useAuth();

  useEffect(() => {
    if (status === "authenticated" && user) router.replace(user.home_route);
    if (status === "anonymous") router.replace("/login");
  }, [status, user, router]);

  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-4 bg-background">
      <Logo size={40} />
      <div className="flex items-center gap-2 text-sm text-ink-muted">
        <Loader2 className="size-4 animate-spin" aria-hidden />
        Loading your workspace…
      </div>
    </main>
  );
}
