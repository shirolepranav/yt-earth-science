import React from "react";
import { AbsoluteFill, useCurrentFrame, useVideoConfig } from "remotion";

/**
 * The grade that makes AI footage, stock footage, charts and cards read as one
 * film: a soft vignette, light film grain, and optional 2.39:1 bars.
 * (The desaturate/crush part of the grade is applied to footage only, in
 * MainVideo - charts and cards keep their colours.)
 *
 * Grain is SVG turbulence at a third of the resolution, scaled up: full-HD
 * turbulence every frame is needlessly slow in a headless browser. The seed
 * comes from the frame number, so it's deterministic across render tabs.
 */
export const LookOverlay: React.FC<{ letterbox?: boolean }> = ({ letterbox }) => {
  const frame = useCurrentFrame();
  const { width, height } = useVideoConfig();
  const bar = Math.round((height - width / 2.39) / 2);

  return (
    <AbsoluteFill style={{ pointerEvents: "none" }}>
      <AbsoluteFill
        style={{ background: "radial-gradient(ellipse at center, rgba(0,0,0,0) 55%, rgba(0,0,0,0.4) 100%)" }}
      />
      <AbsoluteFill style={{ mixBlendMode: "overlay", opacity: 0.2 }}>
        <svg width={width / 3} height={height / 3} style={{ transform: "scale(3)", transformOrigin: "0 0" }}>
          <filter id="grain">
            <feTurbulence type="fractalNoise" baseFrequency="0.8" numOctaves={2} seed={frame % 24} stitchTiles="stitch" />
            <feColorMatrix type="saturate" values="0" />
          </filter>
          <rect width="100%" height="100%" filter="url(#grain)" />
        </svg>
      </AbsoluteFill>
      {letterbox ? (
        <>
          <div style={{ position: "absolute", top: 0, left: 0, right: 0, height: bar, background: "#000" }} />
          <div style={{ position: "absolute", bottom: 0, left: 0, right: 0, height: bar, background: "#000" }} />
        </>
      ) : null}
    </AbsoluteFill>
  );
};
