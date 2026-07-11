"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/contexts/AuthContext";

export default function HomePage() {
  const { user, profile, loading, profileLoading, signOut } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading) {
      if (!user) {
        router.replace("/login");
      } else if (!profileLoading) {
        if (profile) {
          router.replace("/dashboard");
        } else {
          // Logged in but no profile exists (e.g. database reset/stale session)
          // Sign out and redirect to login so the user defaults to login screen.
          signOut().then(() => {
            router.replace("/login");
          });
        }
      }
    }
  }, [user, profile, loading, profileLoading, router, signOut]);

  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        height: "100vh",
        background: "var(--bg-primary)",
      }}
    >
      <div style={{ textAlign: "center" }}>
        <div
          style={{
            width: 48,
            height: 48,
            margin: "0 auto 16px",
            borderRadius: 12,
            background: "linear-gradient(135deg, #3b82f6, #8b5cf6)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            color: "white",
            fontSize: 24,
            fontWeight: 700,
          }}
        >
          U
        </div>
        <p style={{ color: "var(--text-secondary)", fontSize: 14 }}>Loading...</p>
      </div>
    </div>
  );
}
