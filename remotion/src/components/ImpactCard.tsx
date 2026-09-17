import React from "react";
import { AbsoluteFill, Img, interpolate, spring, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import { DISPLAY } from "../fonts";
import type { Brand } from "../types";

/**
 * A ColdFusion-style card: a few condensed all-caps words punched in one at a
 * time over a darkened, blurred cinematic plate. "question" cards open a
 * section ("WHY WOULD A BANK DO THIS?"); "fact" cards land a key figure.
 * Figures and question marks go in the accent colour. Sparse by design -
 * storyboard.max_cards - these are chapter beats, never captions.
 */
export const ImpactCard: React.FC<{ brand: Brand; variant: "question" | "fact"; text: string; src: string }> = ({ brand, variant, text, src }) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const words = text.split(/\s+/).filter(Boolean);
  const size = words.length > 4 ? 118 : 150;

  return (
    <AbsoluteFill style={{ backgroundColor: "#000", overflow: "hidden" }}>
      <Img
        src={staticFile(src)}
        style={{
          width: "100%", height: "100%", objectFit: "cover",
          filter: "brightness(0.32) blur(5px) saturate(0.7)",
          transform: `scale(${interpolate(frame, [0, durationInFrames], [1.08, 1.16])})`,
        }}
      />
      <AbsoluteFill style={{ opacity: interpolate(frame, [0, 6], [0, 1], { extrapolateRight: "clamp" }) }}>
        <div style={{ position: "absolute", left: 160, right: 160, top: "50%", transform: "translateY(-50%)" }}>
          <div style={{ fontFamily: DISPLAY, fontWeight: 700, fontSize: size, lineHeight: 1.02, textTransform: "uppercase", textAlign: variant === "question" ? "left" : "center" }}>
            {words.map((word, i) => {
              const pop = spring({ frame: frame - 4 - i * 5, fps, config: { damping: 16, mass: 0.5 } });
              const highlight = /[\d$%?]/.test(word);
              return (
                <span
                  key={i}
                  style={{
                    display: "inline-block", marginRight: "0.22em",
                    color: highlight ? brand.colors.accent : brand.colors.text,
                    opacity: Math.min(1, pop * 2),
                    transform: `scale(${interpolate(pop, [0, 1], [1.35, 1])})`,
                    textShadow: "0 8px 40px rgba(0,0,0,0.9)",
                  }}
                >
                  {word}
                </span>
              );
            })}
          </div>
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
