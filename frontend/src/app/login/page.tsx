"use client";

import { useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";

export default function LoginRedirect() {
    const router = useRouter();
    const searchParams = useSearchParams();

    useEffect(() => {
        const redirectTo = searchParams.get("redirectTo") || "/";
        router.replace(`/monitor-login?from=${encodeURIComponent(redirectTo)}`);
    }, [router, searchParams]);

    return (
        <div className="flex items-center justify-center min-h-screen">
            <p className="text-[var(--muted)]">Redirecting to login...</p>
        </div>
    );
}
