"use client";

import React, { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/contexts/AuthContext";
import Sidebar from "@/components/Sidebar/Sidebar";
import TopBar from "@/components/TopBar/TopBar";
import styles from "./layout.module.css";

export default function AuthenticatedLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const { user, profile, loading, profileLoading, signOut } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && !user) {
      router.replace("/login");
    }
    // Signed in but no profile → stale session or database reset
    if (!loading && user && !profileLoading && !profile) {
      signOut().then(() => {
        router.replace("/login");
      });
    }
  }, [user, profile, loading, profileLoading, router, signOut]);

  if (loading || profileLoading) {
    return (
      <div className={styles.loading}>
        <div className={styles.spinner} />
        <p>Loading...</p>
      </div>
    );
  }

  if (!user || !profile) {
    return null;
  }

  return (
    <div className={styles.shell}>
      <Sidebar />
      <TopBar />
      <main className={styles.main}>{children}</main>
    </div>
  );
}
