"use client";

import { useEffect } from "react";
import { AlertTriangle, RefreshCw } from "lucide-react";

import { Button } from "@/components/ui";

export default function GlobalError({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  useEffect(() => {
    console.error("Unhandled application error", error);
  }, [error]);

  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-5 bg-background px-6 text-center">
      <div className="flex size-12 items-center justify-center rounded-full bg-negative-soft">
        <AlertTriangle className="size-5 text-negative" aria-hidden />
      </div>
      <div>
        <h1 className="text-xl font-semibold tracking-tight text-ink">Something went wrong</h1>
        <p className="mt-1.5 max-w-md text-sm leading-6 text-ink-muted">
          This view could not be rendered. Your data has not been changed.
        </p>
      </div>
      <Button variant="primary" onClick={reset}>
        <RefreshCw />
        Try again
      </Button>
    </main>
  );
}
