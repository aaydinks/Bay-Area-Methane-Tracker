import { lazy, Suspense, useEffect, useRef, useState } from 'react';
import type { SiteSummary } from './MethaneMap';

// The map library is large. This small island shows a placeholder and loads the map only when
// the placeholder comes near the viewport, or when the reader asks for it.
const MethaneMap = lazy(() => import('./MethaneMap'));

interface Props {
  sites: SiteSummary[];
  isPublic: boolean;
  dataThrough: string | null;
  availableSources: string[];
}

export default function MapLoader(props: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const [wanted, setWanted] = useState(false);

  useEffect(() => {
    if (wanted || !ref.current || !('IntersectionObserver' in window)) return;
    const io = new IntersectionObserver(
      (entries) => {
        if (entries.some((e) => e.isIntersecting)) {
          setWanted(true);
          io.disconnect();
        }
      },
      { rootMargin: '200px 0px' },
    );
    io.observe(ref.current);
    return () => io.disconnect();
  }, [wanted]);

  if (!wanted) {
    return (
      <div ref={ref} className="map-placeholder" role="status">
        <p>The interactive map loads when you scroll to it.</p>
        <button type="button" className="theme-toggle" onClick={() => setWanted(true)}>Load the map now</button>
      </div>
    );
  }
  return (
    <Suspense fallback={<div className="map-placeholder" role="status"><p>Loading the map…</p></div>}>
      <MethaneMap {...props} />
    </Suspense>
  );
}
