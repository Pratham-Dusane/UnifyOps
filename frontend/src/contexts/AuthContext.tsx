"use client";

import React, { createContext, useContext, useEffect, useState } from "react";
import {
  User,
  onAuthStateChanged,
  signInWithEmailAndPassword,
  createUserWithEmailAndPassword,
  signInWithPopup,
  GoogleAuthProvider,
  signOut as firebaseSignOut,
} from "firebase/auth";
import { auth } from "@/lib/firebase";

export interface UserProfile {
  uid: string;
  email: string;
  display_name: string;
  org_id: string;
  org_name: string;
  role: string;
  department: string;
  plant_id: string;
}

interface AuthContextType {
  user: User | null;
  profile: UserProfile | null;
  loading: boolean;
  profileLoading: boolean;
  signIn: (email: string, password: string) => Promise<void>;
  signUp: (email: string, password: string) => Promise<User>;
  signInWithGoogle: () => Promise<User>;
  signOut: () => Promise<void>;
  registerProfile: (data: {
    display_name: string;
    org_name: string;
    org_id?: string;
    department?: string;
  }) => Promise<UserProfile>;
  refreshProfile: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);
const API_URL = process.env.NEXT_PUBLIC_API_URL || "https://unifyops-backend-381606738104.asia-south1.run.app";
const PROFILE_CACHE_KEY = "unifyops_profile";

/**
 * Read cached profile from localStorage.
 * Returns null if nothing cached or if it belongs to a different UID.
 */
function getCachedProfile(uid: string): UserProfile | null {
  try {
    const raw = localStorage.getItem(PROFILE_CACHE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as UserProfile;
    return parsed.uid === uid ? parsed : null;
  } catch {
    return null;
  }
}

function setCachedProfile(profile: UserProfile | null) {
  try {
    if (profile) {
      localStorage.setItem(PROFILE_CACHE_KEY, JSON.stringify(profile));
    } else {
      localStorage.removeItem(PROFILE_CACHE_KEY);
    }
  } catch {
    // localStorage may be unavailable in SSR
  }
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [profileLoading, setProfileLoading] = useState(false);

  // Fetch backend profile for a Firebase user
  const fetchProfile = async (firebaseUser: User): Promise<UserProfile | null> => {
    try {
      const res = await fetch(`${API_URL}/api/v1/auth/profile`, {
        headers: {
          "X-User-UID": firebaseUser.uid,
          "X-User-Email": firebaseUser.email || "",
        },
      });
      if (res.ok) {
        const data = await res.json();
        if (data && data.uid) {
          return data as UserProfile;
        }
      }
      return null;
    } catch {
      return null;
    }
  };

  useEffect(() => {
    const unsubscribe = onAuthStateChanged(auth, async (firebaseUser) => {
      setUser(firebaseUser);

      if (firebaseUser) {
        // Immediately restore cached profile so there's no flash
        const cached = getCachedProfile(firebaseUser.uid);
        if (cached) {
          setProfile(cached);
        }

        // Then fetch fresh profile from backend
        setProfileLoading(true);
        const fresh = await fetchProfile(firebaseUser);
        if (fresh) {
          setProfile(fresh);
          setCachedProfile(fresh);
        } else {
          // No profile on backend (e.g., server restarted) - invalidate cache
          setProfile(null);
          setCachedProfile(null);
        }
        setProfileLoading(false);
      } else {
        setProfile(null);
        setCachedProfile(null);
      }

      setLoading(false);
    });
    return () => unsubscribe();
  }, []);

  const signIn = async (email: string, password: string) => {
    await signInWithEmailAndPassword(auth, email, password);
  };

  const signUp = async (email: string, password: string): Promise<User> => {
    const cred = await createUserWithEmailAndPassword(auth, email, password);
    return cred.user;
  };

  const signInWithGoogle = async (): Promise<User> => {
    const provider = new GoogleAuthProvider();
    const cred = await signInWithPopup(auth, provider);
    return cred.user;
  };

  const signOut = async () => {
    await firebaseSignOut(auth);
    setProfile(null);
    setCachedProfile(null);
  };

  const registerProfile = async (data: {
    display_name: string;
    org_name: string;
    org_id?: string;
    department?: string;
  }): Promise<UserProfile> => {
    if (!user) throw new Error("Not authenticated");

    const res = await fetch(`${API_URL}/api/v1/auth/register`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-User-UID": user.uid,
        "X-User-Email": user.email || "",
      },
      body: JSON.stringify({
        display_name: data.display_name,
        org_name: data.org_name,
        org_id: data.org_id || null,
        department: data.department || "",
      }),
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Registration failed");
    }

    const p = (await res.json()) as UserProfile;
    setProfile(p);
    setCachedProfile(p);
    return p;
  };

  const refreshProfile = async () => {
    if (user) {
      const p = await fetchProfile(user);
      setProfile(p);
      if (p) setCachedProfile(p);
    }
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        profile,
        loading,
        profileLoading,
        signIn,
        signUp,
        signInWithGoogle,
        signOut,
        registerProfile,
        refreshProfile,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
