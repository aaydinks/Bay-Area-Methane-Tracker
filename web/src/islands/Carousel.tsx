import useEmblaCarousel from 'embla-carousel-react';
import { useCallback, useEffect, useRef, useState } from 'react';

export interface SlideImage {
  src: string;
  srcset?: string;
  sizes?: string;
  width: number;
  height: number;
  alt: string;
}

export interface Slide {
  title: string;
  text?: string;
  href?: string;
  linkText?: string;
  /** A result colour (red, orange, yellow, green, grey) and its label, when the slide has one. */
  colour?: string | null;
  badge?: string | null;
  /** A large figure shown under the title, such as an annual estimate. */
  figure?: string | null;
  image?: SlideImage;
  /** An illustration from ART, drawn above the title. */
  art?: string;
}

interface Props {
  label: string;
  slides: Slide[];
  /** "photos" leads each slide with its picture; "steps" with a numbered illustration. */
  kind?: 'photos' | 'steps';
  /** Milliseconds between automatic moves. */
  interval?: number;
}

const ICONS: Record<string, string> = {
  red: 'M8 2 15 14H1z',
  orange: 'M8 1l7 7-7 7-7-7z',
  yellow: 'M8 2a6 6 0 1 1 0 12A6 6 0 0 1 8 2z',
  green: 'M1 3h14L8 14z',
  grey: 'M8 2.5a5.5 5.5 0 1 1 0 11 5.5 5.5 0 0 1 0-11zm0 2a3.5 3.5 0 1 0 0 7 3.5 3.5 0 0 0 0-7z',
};

/* Line drawings for the steps, in the site's black, red and green. Decorative: the slide's title
   and text carry the meaning. */
const ART: Record<string, React.ReactNode> = {
  pass: (
    <>
      <path d="M8 62 C 40 52, 80 52, 112 62 L 112 72 L 8 72 Z" fill="var(--green)" />
      <path d="M44 16 l14 -6 l6 14 l-14 6 z" fill="var(--black)" />
      <path d="M30 22 l12 -5 l3 7 l-12 5 z M62 9 l12 -5 l3 7 l-12 5 z" fill="var(--red)" />
      <path d="M54 30 L 30 62 M58 30 L 90 62" stroke="var(--black)" strokeWidth="1.5" strokeDasharray="4 4" />
    </>
  ),
  plume: (
    <>
      <path d="M8 62 C 40 52, 80 52, 112 62 L 112 72 L 8 72 Z" fill="var(--green)" />
      <rect x="34" y="50" width="20" height="10" rx="2" fill="var(--black)" />
      <path d="M44 50 C 40 40, 52 34, 60 30 C 72 24, 84 26, 96 18" stroke="var(--red)" strokeWidth="9" strokeLinecap="round" fill="none" opacity="0.35" />
      <path d="M44 50 C 40 40, 52 34, 60 30 C 72 24, 84 26, 96 18" stroke="var(--red)" strokeWidth="3" strokeLinecap="round" fill="none" />
    </>
  ),
  count: (
    <>
      {[0, 1, 2, 3, 4, 5, 6, 7].map((i) => (
        <rect key={i} x={14 + i * 12} y="20" width="8" height="40" rx="2" fill={i === 2 || i === 6 ? 'var(--red)' : 'var(--green)'} stroke="var(--black)" strokeWidth="1" />
      ))}
      <path d="M10 66 H 110" stroke="var(--black)" strokeWidth="1.5" />
    </>
  ),
  range: (
    <>
      <path d="M10 60 H 110" stroke="var(--black)" strokeWidth="1.5" />
      {[20, 45, 70, 95].map((x) => <path key={x} d={`M${x} 56 V 64`} stroke="var(--black)" strokeWidth="1.5" />)}
      <rect x="28" y="30" width="62" height="14" rx="7" fill="var(--green)" />
      <path d="M28 37 H 90" stroke="var(--black)" strokeWidth="2" />
      <circle cx="56" cy="37" r="7" fill="var(--red)" stroke="var(--white)" strokeWidth="2" />
    </>
  ),
  controls: (
    <>
      <path d="M10 64 H 110" stroke="var(--black)" strokeWidth="1.5" />
      {[24, 48, 72, 96].map((x, i) => (
        <g key={x}>
          <rect x={x - 9} y={i === 1 ? 26 : 40} width="18" height={i === 1 ? 38 : 24} rx="3" fill={i === 1 ? 'var(--red)' : 'var(--green)'} stroke="var(--black)" strokeWidth="1" />
        </g>
      ))}
      <path d="M10 34 H 110" stroke="var(--black)" strokeWidth="1.5" strokeDasharray="5 4" />
    </>
  ),
  report: (
    <>
      <rect x="22" y="12" width="40" height="52" rx="3" fill="var(--white)" stroke="var(--black)" strokeWidth="1.5" />
      <path d="M30 24 H 54 M30 32 H 54 M30 40 H 46" stroke="var(--black)" strokeWidth="1.5" />
      <rect x="70" y="12" width="32" height="52" rx="3" fill="var(--green)" stroke="var(--black)" strokeWidth="1.5" />
      <circle cx="86" cy="34" r="8" fill="var(--red)" />
      <path d="M64 38 H 68" stroke="var(--black)" strokeWidth="1.5" />
    </>
  ),
};

/**
 * Two slides in view at a time. It moves on by one slide every few seconds and loops, and pauses
 * while the pointer or keyboard focus is on it, while the tab is hidden, under reduced motion,
 * or when the pause button is pressed. The side arrows, the dots and the left and right keys move
 * it by hand.
 */
