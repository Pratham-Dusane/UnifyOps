import React from "react";
import styles from "./PlaceholderPage.module.css";

interface PlaceholderPageProps {
  title: string;
  description: string;
  phase: string;
  features: string[];
}

export default function PlaceholderPage({
  title,
  description,
  phase,
  features,
}: PlaceholderPageProps) {
  return (
    <div className={styles.page}>
      <div className={styles.card}>
        <div className={styles.badge}>{phase}</div>
        <h2 className={styles.title}>{title}</h2>
        <p className={styles.description}>{description}</p>

        <div className={styles.featureList}>
          <h3 className={styles.featureTitle}>Planned Capabilities</h3>
          <ul className={styles.features}>
            {features.map((feature) => (
              <li key={feature} className={styles.featureItem}>
                <span className={styles.checkmark}>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <circle cx="12" cy="12" r="10" />
                    <line x1="12" y1="8" x2="12" y2="16" />
                    <line x1="8" y1="12" x2="16" y2="12" />
                  </svg>
                </span>
                {feature}
              </li>
            ))}
          </ul>
        </div>

        <div className={styles.statusBar}>
          <span className={styles.statusDot} />
          <span className={styles.statusText}>Awaiting implementation</span>
        </div>
      </div>
    </div>
  );
}
