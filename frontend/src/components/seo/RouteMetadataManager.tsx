import React, { useEffect } from 'react';
import type { RouteMetadata } from '../../routes';

interface RouteMetadataManagerProps {
  route: RouteMetadata;
  currentPath: string;
}

function upsertMeta(selector: string, attrName: 'name' | 'property', attrValue: string, content: string): void {
  let el = document.head.querySelector<HTMLMetaElement>(selector);
  if (!el) {
    el = document.createElement('meta');
    el.setAttribute(attrName, attrValue);
    document.head.appendChild(el);
  }
  el.setAttribute('content', content);
}

export const RouteMetadataManager: React.FC<RouteMetadataManagerProps> = ({ route, currentPath }) => {
  useEffect(() => {
    const origin = window.location.origin;
    const canonicalPath = route.id === 'not_found' ? currentPath : route.path;
    const canonicalUrl = `${origin}${canonicalPath === '/' ? '/' : canonicalPath}`;

    // Unique page title (never Vite or React)
    document.title = route.documentTitle;

    // Meta description & robots
    upsertMeta('meta[name="description"]', 'name', 'description', route.metaDescription);
    upsertMeta(
      'meta[name="robots"]',
      'name',
      'robots',
      route.id === 'not_found' ? 'noindex, nofollow' : 'index, follow'
    );

    // Canonical link tag
    let canonicalEl = document.head.querySelector<HTMLLinkElement>('link[rel="canonical"]');
    if (!canonicalEl) {
      canonicalEl = document.createElement('link');
      canonicalEl.setAttribute('rel', 'canonical');
      document.head.appendChild(canonicalEl);
    }
    canonicalEl.setAttribute('href', canonicalUrl);

    // Open Graph & Twitter dynamic tags
    upsertMeta('meta[property="og:title"]', 'property', 'og:title', route.documentTitle);
    upsertMeta('meta[property="og:description"]', 'property', 'og:description', route.metaDescription);
    upsertMeta('meta[property="og:url"]', 'property', 'og:url', canonicalUrl);
    upsertMeta('meta[name="twitter:title"]', 'name', 'twitter:title', route.documentTitle);
    upsertMeta('meta[name="twitter:description"]', 'name', 'twitter:description', route.metaDescription);

    // Dynamic BreadcrumbList JSON-LD
    const breadcrumbItems = [
      {
        '@type': 'ListItem',
        position: 1,
        name: 'AgentGuard Console',
        item: `${origin}/`,
      },
    ];

    if (route.path !== '/') {
      breadcrumbItems.push({
        '@type': 'ListItem',
        position: 2,
        name: route.label,
        item: canonicalUrl,
      });
    }

    const breadcrumbSchema = {
      '@context': 'https://schema.org',
      '@type': 'BreadcrumbList',
      itemListElement: breadcrumbItems,
    };

    let ldScript = document.head.querySelector<HTMLScriptElement>('#agentguard-breadcrumb-schema');
    if (!ldScript) {
      ldScript = document.createElement('script');
      ldScript.id = 'agentguard-breadcrumb-schema';
      ldScript.type = 'application/ld+json';
      document.head.appendChild(ldScript);
    }
    ldScript.textContent = JSON.stringify(breadcrumbSchema);
  }, [route, currentPath]);

  return null;
};
