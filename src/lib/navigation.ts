export type NavItem = {
  label: string;
  href: string;
  section: 'sentinel' | 'investigation' | 'intelligence';
  icon: string;
};

export const navigation: NavItem[] = [
  { label: 'Overview', href: '/', section: 'sentinel', icon: 'layout-dashboard' },
  { label: 'Intercept', href: '/intercept', section: 'sentinel', icon: 'shield-alert' },
  { label: 'Artifacts', href: '/artifacts', section: 'sentinel', icon: 'file-search' },
  { label: 'Fractures', href: '/fractures', section: 'sentinel', icon: 'triangle-alert' },
  { label: 'Interpretation Graph', href: '/graph', section: 'investigation', icon: 'share-2' },
  { label: 'PRISM Lab', href: '/lab', section: 'investigation', icon: 'flask-conical' },
  { label: 'Experiments', href: '/experiments', section: 'investigation', icon: 'beaker' },
  { label: 'Artifact Passports', href: '/passports', section: 'intelligence', icon: 'file-badge' },
  { label: 'Capability Graph', href: '/capabilities', section: 'intelligence', icon: 'network' },
  { label: 'Immune Memory', href: '/immune-memory', section: 'intelligence', icon: 'database-zap' },
];
