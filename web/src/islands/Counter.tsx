import { animate, useInView, useReducedMotion } from 'motion/react';
import { useEffect, useRef, useState } from 'react';

interface Props {
  value: number;
  label: string;
}

/** A number that counts up once it scrolls into view. Static under reduced motion or without JS. */
export default function Counter({ value, label }: Props) {
  const ref = useRef<HTMLSpanElement>(null);
  const inView = useInView(ref, { once: true, margin: '-10% 0px' });
  const reduced = useReducedMotion();
  const [shown, setShown] = useState(value);
  // A ref, not state: setting state here re-ran the effect, whose cleanup stopped the count on
  // its first frame and left the number at 0.
  const started = useRef(false);

  useEffect(() => {
    if (!inView || started.current) return;
    started.current = true;
    if (reduced || value === 0) return;
    const controls = animate(0, value, {
      duration: 1.1,
      ease: 'easeOut',
      onUpdate: (v) => setShown(Math.round(v)),
    });
    // If anything interrupts the count, show the real figure rather than a partial one.
    return () => {
      controls.stop();
      setShown(value);
    };
  }, [inView, reduced, value]);

  return (
    <span className="counter">
      <span ref={ref} className="big" aria-hidden="true">
        {shown.toLocaleString('en-US')}
      </span>
      <span className="visually-hidden">{value.toLocaleString('en-US')}</span>
      <span className="what">{label}</span>
    </span>
  );
}
