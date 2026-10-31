import useEmblaCarousel from 'embla-carousel-react';
import { useCallback, useEffect, useState } from 'react';

export interface Slide {
  title: string;
  text: string;
  href?: string;
  linkText?: string;
  /** A result colour (red, orange, yellow, green, grey) and its label, when the slide has one. */
  colour?: string | null;
  badge?: string | null;
  step?: number;
}

interface Props {
  label: string;
  slides: Slide[];
  /** "steps" numbers each slide; "cards" renders titles as links. */
  kind?: 'steps' | 'cards';
}

const ICONS: Record<string, string> = {
  red: 'M8 2 15 14H1z',
  orange: 'M8 1l7 7-7 7-7-7z',
  yellow: 'M8 2a6 6 0 1 1 0 12A6 6 0 0 1 8 2z',
  green: 'M1 3h14L8 14z',
  grey: 'M8 2.5a5.5 5.5 0 1 1 0 11 5.5 5.5 0 0 1 0-11zm0 2a3.5 3.5 0 1 0 0 7 3.5 3.5 0 0 0 0-7z',
};

/** An Embla carousel with buttons, dots and arrow-key support. No autoplay, so nothing to pause. */
export default function Carousel({ label, slides, kind = 'cards' }: Props) {
  const [viewportRef, embla] = useEmblaCarousel({ align: 'start', loop: false, skipSnaps: false });
  const [index, setIndex] = useState(0);
  const [snaps, setSnaps] = useState<number[]>([]);

  useEffect(() => {
    if (!embla) return;
    const update = () => setIndex(embla.selectedScrollSnap());
    setSnaps(embla.scrollSnapList());
    embla.on('select', update).on('reInit', () => setSnaps(embla.scrollSnapList()));
    update();
  }, [embla]);

  const prev = useCallback(() => embla?.scrollPrev(), [embla]);
  const next = useCallback(() => embla?.scrollNext(), [embla]);
  const onKey = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowLeft') { e.preventDefault(); prev(); }
    if (e.key === 'ArrowRight') { e.preventDefault(); next(); }
    if (e.key === 'Home') { e.preventDefault(); embla?.scrollTo(0); }
    if (e.key === 'End') { e.preventDefault(); embla?.scrollTo(slides.length - 1); }
  };

  return (
    <section className={`carousel carousel-${kind}`} aria-roledescription="carousel" aria-label={label}>
      <div className="carousel-controls">
        <button type="button" onClick={prev} disabled={index === 0} aria-label="Previous">
          <span aria-hidden="true">←</span>
        </button>
        <span className="carousel-count" aria-live="polite">
          {index + 1} of {slides.length}
        </span>
        <button type="button" onClick={next} disabled={index >= snaps.length - 1 && snaps.length > 0} aria-label="Next">
          <span aria-hidden="true">→</span>
        </button>
      </div>
      {/* A scrollable strip has to be reachable from the keyboard, and the arrow keys move it. */}
      {/* eslint-disable-next-line jsx-a11y/no-noninteractive-tabindex, jsx-a11y/no-static-element-interactions */}
      <div className="carousel-viewport" ref={viewportRef} tabIndex={0} onKeyDown={onKey}>
        <ul className="carousel-track">
          {slides.map((s, i) => (
            <li
              key={s.title + i}
              className="carousel-slide"
              aria-roledescription="slide"
              aria-label={`${i + 1} of ${slides.length}`}
            >
              <div className="card">
                {kind === 'steps' && <span className="step-number" aria-hidden="true">{s.step ?? i + 1}</span>}
                <h3>{s.href ? <a href={s.href}>{s.title}</a> : s.title}</h3>
                <p>{s.text}</p>
                {s.colour && s.badge && (
                  <span className={`badge ${s.colour}`}>
                    <svg viewBox="0 0 16 16" aria-hidden="true" focusable="false" fill="currentColor">
                      <path d={ICONS[s.colour] ?? ICONS.grey} />
                    </svg>
                    {s.badge}
                  </span>
                )}
                {s.href && s.linkText && (
                  <p className="card-link">
                    <a href={s.href}>{s.linkText}</a>
                  </p>
                )}
              </div>
            </li>
          ))}
        </ul>
      </div>
      {snaps.length > 1 && (
        <div className="carousel-dots" role="tablist" aria-label={`${label}: pages`}>
          {snaps.map((_, i) => (
            <button
              key={i}
              type="button"
              role="tab"
              aria-selected={i === index}
              aria-label={`Go to ${i + 1}`}
              className={i === index ? 'is-active' : ''}
              onClick={() => embla?.scrollTo(i)}
            />
          ))}
        </div>
      )}
    </section>
  );
}
