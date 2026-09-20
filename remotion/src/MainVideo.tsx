import React from "react";
import { AbsoluteFill, Audio, Freeze, Sequence, interpolate, staticFile, useCurrentFrame, useVideoConfig } from "remotion";

import { BODY, useFonts } from "./fonts";
import { EvidenceCard } from "./components/EvidenceCard";
import { ImpactCard } from "./components/ImpactCard";
import { LookOverlay } from "./components/LookOverlay";
import { ParallaxStill } from "./components/ParallaxStill";
import { StockClip } from "./components/StockClip";
import { BigNumber } from "./components/charts/BigNumber";
import { ChartView } from "./components/charts/ChartView";
import type { Shot, ShotList } from "./types";

// Footage from four libraries and the occasional AI shot only reads as one film
// once it shares a grade: near-natural colour (a nature documentary, not the finance channel's crushed look).
const FOOTAGE_GRADE = "saturate(0.95) contrast(1.05) brightness(0.97)";

/**
 * Where a shot came from, bottom-left, in the same place and size as a chart's
 * source line. Only public-domain and openly licensed archives are named: it is
 * what turns "some footage of a volcano" into "this volcano, filmed by NASA".
 * Outside the grade, so the credit stays legible over a darkened shot.
 */
const FootageCredit: React.FC<{ credit: string; brand: ShotList["brand"] }> = ({ credit, brand }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const fade = interpolate(frame, [0, Math.round(0.4 * fps)], [0, 1], { extrapolateRight: "clamp" });
  return (
    <div
      style={{
        position: "absolute", left: 120, bottom: 36, opacity: 0.85 * fade,
        fontFamily: BODY, fontSize: 22, color: brand.colors.muted,
        textShadow: "0 2px 8px rgba(0,0,0,0.85)",
      }}
    >
      {credit}
    </div>
  );
};

const ShotView: React.FC<{ shot: Shot; brand: ShotList["brand"] }> = ({ shot, brand }) => {
  switch (shot.type) {
    case "clip":
      return (
        <AbsoluteFill>
          <AbsoluteFill style={{ filter: FOOTAGE_GRADE }}>
            <StockClip src={shot.src} playbackRate={shot.playbackRate} />
          </AbsoluteFill>
          {shot.credit ? <FootageCredit credit={shot.credit} brand={brand} /> : null}
        </AbsoluteFill>
      );
    case "still":
      return (
        <AbsoluteFill>
          <AbsoluteFill style={{ filter: FOOTAGE_GRADE }}>
            <ParallaxStill src={shot.src} depth={shot.depth} seed={shot.seed} />
          </AbsoluteFill>
          {shot.credit ? <FootageCredit credit={shot.credit} brand={brand} /> : null}
        </AbsoluteFill>
      );
    case "chart": {
      const { chartKind, title, labels, values, unit, source, component } = shot;
      return <ChartView brand={brand} component={component} chart={{ chartKind, title, labels, values, unit, source }} />;
    }
    case "number":
      return <BigNumber brand={brand} value={shot.value} label={shot.label} source={shot.source} />;
    case "evidence":
      return <EvidenceCard brand={brand} {...shot} />;
    case "card":
      return <ImpactCard brand={brand} variant={shot.variant} text={shot.text} src={shot.src} />;
  }
};

/**
 * The end-screen hold: the last shot's final frame, frozen, pushing in very
 * slowly while it fades most of the way to black. Nothing drawn on top -
 * YouTube places its video tiles and subscribe button over this.
 */
const Outro: React.FC<{ shot: Shot; brand: ShotList["brand"]; lastFrame: number }> = ({ shot, brand, lastFrame }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const dark = interpolate(frame, [0, 2 * fps], [0, 0.8], { extrapolateRight: "clamp" });
  return (
    <AbsoluteFill style={{ backgroundColor: brand.colors.background }}>
      <AbsoluteFill style={{ transform: `scale(${1 + frame * 0.00004})` }}>
        <Freeze frame={lastFrame}>
          <ShotView shot={shot} brand={brand} />
        </Freeze>
      </AbsoluteFill>
      <AbsoluteFill style={{ backgroundColor: "#000", opacity: dark }} />
    </AbsoluteFill>
  );
};

/**
 * The whole video, assembled from the shot list: the narration, one Sequence
 * per shot (cut hard on the storyboard's timings), and the film grade on top.
 * No captions and no kinetic text - on-screen words are limited to charts,
 * key numbers, evidence pages and the occasional card.
 */
export const MainVideo: React.FC<ShotList> = ({ brand, shots, audioFile, letterbox, outroSeconds }) => {
  useFonts();
  const { fps, durationInFrames } = useVideoConfig();
  const toFrames = (seconds: number) => Math.round(seconds * fps);
  const last = shots[shots.length - 1];
  const outroFrom = durationInFrames - toFrames(outroSeconds ?? 0);

  return (
    <AbsoluteFill style={{ backgroundColor: brand.colors.background }}>
      <Audio src={staticFile(audioFile)} />
      {shots.map((shot, index) => {
        const from = toFrames(shot.start);
        return (
          <Sequence key={index} from={from} durationInFrames={Math.max(1, toFrames(shot.end) - from)}>
            <ShotView shot={shot} brand={brand} />
          </Sequence>
        );
      })}
      {outroFrom < durationInFrames && last ? (
        <Sequence from={outroFrom}>
          <Outro shot={last} brand={brand} lastFrame={Math.max(0, toFrames(last.end) - toFrames(last.start) - 1)} />
        </Sequence>
      ) : null}
      <LookOverlay letterbox={letterbox} />
    </AbsoluteFill>
  );
};
