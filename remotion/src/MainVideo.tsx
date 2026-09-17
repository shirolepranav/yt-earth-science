import React from "react";
import { AbsoluteFill, Audio, Sequence, staticFile, useVideoConfig } from "remotion";

import { useFonts } from "./fonts";
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

const ShotView: React.FC<{ shot: Shot; brand: ShotList["brand"] }> = ({ shot, brand }) => {
  switch (shot.type) {
    case "clip":
      return (
        <AbsoluteFill style={{ filter: FOOTAGE_GRADE }}>
          <StockClip src={shot.src} playbackRate={shot.playbackRate} />
        </AbsoluteFill>
      );
    case "still":
      return (
        <AbsoluteFill style={{ filter: FOOTAGE_GRADE }}>
          <ParallaxStill src={shot.src} depth={shot.depth} seed={shot.seed} />
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
 * The whole video, assembled from the shot list: the narration, one Sequence
 * per shot (cut hard on the storyboard's timings), and the film grade on top.
 * No captions and no kinetic text - on-screen words are limited to charts,
 * key numbers, evidence pages and the occasional card.
 */
export const MainVideo: React.FC<ShotList> = ({ brand, shots, audioFile, letterbox }) => {
  useFonts();
  const { fps } = useVideoConfig();
  const toFrames = (seconds: number) => Math.round(seconds * fps);

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
      <LookOverlay letterbox={letterbox} />
    </AbsoluteFill>
  );
};
