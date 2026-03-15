import React from 'react';
import Link from '@docusaurus/Link';
import useDocusaurusContext from '@docusaurus/useDocusaurusContext';
import Layout from '@theme/Layout';

import styles from './index.module.css';

const FEATURES = [
  {
    title: 'Multi-Cloud',
    description: 'Manage AWS, Azure, and GCP instances from a single dashboard. Connect accounts and auto-discover compute resources.',
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <path d="M18 10h-1.26A8 8 0 1 0 9 20h9a5 5 0 0 0 0-10z" />
      </svg>
    ),
  },
  {
    title: 'Flexible Schedules',
    description: 'Define schedules with a visual weekly grid or cron expressions. Full timezone support for global teams.',
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="12" cy="12" r="10" />
        <polyline points="12 6 12 12 16 14" />
      </svg>
    ),
  },
  {
    title: 'Auto Start/Stop',
    description: 'The reconciliation engine continuously compares desired vs actual state and starts or stops instances automatically.',
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
      </svg>
    ),
  },
  {
    title: 'Cost Savings',
    description: 'Track savings estimates per resource and explore what-if scenarios with the built-in cost calculator.',
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <line x1="12" y1="1" x2="12" y2="23" />
        <path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6" />
      </svg>
    ),
  },
  {
    title: 'Overrides',
    description: 'Need an instance outside its schedule? Apply temporary per-resource overrides with automatic expiration.',
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
      </svg>
    ),
  },
  {
    title: 'Audit Trail',
    description: 'Full execution history and state transition log. Know exactly what happened, when, and why.',
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
        <polyline points="14 2 14 8 20 8" />
        <line x1="16" y1="13" x2="8" y2="13" />
        <line x1="16" y1="17" x2="8" y2="17" />
        <polyline points="10 9 9 9 8 9" />
      </svg>
    ),
  },
];

export default function Home(): JSX.Element {
  const {siteConfig} = useDocusaurusContext();
  const apiDocsUrl = (siteConfig.customFields?.apiDocsUrl as string) ??
    'http://localhost:8000/api/v1/docs';

  return (
    <Layout
      title="Cloud Instance Scheduler"
      description="Public documentation for Cloud Instance Scheduler">
      <main className={styles.hero}>
        <div className="container">
          <p className={styles.kicker}>Documentation</p>
          <h1 className={styles.title}>Cloud Instance Scheduler</h1>
          <p className={styles.subtitle}>
            Most cloud instances don't need to run 24/7. Development, staging,
            and test environments sit idle nights, weekends, and holidays — but
            you keep paying for them. CIS lets you define schedules for your
            AWS, Azure, and GCP instances, handles start/stop automation, and
            gives you a clear view of your savings.
          </p>
          <div className={styles.actions}>
            <Link className="button button--primary button--lg" to="/docs/">
              Read the docs
            </Link>
            <Link className="button button--secondary button--lg" href={apiDocsUrl}>
              API reference
            </Link>
          </div>
        </div>
      </main>

      <section className={styles.features}>
        <div className="container">
          <div className={styles.grid}>
            {FEATURES.map(({title, description, icon}) => (
              <div key={title} className={styles.card}>
                <div className={styles.cardIcon}>{icon}</div>
                <h3 className={styles.cardTitle}>{title}</h3>
                <p className={styles.cardDescription}>{description}</p>
              </div>
            ))}
          </div>
        </div>
      </section>
    </Layout>
  );
}
