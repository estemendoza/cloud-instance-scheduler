import {themes as prismThemes} from 'prism-react-renderer';
import type {Config} from '@docusaurus/types';
import type * as Preset from '@docusaurus/preset-classic';

const repoName = process.env.GITHUB_REPOSITORY?.split('/')[1] ?? 'cis';
const organizationName = process.env.GITHUB_REPOSITORY_OWNER ?? 'example';
const siteUrl = process.env.DOCS_URL ?? `https://${organizationName}.github.io`;
const baseUrl = process.env.DOCS_BASE_URL ?? `/${repoName}/`;
const apiDocsUrl = process.env.API_DOCS_URL || '';

const config: Config = {
  title: 'Cloud Instance Scheduler',
  tagline: 'Public documentation for CIS',
  favicon: 'img/favicon.ico',
  url: siteUrl,
  baseUrl,
  organizationName,
  projectName: repoName,
  onBrokenLinks: 'throw',
  onBrokenMarkdownLinks: 'warn',
  i18n: {
    defaultLocale: 'en',
    locales: ['en'],
  },
  customFields: {
    apiDocsUrl,
  },
  presets: [
    [
      'classic',
      {
        docs: {
          routeBasePath: 'docs',
          sidebarPath: './sidebars.ts',
          editUrl: `https://github.com/${organizationName}/${repoName}/tree/main/docs-site/`,
        },
        blog: false,
        theme: {
          customCss: './src/css/custom.css',
        },
      } satisfies Preset.Options,
    ],
  ],
  themeConfig: {
    image: 'img/docusaurus-social-card.jpg',
    navbar: {
      title: 'CIS Docs',
      logo: {
        alt: 'Cloud Instance Scheduler',
        src: 'img/logo.svg',
      },
      items: [
        {
          type: 'docSidebar',
          sidebarId: 'tutorialSidebar',
          position: 'left',
          label: 'Docs',
        },
        {
          href: `https://github.com/${organizationName}/${repoName}`,
          label: 'GitHub',
          position: 'right',
        },
      ],
    },
    footer: {
      style: 'dark',
      links: [
        {
          title: 'Docs',
          items: [
            {
              label: 'Overview',
              to: '/docs/',
            },
            {
              label: 'Getting Started',
              to: '/docs/getting-started',
            },
          ],
        },
        {
          title: 'Project',
          items: [
            {
              label: 'Repository',
              href: `https://github.com/${organizationName}/${repoName}`,
            },
            ...(apiDocsUrl ? [{ label: 'API Docs', href: apiDocsUrl }] : []),
          ],
        },
      ],
      copyright: `Copyright © ${new Date().getFullYear()} Cloud Instance Scheduler. Built with Docusaurus.`,
    },
    prism: {
      theme: prismThemes.github,
      darkTheme: prismThemes.dracula,
    },
  } satisfies Preset.ThemeConfig,
};

export default config;
