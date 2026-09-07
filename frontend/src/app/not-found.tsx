import Link from "next/link";
import { Compass } from "lucide-react";

import { Button } from "@/components/ui";
import { Logo } from "@/components/layout/logo";

export default function NotFound() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-5 bg-background px-6 text-center">
      <Logo size={36} />
      <div className="flex size-12 items-center justify-center rounded-full bg-surface-muted">
        <Compass className="size-5 text-ink-subtle" aria-hidden />
      </div>
      <div>
        <h1 className="text-xl font-semibold tracking-tight text-ink">Page not found</h1>
        <p className="mt-1.5 max-w-md text-sm leading-6 text-ink-muted">
          That route does not exist in Nexgile WealthAgent. It may have moved, or the link may be out of date.
        </p>
      </div>
      <Link href="/">
        <Button variant="primary">Back to my workspace</Button>
      </Link>
    </main>
  );
}
