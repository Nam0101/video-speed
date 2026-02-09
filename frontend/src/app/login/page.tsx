"use client";

import { Suspense, useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";

function LoginRedirectInner() {
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

export default function LoginRedirect() {
    return (
        <Suspense fallback={<div className="flex items-center justify-center min-h-screen"><p>Loading...</p></div>}>
            <LoginRedirectInner />
        </Suspense>
    );
}
