"use client";

import React, { useState, useEffect, useCallback, useRef } from "react";
import { usePathname } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/contexts/AuthContext";
import { useTheme } from "@/contexts/ThemeContext";
import styles from "./TopBar.module.css";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "https://unifyops-backend-381606738104.asia-south1.run.app";

interface NotificationRecord {
  id: string;
  category: "compliance_gap" | "maintenance_attention" | "safety_warning";
  title: string;
  message: string;
  is_read: boolean;
  created_at: string;
}

const routeNames: Record<string, string> = {
  "/dashboard": "Dashboard",
  "/copilot": "Expert Knowledge Copilot",
  "/documents": "Document Management",
  "/knowledge-graph": "Knowledge Graph Explorer",
  "/maintenance": "Maintenance Intelligence",
  "/compliance": "Regulatory Compliance",
  "/lessons": "Lessons Learned",
  "/interviews": "Knowledge Capture Centre",
  "/admin": "Administration",
  "/settings": "Settings",
};

export default function TopBar() {
  const pathname = usePathname();
  const { user, profile, signOut } = useAuth();
  const { theme, toggleTheme } = useTheme();

  // Notification states
  const [notifications, setNotifications] = useState<NotificationRecord[]>([]);
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  const currentRoute = Object.keys(routeNames).find(
    (key) => pathname === key || (key !== "/dashboard" && pathname.startsWith(key))
  );
  const pageTitle = currentRoute ? routeNames[currentRoute] : "UnifyOps";

  const userInitial = profile?.display_name?.[0]?.toUpperCase() ||
    user?.email?.[0]?.toUpperCase() || "U";

  const getHeaders = useCallback(() => ({
    "Content-Type": "application/json",
    "X-User-UID": user?.uid || "",
    "X-User-Org": profile?.org_id || "",
    "X-User-Role": profile?.role || "viewer",
    "X-User-Plant": profile?.plant_id || "",
    "X-User-Department": profile?.department || "",
  }), [user, profile]);

  const loadNotifications = useCallback(async () => {
    if (!user || !profile) return;
    try {
      const res = await fetch(`${API_URL}/api/v1/notifications`, {
        headers: getHeaders(),
      });
      if (res.ok) {
        const data = await res.json();
        setNotifications(data);
      }
    } catch {
      // Keep empty
    }
  }, [user, profile, getHeaders]);

  useEffect(() => {
    if (user && profile) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      loadNotifications();
    }
  }, [user, profile, loadNotifications]);



  // Poll for notifications every 30 seconds
  useEffect(() => {
    if (!user || !profile) return;
    const interval = setInterval(() => {
      loadNotifications();
    }, 30000);
    return () => clearInterval(interval);
  }, [user, profile, loadNotifications]);

  // Close dropdown on click outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const handleMarkAsRead = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      const res = await fetch(`${API_URL}/api/v1/notifications/${id}/read`, {
        method: "POST",
        headers: getHeaders(),
      });
      if (res.ok) {
        setNotifications((prev) =>
          prev.map((n) => (n.id === id ? { ...n, is_read: true } : n))
        );
      }
    } catch {
      // Ignore error
    }
  };

  const unreadCount = notifications.filter((n) => !n.is_read).length;

  const getCategoryClass = (cat: string) => {
    if (cat === "safety_warning") return styles.catSafety;
    if (cat === "maintenance_attention") return styles.catMaintenance;
    return styles.catCompliance;
  };

  const getCategoryLabel = (cat: string) => {
    if (cat === "safety_warning") return "Safety";
    if (cat === "maintenance_attention") return "Attention";
    return "Compliance";
  };

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

        {/* Notifications Dropdown (Phase 7.2) */}
        <div className={styles.notificationContainer} ref={dropdownRef}>
          <button
            className={styles.iconBtn}
            onClick={() => setIsOpen(!isOpen)}
            aria-label="Notifications"
            title="Notifications"
          >
            <BellIcon />
            {unreadCount > 0 && <span className={styles.badge}>{unreadCount}</span>}
          </button>

          {isOpen && (
            <div className={styles.dropdown}>
              <div className={styles.dropdownHeader}>
                <span>Notifications</span>
                {unreadCount > 0 && (
                  <span style={{ fontSize: "11px", color: "var(--text-secondary)" }}>
                    {unreadCount} unread
                  </span>
                )}
              </div>

              <ul className={styles.dropdownList}>
                {notifications.length === 0 ? (
                  <li className={styles.noNotifs}>No notifications</li>
                ) : (
                  notifications.map((n) => (
                    <li
                      key={n.id}
                      className={`${styles.dropdownItem} ${!n.is_read ? styles.unreadItem : ""}`}
                    >
                      <div className={styles.itemHeader}>
                        <span className={`${styles.itemCategory} ${getCategoryClass(n.category)}`}>
                          {getCategoryLabel(n.category)}
                        </span>
                        {!n.is_read && (
                          <button
                            className={styles.readBtn}
                            onClick={(e) => handleMarkAsRead(n.id, e)}
                          >
                            Mark Read
                          </button>
                        )}
                      </div>
                      <span className={styles.itemTitle}>{n.title}</span>
                      <p className={styles.itemMessage}>{n.message}</p>
                      <div className={styles.itemFooter}>
                        <span className={styles.itemTime}>
                          {new Date(n.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                        </span>
                      </div>
                    </li>
                  ))
                )}
              </ul>

              <div className={styles.dropdownFooter}>
                <Link
                  href="/settings"
                  className={styles.settingsLink}
                  onClick={() => setIsOpen(false)}
                >
                  Configure Notification Settings
                </Link>
              </div>
            </div>
          )}
        </div>

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