export default function Carousel({ label, slides, kind = 'photos', interval = 5000 }: Props) {
  const rotates = slides.length > 2;
  const [viewportRef, embla] = useEmblaCarousel({ align: 'start', loop: rotates, slidesToScroll: 1, duration: 32 });
  const [index, setIndex] = useState(0);
  const [stopped, setStopped] = useState(false); // the pause button, or reduced motion
  const [held, setHeld] = useState(false); // pointer or focus inside, or the tab hidden
  const root = useRef<HTMLElement>(null);
  const timer = useRef<number | undefined>(undefined);

  useEffect(() => {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) setStopped(true);
  }, []);

  useEffect(() => {
    if (!embla) return;
    const update = () => setIndex(embla.selectedScrollSnap());
    embla.on('select', update).on('reInit', update);
    update();
    return () => {
      embla.off('select', update).off('reInit', update);
    };
  }, [embla]);

  const playing = rotates && !stopped && !held;
  const restart = useCallback(() => {
    window.clearInterval(timer.current);
    if (!embla || !playing) return;
    timer.current = window.setInterval(() => embla.scrollNext(), interval);
  }, [embla, playing, interval]);

  useEffect(() => {
    restart();
    return () => window.clearInterval(timer.current);
  }, [restart]);

  useEffect(() => {
    const onVisibility = () => setHeld(document.hidden);
    document.addEventListener('visibilitychange', onVisibility);
    return () => document.removeEventListener('visibilitychange', onVisibility);
  }, []);

  // A move by hand starts the wait for the next automatic move again.
  const go = useCallback((to: 'prev' | 'next' | number) => {
    if (!embla) return;
    if (to === 'prev') embla.scrollPrev();
    else if (to === 'next') embla.scrollNext();
    else embla.scrollTo(to);
    restart();
  }, [embla, restart]);

  const onKey = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowLeft') { e.preventDefault(); go('prev'); }
    if (e.key === 'ArrowRight') { e.preventDefault(); go('next'); }
  };
  const onBlur = (e: React.FocusEvent) => {
    if (!root.current?.contains(e.relatedTarget as Node | null)) setHeld(false);
  };

  return (
    <section
      ref={root}
      className={`carousel carousel-${kind}`}
      aria-roledescription="carousel"
      aria-label={label}
      onPointerEnter={() => setHeld(true)}
      onPointerLeave={() => setHeld(false)}
      onFocus={() => setHeld(true)}
      onBlur={onBlur}
    >
      <div className="carousel-stage">
        <button type="button" className="carousel-arrow prev" onClick={() => go('prev')} disabled={!rotates && index === 0} aria-label="Previous slide">
          <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M15 5l-7 7 7 7" /></svg>
        </button>
        {/* A scrollable strip has to be reachable from the keyboard, and the arrow keys move it. */}
        {/* eslint-disable-next-line jsx-a11y/no-noninteractive-tabindex, jsx-a11y/no-static-element-interactions */}
        <div className="carousel-viewport" ref={viewportRef} tabIndex={0} onKeyDown={onKey}>
          {/* Slides are groups, not list items: a list item given another role breaks its list. */}
          <div className="carousel-track">
            {slides.map((s, i) => (
              <div key={s.title + i} className="carousel-slide" role="group" aria-roledescription="slide" aria-label={`${i + 1} of ${slides.length}: ${s.title}`}>
                <article className="slide-card">
                  {s.image && (
                    <img
                      className="slide-image"
                      src={s.image.src}
                      srcSet={s.image.srcset}
                      sizes={s.image.sizes}
                      width={s.image.width}
                      height={s.image.height}
                      alt={s.image.alt}
                      loading="lazy"
                      decoding="async"
                    />
                  )}
                  {s.art && (
                    <div className="slide-art">
                      <span className="step-number" aria-hidden="true">{i + 1}</span>
                      <svg viewBox="0 0 120 76" aria-hidden="true" focusable="false" fill="none">{ART[s.art]}</svg>
                    </div>
                  )}
                  <div className="slide-body">
                    <h3>{s.href ? <a href={s.href}>{s.title}</a> : s.title}</h3>
                    {s.figure && <p className="slide-figure">{s.figure}</p>}
                    {s.text && <p className="slide-text">{s.text}</p>}
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
                </article>
              </div>
            ))}
          </div>
        </div>
        <button type="button" className="carousel-arrow next" onClick={() => go('next')} disabled={!rotates && index >= slides.length - 2} aria-label="Next slide">
          <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M9 5l7 7-7 7" /></svg>
        </button>
      </div>
      {/* Moves by hand are announced; automatic ones are not, so a screen reader is not interrupted. */}
      <p className="visually-hidden" aria-live={playing ? 'off' : 'polite'}>
        Showing slides {index + 1} and {((index + 1) % slides.length) + 1} of {slides.length}
      </p>
      {rotates && (
        <div className="carousel-foot">
          <button type="button" className="carousel-pause" onClick={() => setStopped((v) => !v)}>
            {stopped ? 'Play' : 'Pause'}
            <span className="visually-hidden"> automatic rotation</span>
          </button>
          <div className="carousel-dots">
            {slides.map((s, i) => (
              <button
                key={i}
                type="button"
                aria-label={`Show slide ${i + 1}: ${s.title}`}
                aria-current={i === index ? 'true' : undefined}
                className={i === index ? 'is-active' : ''}
                onClick={() => go(i)}
              />
            ))}
          </div>
        </div>
      )}
    </section>
  );
}
