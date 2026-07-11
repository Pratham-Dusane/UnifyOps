"use client";

import React, { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/contexts/AuthContext";
import styles from "./register.module.css";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface OrgOption {
  id: string;
  name: string;
}

export default function RegisterPage() {
  const [step, setStep] = useState<"credentials" | "profile">("credentials");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [displayName, setDisplayName] = useState("");
  const [orgMode, setOrgMode] = useState<"create" | "join">("create");
  const [orgName, setOrgName] = useState("");
  const [selectedOrgId, setSelectedOrgId] = useState("");
  const [department, setDepartment] = useState("");
  const [existingOrgs, setExistingOrgs] = useState<OrgOption[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const { user, profile, loading: authLoading, signUp, signInWithGoogle, registerProfile } = useAuth();
  const router = useRouter();

  // If user already has a profile, go to dashboard
  useEffect(() => {
    if (!authLoading && user && profile) {
      router.replace("/dashboard");
    }
  }, [user, profile, authLoading, router]);

  // If user is signed in (Firebase) but has no backend profile, show profile step
  const shouldShowProfile = !authLoading && !!user && !profile;
  const effectiveStep = shouldShowProfile ? "profile" : step;

  // Sync display name and email from Firebase user when transitioning to profile step
  const resolvedDisplayName = effectiveStep === "profile" && user?.displayName && !displayName ? user.displayName : displayName;

  // Fetch existing orgs for the "join" option
  useEffect(() => {
    async function fetchOrgs() {
      try {
        const res = await fetch(`${API_URL}/api/v1/auth/organisations`);
        if (res.ok) {
          const data = await res.json();
          setExistingOrgs(data);
        }
      } catch {
        // Backend may be down
      }
    }
    fetchOrgs();
  }, []);

  const handleEmailSignUp = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");

    if (password !== confirmPassword) {
      setError("Passwords do not match.");
      return;
    }
    if (password.length < 6) {
      setError("Password must be at least 6 characters.");
      return;
    }

    setLoading(true);
    try {
      const newUser = await signUp(email, password);
      setDisplayName(newUser.displayName || displayName);
      setStep("profile");
    } catch (err: unknown) {
      if (err instanceof Error) {
        if (err.message.includes("email-already-in-use")) {
          setError("This email is already registered. Try signing in instead.");
        } else {
          setError(err.message);
        }
      } else {
        setError("Registration failed.");
      }
    } finally {
      setLoading(false);
    }
  };

  const handleGoogleSignUp = async () => {
    setError("");
    setLoading(true);
    try {
      const googleUser = await signInWithGoogle();
      setDisplayName(googleUser.displayName || "");
      setEmail(googleUser.email || "");
      setStep("profile");
    } catch (err: unknown) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError("Google sign-in failed.");
      }
    } finally {
      setLoading(false);
    }
  };

  const handleProfileSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");

    if (!resolvedDisplayName.trim()) {
      setError("Display name is required.");
      return;
    }
    if (orgMode === "create" && !orgName.trim()) {
      setError("Organisation name is required.");
      return;
    }
    if (orgMode === "join" && !selectedOrgId) {
      setError("Please select an organisation to join.");
      return;
    }

    setLoading(true);
    try {
      await registerProfile({
        display_name: resolvedDisplayName.trim(),
        org_name: orgMode === "create" ? orgName.trim() : "",
        org_id: orgMode === "join" ? selectedOrgId : undefined,
        department: department.trim(),
      });
      router.push("/dashboard");
    } catch (err: unknown) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError("Profile registration failed.");
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className={styles.container}>
      <div className={styles.backdrop} />
      <div className={styles.card}>
        <div className={styles.header}>
          <span className={styles.eyebrow}>
            {effectiveStep === "credentials" ? "New Account" : "Almost there"}
          </span>
          <h1 className={styles.title}>
            {effectiveStep === "credentials" ? "Create your account" : "Complete profile"}
          </h1>
          <p className={styles.subtitle}>
            {effectiveStep === "credentials"
              ? "Get started with UnifyOps."
              : "Set up your organisation and profile."}
          </p>
        </div>

        {/* ─── Step 1: Credentials ─── */}
        {effectiveStep === "credentials" && (
          <>
            {error && <div className={styles.error}>{error}</div>}

            {/* Google — primary CTA */}
            <button
              className={styles.googleBtn}
              onClick={handleGoogleSignUp}
              disabled={loading}
            >
              <GoogleIcon />
              Continue with Google
            </button>

            <div className={styles.divider}>
              <span className={styles.dividerText}>or continue with email</span>
            </div>

            <form onSubmit={handleEmailSignUp} className={styles.form}>
              <div className={styles.field}>
                <div className={styles.inputWrap}>
                  <span className={styles.inputIcon}><MailIcon /></span>
                  <input
                    id="register-email"
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    className={styles.input}
                    placeholder="Email address"
                    required
                    autoComplete="email"
                  />
                </div>
              </div>

              <div className={styles.field}>
                <div className={styles.inputWrap}>
                  <span className={styles.inputIcon}><LockIcon /></span>
                  <input
                    id="register-password"
                    type={showPassword ? "text" : "password"}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className={styles.input}
                    placeholder="Password (min. 6 characters)"
                    required
                    autoComplete="new-password"
                  />
                  <button
                    type="button"
                    className={styles.togglePassword}
                    onClick={() => setShowPassword(!showPassword)}
                    tabIndex={-1}
                  >
                    {showPassword ? <EyeOffIcon /> : <EyeIcon />}
                  </button>
                </div>
              </div>

              <div className={styles.field}>
                <div className={styles.inputWrap}>
                  <span className={styles.inputIcon}><LockIcon /></span>
                  <input
                    id="register-confirm"
                    type={showPassword ? "text" : "password"}
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    className={styles.input}
                    placeholder="Confirm password"
                    required
                    autoComplete="new-password"
                  />
                </div>
              </div>

              <button
                type="submit"
                className={styles.submitBtn}
                disabled={loading}
              >
                {loading ? "Creating..." : "Create account"}
                {!loading && <ArrowIcon />}
              </button>
            </form>

            <div className={styles.footer}>
              <p className={styles.footerText}>
                Already have an account?{" "}
                <Link href="/login" className={styles.footerLink}>
                  Sign in
                </Link>
              </p>
            </div>
          </>
        )}

        {/* ─── Step 2: Profile & Organisation ─── */}
        {effectiveStep === "profile" && (
          <form onSubmit={handleProfileSubmit} className={styles.form}>
            {error && <div className={styles.error}>{error}</div>}

            <div className={styles.field}>
              <label htmlFor="display-name" className={styles.label}>
                Full Name
              </label>
              <input
                id="display-name"
                type="text"
                value={resolvedDisplayName}
                onChange={(e) => setDisplayName(e.target.value)}
                className={styles.inputFlat}
                placeholder="Your full name"
                required
              />
            </div>

            <div className={styles.field}>
              <label className={styles.label}>Organisation</label>
              <div className={styles.orgToggle}>
                <button
                  type="button"
                  className={`${styles.orgToggleBtn} ${orgMode === "create" ? styles.orgToggleActive : ""}`}
                  onClick={() => setOrgMode("create")}
                >
                  Create new
                </button>
                <button
                  type="button"
                  className={`${styles.orgToggleBtn} ${orgMode === "join" ? styles.orgToggleActive : ""}`}
                  onClick={() => setOrgMode("join")}
                >
                  Join existing
                </button>
              </div>
            </div>

            {orgMode === "create" ? (
              <div className={styles.field}>
                <label htmlFor="org-name" className={styles.label}>
                  Organisation Name
                </label>
                <input
                  id="org-name"
                  type="text"
                  value={orgName}
                  onChange={(e) => setOrgName(e.target.value)}
                  className={styles.inputFlat}
                  placeholder="e.g. Tata Steel Jamshedpur"
                  required
                />
              </div>
            ) : (
              <div className={styles.field}>
                <label htmlFor="org-select" className={styles.label}>
                  Select Organisation
                </label>
                <select
                  id="org-select"
                  value={selectedOrgId}
                  onChange={(e) => setSelectedOrgId(e.target.value)}
                  className={styles.inputFlat}
                  required
                >
                  <option value="">Select an organisation...</option>
                  {existingOrgs.map((org) => (
                    <option key={org.id} value={org.id}>
                      {org.name}
                    </option>
                  ))}
                </select>
              </div>
            )}

            <div className={styles.field}>
              <label htmlFor="department" className={styles.label}>
                Department
                <span className={styles.optional}> (optional)</span>
              </label>
              <input
                id="department"
                type="text"
                value={department}
                onChange={(e) => setDepartment(e.target.value)}
                className={styles.inputFlat}
                placeholder="e.g. Maintenance, Operations, Quality"
              />
            </div>

            <button
              type="submit"
              className={styles.submitBtn}
              disabled={loading}
            >
              {loading ? "Setting up..." : "Complete registration"}
              {!loading && <ArrowIcon />}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}

/* ─── Inline SVG Icons ─── */

function GoogleIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
      <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z" fill="#4285F4" />
      <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853" />
      <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05" />
      <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335" />
    </svg>
  );
}

function MailIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
      <rect x="2" y="4" width="20" height="16" rx="2" />
      <path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7" />
    </svg>
  );
}

function LockIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
      <path d="M7 11V7a5 5 0 0 1 10 0v4" />
    </svg>
  );
}

function EyeIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
      <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
      <circle cx="12" cy="12" r="3" />
    </svg>
  );
}

function EyeOffIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
      <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24" />
      <line x1="1" y1="1" x2="23" y2="23" />
    </svg>
  );
}

function ArrowIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <line x1="5" y1="12" x2="19" y2="12" />
      <polyline points="12 5 19 12 12 19" />
    </svg>
  );
}
