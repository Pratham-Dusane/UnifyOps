// UnifyOps - Firebase Client Configuration
// Replace placeholder values with your actual Firebase config from the Firebase Console.

import { initializeApp, getApps } from "firebase/app";
import { getAuth } from "firebase/auth";

const firebaseConfig = {
  apiKey: process.env.NEXT_PUBLIC_FIREBASE_API_KEY || "AIzaSyA9knDq4V9SkayS24vnk9Weg5Cj4DzDq3o",
  authDomain: process.env.NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN || "unifyops-bd385.firebaseapp.com",
  projectId: process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID || "unifyops-bd385",
  storageBucket: process.env.NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET || "unifyops-bd385.firebasestorage.app",
  messagingSenderId: process.env.NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID || "897751011372",
  appId: process.env.NEXT_PUBLIC_FIREBASE_APP_ID || "1:897751011372:web:f3088f88e5572e87438189",
};

// Initialize Firebase only once
const app = getApps().length === 0 ? initializeApp(firebaseConfig) : getApps()[0];
const auth = getAuth(app);

export { app, auth };
