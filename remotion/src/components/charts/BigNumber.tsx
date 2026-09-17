import React from "react";
import { AbsoluteFill, Easing, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { BODY, DISPLAY } from "../../fonts";
import type { Brand } from "../../types";
import { ChartStage, useChartCamera } from "./ChartStage";

/**
 * One huge figure counting up over the dark three.js stage - the moment the
 * narration lands a number. "$40,000" keeps its prefix, separators and decimals
 * while the digits roll.
 */
export const BigNumber: React.FC<{ brand: Brand; value: string; label: string; source: string }> = ({ brand, value, label, source }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const camera = useChartCamera();

  const match = value.match(/^(.*?)(-?[\d,]*\.?\d+)(.*)$/);
  const [prefix, digits, suffix] = match ? [match[1], match[2], match[3]] : ["", "", value];
  const target = Number(digits.replace(/,/g, ""));
  const decimals = (digits.split(".")[1] ?? "").length;
  const t = interpolate(frame, [6, 6 + fps * 1.3], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.out(Easing.cubic) });
  const shown = digits
    ? (target * t).toLocaleString("en-US", { minimumFractionDigits: decimals, maximumFractionDigits: decimals, useGrouping: digits.includes(",") || target >= 10000 })
    : "";
  const pop = spring({ frame, fps, config: { damping: 14, mass: 0.6 } });

  // ChartStage draws the 3D stage; the figure sits on top as crisp DOM text.
  return (
    <AbsoluteFill>
      <ChartStage brand={brand} camera={camera} source={source} />
      <AbsoluteFill style={{ justifyContent: "center", alignItems: "center", flexDirection: "column" }}>
        <div
          style={{
            fontFamily: DISPLAY, fontWeight: 700, fontSize: 280, lineHeight: 1, color: brand.colors.accent,
            transform: `scale(${interpolate(pop, [0, 1], [0.85, 1])})`, textShadow: `0 0 60px ${brand.colors.accent}55, 0 6px 30px rgba(0,0,0,0.8)`,
          }}
        >
          {prefix}{shown}{suffix}
        </div>
        <div style={{ fontFamily: BODY, fontWeight: 600, fontSize: 40, letterSpacing: 6, textTransform: "uppercase", color: brand.colors.text, marginTop: 28, opacity: t }}>
          {label}
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
