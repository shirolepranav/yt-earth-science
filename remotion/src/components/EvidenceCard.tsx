import React from "react";
import { AbsoluteFill, Easing, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { BODY, SERIF } from "../fonts";
import type { Brand } from "../types";

/**
 * The receipts. A recreated page from one of this video's real sources -
 * publisher, headline, the surrounding paragraph - with the exact sentence the
 * narration leans on swept with a highlighter while the camera pushes in.
 *
 * This is what ColdFusion does with S-1 filings and Moon with news articles:
 * the alarming claim is never just asserted, it's shown. Built from the text
 * research already collected (the storyboard only lets through quotes that
 * appear verbatim in the source), so there are no screenshots, cookie banners
 * or paywalls to fight.
 */
export const EvidenceCard: React.FC<{
  brand: Brand;
  variant: "article" | "filing";
  publisher: string;
  headline: string;
  before: string;
  quote: string;
  after: string;
}> = ({ brand, variant, publisher, headline, before, quote, after }) => {
  const frame = useCurrentFrame();
  const { durationInFrames, fps } = useVideoConfig();
  const filing = variant === "filing";

  const enter = interpolate(frame, [0, 10], [0, 1], { extrapolateRight: "clamp", easing: Easing.out(Easing.cubic) });
  const sweep = interpolate(frame, [fps * 0.5, fps * 1.4], [0, 100], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.inOut(Easing.quad) });
  const push = interpolate(frame, [0, durationInFrames], [1.0, 1.16]);
  const marker = filing ? "rgba(255,140,26,0.55)" : "rgba(245,200,35,0.6)";
  const ink = filing ? "#1D1F24" : "#1A1712";

  return (
    <AbsoluteFill style={{ backgroundColor: "#07090C", overflow: "hidden" }}>
      <AbsoluteFill style={{ background: `radial-gradient(circle at 50% 40%, ${brand.colors.accent}14 0%, #07090C 70%)` }} />
      <AbsoluteFill style={{ justifyContent: "center", alignItems: "center" }}>
        <div
          style={{
            width: 1320,
            padding: "70px 90px",
            backgroundColor: filing ? "#F7F7F4" : "#F3EFE6",
            boxShadow: "0 40px 120px rgba(0,0,0,0.7)",
            transform: `translateY(${(1 - enter) * 40}px) rotate(-1.2deg) scale(${push})`,
            transformOrigin: "50% 62%",
            opacity: enter,
          }}
        >
          <div style={{ fontFamily: BODY, fontWeight: 700, fontSize: 22, letterSpacing: 4, textTransform: "uppercase", color: filing ? "#555B66" : "#8B1A1A" }}>
            {filing ? `Filing excerpt · ${publisher}` : publisher}
          </div>
          <div style={{ fontFamily: filing ? BODY : SERIF, fontWeight: 700, fontSize: filing ? 44 : 58, lineHeight: 1.12, color: ink, margin: "18px 0 30px" }}>
            {headline}
          </div>
          <div style={{ height: 2, backgroundColor: "#00000022", marginBottom: 30 }} />
          <div style={{ fontFamily: SERIF, fontSize: 34, lineHeight: 1.55, color: ink }}>
            <span style={{ opacity: 0.45 }}>{before} </span>
            <span
              style={{
                backgroundImage: `linear-gradient(${marker}, ${marker})`,
                backgroundRepeat: "no-repeat",
                backgroundSize: `${sweep}% 100%`,
                WebkitBoxDecorationBreak: "clone",
                boxDecorationBreak: "clone",
                fontWeight: 600,
              }}
            >
              {quote}
            </span>
            <span style={{ opacity: 0.45 }}> {after}</span>
          </div>
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
