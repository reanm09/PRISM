'use client';

import Image from 'next/image';

export function PrismNavigationTransition({ active }: { active: boolean }) {
  return (
    <div aria-hidden={!active} className={`prism-nav-transition ${active ? 'prism-nav-transition--active' : ''}`}>
      <div className="prism-nav-transition__inner">
        <Image src="/prism-mark.svg" alt="" width={72} height={72} priority className="prism-nav-transition__logo" />
        <span className="prism-nav-transition__beam" />
      </div>
    </div>
  );
}
