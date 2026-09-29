'use client';

import {
  AlertTriangle,
  Beaker,
  DatabaseZap,
  FileBadge2,
  FileSearch,
  FlaskConical,
  LayoutDashboard,
  Network,
  Settings2,
  Share2,
  ShieldAlert,
} from 'lucide-react';

const iconMap = {
  'layout-dashboard': LayoutDashboard,
  'shield-alert': ShieldAlert,
  'file-search': FileSearch,
  'triangle-alert': AlertTriangle,
  'share-2': Share2,
  'flask-conical': FlaskConical,
  beaker: Beaker,
  'file-badge': FileBadge2,
  network: Network,
  'database-zap': DatabaseZap,
  'settings-2': Settings2,
} as const;

export function NavIcon({ name }: { name: keyof typeof iconMap }) {
  const Icon = iconMap[name];
  return <Icon size={17} strokeWidth={1.7} />;
}
