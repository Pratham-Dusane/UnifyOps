"use client";

import React, { useState, useEffect, useCallback } from "react";
import { useTheme } from "@/contexts/ThemeContext";
import { useAuth } from "@/contexts/AuthContext";
import styles from "./settings.module.css";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "https://unifyops-backend-381606738104.asia-south1.run.app";

interface PreferenceItem {
  category: "compliance_gap" | "maintenance_attention" | "safety_warning";
  in_app: boolean;
  email: boolean;
  sms: boolean;
  frequency: "real_time" | "daily_digest" | "weekly_digest" | "disabled";
}

interface NotificationPreference {
  user_uid: string;
  org_id: string;
  preferences: PreferenceItem[];
}

export default function SettingsPage() {
  const { theme, toggleTheme } = useTheme();
  const { user, profile } = useAuth();

  // Localisation and notification states
  const [preferredLang, setPreferredLang] = useState(() => {
    if (typeof window !== "undefined") {
      return localStorage.getItem("preferred_lang") || "en";
    }
    return "en";
  });
  const [preferenceData, setPreferenceData] = useState<NotificationPreference | null>(null);
  const [saveStatus, setSaveStatus] = useState<"idle" | "saving" | "success" | "error">("idle");
  const [errorMessage, setErrorMessage] = useState("");

  const getHeaders = useCallback(
    () => ({
      "Content-Type": "application/json",
      "X-User-UID": user?.uid || "",
      "X-User-Org": profile?.org_id || "",
      "X-User-Role": profile?.role || "viewer",
      "X-User-Plant": profile?.plant_id || "",
      "X-User-Department": profile?.department || "",
    }),
    [user, profile]
  );

  // Load preferences
  useEffect(() => {
    let isMounted = true;
    if (user && profile) {
      fetch(`${API_URL}/api/v1/notifications/preferences`, {
        headers: getHeaders(),
      })
        .then((res) => {
          if (res.ok) return res.json();
          throw new Error("Failed to load preferences");
        })
        .then((data) => {
          if (isMounted) setPreferenceData(data);
        })
        .catch(() => {
          // Keep defaults
        });
    }
    return () => {
      isMounted = false;
    };
  }, [user, profile, getHeaders]);


  const handleLanguageChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const lang = e.target.value;
    setPreferredLang(lang);
    localStorage.setItem("preferred_lang", lang);
  };

  const handlePreferenceCheckboxChange = (
    category: string,
    channel: "in_app" | "email" | "sms"
  ) => {
    if (!preferenceData) return;

    const updatedPrefs = preferenceData.preferences.map((p) => {
      if (p.category === category) {
        return { ...p, [channel]: !p[channel] };
      }
      return p;
    });

    setPreferenceData({ ...preferenceData, preferences: updatedPrefs });
  };

  const handleFrequencyChange = (category: string, value: string) => {
    if (!preferenceData) return;

    const updatedPrefs = preferenceData.preferences.map((p) => {
      if (p.category === category) {
        return { ...p, frequency: value as PreferenceItem["frequency"] };
      }
      return p;
    });

    setPreferenceData({ ...preferenceData, preferences: updatedPrefs });
  };

  const handleSavePreferences = async () => {
    if (!preferenceData) return;
    setSaveStatus("saving");
    setErrorMessage("");

    // Enforce safety warning validation locally as well
    const safetyPref = preferenceData.preferences.find(
      (p) => p.category === "safety_warning"
    );
    if (safetyPref) {
      const allDisabled = !(safetyPref.in_app || safetyPref.email || safetyPref.sms);
      const freqDisabled = safetyPref.frequency === "disabled";

      if (allDisabled || freqDisabled) {
        setSaveStatus("error");
        setErrorMessage(
          "Safety warnings cannot be fully disabled (Guiding Principle 2). Please enable at least one delivery channel (In-App, Email, or SMS) and set a valid alert frequency."
        );
        return;
      }
    }

    try {
      const res = await fetch(`${API_URL}/api/v1/notifications/preferences`, {
        method: "PUT",
        headers: getHeaders(),
        body: JSON.stringify(preferenceData),
      });

      if (res.ok) {
        setSaveStatus("success");
        setTimeout(() => setSaveStatus("idle"), 3000);
      } else {
        const errorData = await res.json();
        setSaveStatus("error");
        setErrorMessage(errorData.detail || "Failed to save preferences.");
      }
    } catch {
      setSaveStatus("error");
      setErrorMessage("Network error occurred while saving.");
    }
  };

  const categoryLabels: Record<string, string> = {
    compliance_gap: "Compliance Gaps",
    maintenance_attention: "Maintenance Attention Alerts",
    safety_warning: "Safety & Lesson Warnings",
  };

  return (
    <div className={styles.page}>
      <div className={styles.card}>
        <h2 className={styles.title}>Settings</h2>

        {/* Localisation & Language Settings */}
        <div className={styles.section}>
          <h3 className={styles.sectionTitle}>Regional Language Support</h3>
          <div className={styles.settingRow}>
            <div>
              <span className={styles.settingLabel}>Preferred Language</span>
              <span className={styles.settingDesc}>
                Select the language used for Copilot queries and system alerts
              </span>
            </div>
            <select
              className={styles.selectInput}
              value={preferredLang}
              onChange={handleLanguageChange}
            >
              <option value="en">English (Default)</option>
              <option value="hi">Hindi (हिन्दी)</option>
              <option value="mr">Marathi (मराठी)</option>
              <option value="ta">Tamil (தமிழ்)</option>
              <option value="kn">Kannada (ಕನ್ನಡ)</option>
            </select>
          </div>
        </div>

        {/* Notification Preferences Settings */}
        {preferenceData && (
          <div className={styles.section}>
            <h3 className={styles.sectionTitle}>Notification Preference Centre</h3>
            <p className={styles.sectionDesc} style={{ fontSize: "12px", color: "var(--text-secondary)", marginBottom: "16px" }}>
              Configure delivery channels and alert frequencies for different operational events.
            </p>

            <table className={styles.prefTable}>
              <thead>
                <tr>
                  <th className={styles.prefTh}>Alert Category</th>
                  <th className={styles.prefTh}>In-App</th>
                  <th className={styles.prefTh}>Email</th>
                  <th className={styles.prefTh}>SMS</th>
                  <th className={styles.prefTh}>Frequency</th>
                </tr>
              </thead>
              <tbody>
                {preferenceData.preferences.map((p) => (
                  <tr key={p.category} className={styles.prefTr}>
                    <td className={styles.prefTd}>
                      <div style={{ fontWeight: 500, fontSize: "14px" }}>
                        {categoryLabels[p.category] || p.category}
                      </div>
                      {p.category === "safety_warning" && (
                        <div style={{ fontSize: "11px", color: "var(--accent-primary)", fontWeight: 500 }}>
                          Safety-critical (Enforced alerts)
                        </div>
                      )}
                    </td>
                    <td className={styles.prefTd}>
                      <input
                        type="checkbox"
                        checked={p.in_app}
                        onChange={() => handlePreferenceCheckboxChange(p.category, "in_app")}
                      />
                    </td>
                    <td className={styles.prefTd}>
                      <input
                        type="checkbox"
                        checked={p.email}
                        onChange={() => handlePreferenceCheckboxChange(p.category, "email")}
                      />
                    </td>
                    <td className={styles.prefTd}>
                      <input
                        type="checkbox"
                        checked={p.sms}
                        onChange={() => handlePreferenceCheckboxChange(p.category, "sms")}
                      />
                    </td>
                    <td className={styles.prefTd}>
                      <select
                        className={styles.frequencySelect}
                        value={p.frequency}
                        onChange={(e) => handleFrequencyChange(p.category, e.target.value)}
                      >
                        <option value="real_time">Real-Time</option>
                        <option value="daily_digest">Daily Digest</option>
                        <option value="weekly_digest">Weekly Digest</option>
                        <option value="disabled" disabled={p.category === "safety_warning"}>
                          Disabled
                        </option>
                      </select>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>

            {saveStatus === "error" && (
              <div className={styles.alertError} role="alert">
                {errorMessage}
              </div>
            )}

            {saveStatus === "success" && (
              <div className={styles.alertSuccess}>
                Preferences saved successfully!
              </div>
            )}

            <div style={{ display: "flex", justifyContent: "flex-end", marginTop: "16px" }}>
              <button
                className={styles.saveBtn}
                onClick={handleSavePreferences}
                disabled={saveStatus === "saving"}
              >
                {saveStatus === "saving" ? "Saving..." : "Save Preferences"}
              </button>
            </div>
          </div>
        )}

        {/* Existing Appearance Section */}
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

        {/* Existing Account Section */}
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
