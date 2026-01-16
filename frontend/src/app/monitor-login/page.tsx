import { Suspense } from "react";
import MonitorLoginClient from "./monitor-login-client";

export default function MonitorLoginPage() {
  return (
    <Suspense
      fallback={<div className="min-h-screen bg-background text-foreground" />}
    >
      <MonitorLoginClient />
    </Suspense>
  );
}
