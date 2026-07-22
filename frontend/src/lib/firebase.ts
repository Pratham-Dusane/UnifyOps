// UnifyOps - Firebase Client Configuration

import { initializeApp, getApps, FirebaseApp } from "firebase/app";
import { getAuth, Auth } from "firebase/auth";

const firebaseConfig = {
  apiKey: process.env.NEXT_PUBLIC_FIREBASE_API_KEY || "",
  authDomain: process.env.NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN || "unifyops-bd385.firebaseapp.com",
  projectId: process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID || "unifyops-bd385",
  storageBucket: process.env.NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET || "unifyops-bd385.firebasestorage.app",
  messagingSenderId: process.env.NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID || "897751011372",
  appId: process.env.NEXT_PUBLIC_FIREBASE_APP_ID || "1:897751011372:web:f3088f88e5572e87438189",
};

let app: FirebaseApp;
let auth: Auth;

try {
  app = getApps().length === 0 ? initializeApp(firebaseConfig) : getApps()[0];
} catch {
  app = getApps().length > 0 ? getApps()[0] : initializeApp({ ...firebaseConfig, apiKey: "dummy-key-for-build" }, "build-app");
}

try {
  auth = getAuth(app);
} catch {
  // Catch invalid API key during static build prerendering to prevent build exit
  auth = {} as Auth;
}

export { app, auth };
