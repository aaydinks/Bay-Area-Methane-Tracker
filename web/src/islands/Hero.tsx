import { motion, useReducedMotion, type TargetAndTransition } from 'motion/react';

interface Site {
  name: string;
  x: number;
  y: number;
}

interface Props {
  sites: Site[];
  /** Which site grows a plume in the animation. */
  plumeAt: number;
}

/**
 * A stylised Bay with the five landfills, a satellite swath sweeping across, and a plume forming
 * over one site. Decorative: the text beside it carries the meaning. Under reduced motion every
 * element is drawn in its final state.
 */
export default function Hero({ sites, plumeAt }: Props) {
  const reduced = useReducedMotion();
  const plume = sites[plumeAt] ?? sites[0];
  const sweep: TargetAndTransition = reduced
    ? { x: 860 }
    : { x: [-260, 860], transition: { duration: 9, ease: 'linear', repeat: Infinity, repeatDelay: 1.5 } };
  const grow: TargetAndTransition = reduced
    ? { opacity: 0.75, scale: 1 }
    : {
        opacity: [0, 0.75, 0.75, 0],
        scale: [0.2, 1, 1.15, 1.3],
        transition: { duration: 9, times: [0.3, 0.45, 0.8, 1], repeat: Infinity, repeatDelay: 1.5 },
      };

  return (
    <svg className="hero-art" viewBox="0 0 800 500" role="img" aria-labelledby="hero-title hero-desc">
      <title id="hero-title">A satellite pass over the Bay Area</title>
      <desc id="hero-desc">
        A simplified map of the Bay with five landfills marked. A satellite swath sweeps across and a plume
        forms over one of them.
      </desc>
      <defs>
        <linearGradient id="swath" x1="0" x2="1">
          <stop offset="0" stopColor="var(--accent)" stopOpacity="0" />
          <stop offset="0.5" stopColor="var(--accent)" stopOpacity="0.28" />
          <stop offset="1" stopColor="var(--accent)" stopOpacity="0" />
        </linearGradient>
        <radialGradient id="plume">
          <stop offset="0" stopColor="var(--result-yellow)" stopOpacity="0.9" />
          <stop offset="1" stopColor="var(--result-yellow)" stopOpacity="0" />
        </radialGradient>
        <clipPath id="frame">
          <rect x="0" y="0" width="800" height="500" rx="18" />
        </clipPath>
      </defs>
      <g clipPath="url(#frame)">
        <rect x="0" y="0" width="800" height="500" fill="var(--hero-land)" />
        {/* The Bay, the Delta and the ocean, as simple shapes */}
        <path
          d="M0 170 C 120 150, 150 120, 170 60 L 0 40 Z"
          fill="var(--hero-water)"
        />
        <path
          d="M250 90 C 300 120, 330 170, 345 220 C 360 280, 380 330, 420 360 C 470 400, 520 420, 560 470 L 520 500 L 380 500 C 350 450, 330 420, 300 380 C 260 330, 230 280, 215 230 C 205 180, 215 130, 250 90 Z"
          fill="var(--hero-water)"
        />
        <path d="M560 140 C 620 150, 700 130, 800 160 L 800 230 C 700 210, 620 230, 560 200 Z" fill="var(--hero-water)" />
        <path d="M250 90 L 290 60 L 345 95 L 330 150 Z" fill="var(--hero-water)" />
        {/* County-like lines, decorative */}
        <g stroke="var(--border)" strokeWidth="1.5" fill="none" opacity="0.7">
          <path d="M60 300 L 200 260 L 215 230" />
          <path d="M420 360 L 520 300 L 640 320 L 800 290" />
          <path d="M345 220 L 460 190 L 560 200" />
        </g>
        <motion.g initial={false} animate={grow} style={{ transformOrigin: `${plume.x}px ${plume.y}px` }}>
          <ellipse cx={plume.x + 18} cy={plume.y - 10} rx="54" ry="30" fill="url(#plume)" />
        </motion.g>
        {sites.map((s) => (
          <g key={s.name}>
            <circle cx={s.x} cy={s.y} r="7" fill="var(--accent)" stroke="var(--bg)" strokeWidth="2" />
            <text x={s.x + 11} y={s.y + 4} fontSize="13" fill="var(--text)">
              {s.name}
            </text>
          </g>
        ))}
        <motion.g initial={false} animate={sweep}>
          <rect x="0" y="-40" width="200" height="580" fill="url(#swath)" transform="skewX(-12)" />
          <line x1="100" y1="-40" x2="100" y2="540" stroke="var(--accent)" strokeWidth="1.5" strokeDasharray="6 8" transform="skewX(-12)" opacity="0.8" />
          <g transform="translate(100 -8)">
            <rect x="-10" y="-6" width="20" height="12" rx="2" fill="var(--text)" />
            <rect x="-34" y="-3" width="20" height="6" fill="var(--accent)" />
            <rect x="14" y="-3" width="20" height="6" fill="var(--accent)" />
          </g>
        </motion.g>
      </g>
    </svg>
  );
}
