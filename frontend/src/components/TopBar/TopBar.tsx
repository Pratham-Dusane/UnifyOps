"use client";

import React from "react";
import { usePathname } from "next/navigation";
import { useAuth } from "@/contexts/AuthContext";
import { useTheme } from "@/contexts/ThemeContext";
import styles from "./TopBar.module.css";

const routeNames: Record<string, string> = {
  "/dashboard": "Dashboard",
  "/copilot": "Expert Knowledge Copilot",
  "/documents": "Document Management",
  "/knowledge-graph": "Knowledge Graph Explorer",
  "/maintenance": "Maintenance Intelligence",
  "/compliance": "Regulatory Compliance",
  "/lessons": "Lessons Learned",
  "/admin": "Administration",
  "/settings": "Settings",
};

export default function TopBar() {
  const pathname = usePathname();
  const { user, profile, signOut } = useAuth();
  const { theme, toggleTheme } = useTheme();

  const currentRoute = Object.keys(routeNames).find(
    (key) => pathname === key || (key !== "/dashboard" && pathname.startsWith(key))
  );
  const pageTitle = currentRoute ? routeNames[currentRoute] : "UnifyOps";

  const userInitial = profile?.display_name?.[0]?.toUpperCase() ||
    user?.email?.[0]?.toUpperCase() || "U";

  return (
    <header className={styles.topbar}>
      <div className={styles.left}>
        <h1 className={styles.pageTitle}>{pageTitle}</h1>
        {profile?.org_name && (
          <span className={styles.orgBadge}>{profile.org_name}</span>
        )}
      </div>

      <div className={styles.right}>
        {/* Theme toggle */}
        <button
          className={styles.iconBtn}
          onClick={toggleTheme}
          aria-label={`Switch to ${theme === "light" ? "dark" : "light"} mode`}
          title={`Switch to ${theme === "light" ? "dark" : "light"} mode`}
        >
          {theme === "light" ? <MoonIcon /> : <SunIcon />}
        </button>

        {/* Notification bell placeholder */}
        <button className={styles.iconBtn} aria-label="Notifications" title="Notifications">
          <BellIcon />
        </button>

        {/* User menu */}
        <div className={styles.userSection}>
          <div className={styles.avatar}>{userInitial}</div>
          <div className={styles.userInfo}>
            <span className={styles.userName}>
              {profile?.display_name || user?.email || "Not signed in"}
            </span>
            <span className={styles.userRole}>
              {profile?.role?.replace(/_/g, " ") || ""}
            </span>
          </div>
          <button
            className={styles.signOutBtn}
            onClick={signOut}
            title="Sign out"
          >
            Sign out
          </button>
        </div>
      </div>
    </header>
  );
}

function MoonIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
    </svg>
  );
}

function SunIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="5" />
      <line x1="12" y1="1" x2="12" y2="3" />
      <line x1="12" y1="21" x2="12" y2="23" />
      <line x1="4.22" y1="4.22" x2="5.64" y2="5.64" />
      <line x1="18.36" y1="18.36" x2="19.78" y2="19.78" />
      <line x1="1" y1="12" x2="3" y2="12" />
      <line x1="21" y1="12" x2="23" y2="12" />
      <line x1="4.22" y1="19.78" x2="5.64" y2="18.36" />
      <line x1="18.36" y1="5.64" x2="19.78" y2="4.22" />
    </svg>
  );
}

function BellIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
      <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
      <path d="M13.73 21a2 2 0 0 1-3.46 0" />
    </svg>
  );
}
