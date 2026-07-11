"use client";

import React from "react";
import { useTheme } from "@/contexts/ThemeContext";
import { useAuth } from "@/contexts/AuthContext";
import styles from "./settings.module.css";

export default function SettingsPage() {
  const { theme, toggleTheme } = useTheme();
  const { user } = useAuth();

  return (
    <div className={styles.page}>
      <div className={styles.card}>
        <h2 className={styles.title}>Settings</h2>

        <div className={styles.section}>
          <h3 className={styles.sectionTitle}>Appearance</h3>
          <div className={styles.settingRow}>
            <div>
              <span className={styles.settingLabel}>Theme</span>
              <span className={styles.settingDesc}>
                Choose between light and dark mode
              </span>
            </div>
            <button className={styles.toggleBtn} onClick={toggleTheme}>
              <span
                className={`${styles.toggleTrack} ${
                  theme === "dark" ? styles.toggleActive : ""
                }`}
              >
                <span className={styles.toggleThumb} />
              </span>
              <span className={styles.toggleLabel}>
                {theme === "light" ? "Light" : "Dark"}
              </span>
            </button>
          </div>
        </div>

        <div className={styles.section}>
          <h3 className={styles.sectionTitle}>Account</h3>
          <div className={styles.settingRow}>
            <div>
              <span className={styles.settingLabel}>Email</span>
              <span className={styles.settingDesc}>
                {user?.email || "Not available"}
              </span>
            </div>
          </div>
          <div className={styles.settingRow}>
            <div>
              <span className={styles.settingLabel}>User ID</span>
              <span className={styles.settingDesc}>
                {user?.uid || "Not available"}
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
