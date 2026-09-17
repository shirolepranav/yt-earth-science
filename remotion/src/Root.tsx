import React from "react";
import { Composition } from "remotion";
import { AbsoluteFill } from "remotion";
import { MainVideo } from "./MainVideo";
import { ChartView } from "./components/charts/ChartView";
import { useFonts } from "./fonts";
import type { ChartPreviewProps, ShotList } from "./types";
import demoProps from "../demo-props.json";

/**
 * Registers the one composition this project renders.
 *
 * The interesting part is calculateMetadata: the video's length, size and frame
 * rate all come from the shot list rather than being hardcoded here. That means
 * a 9-minute video and a 13-minute video use the exact same composition.
 */
// One chart on its own, for pipeline/charts3d.py to test-render each component
// GPT-6 Astra writes before it is allowed into the video.
const ChartPreview: React.FC<ChartPreviewProps> = ({ brand, chart, component }) => {
  useFonts();
  return (
    <AbsoluteFill style={{ backgroundColor: brand.colors.background }}>
      <ChartView brand={brand} chart={chart} component={component} />
    </AbsoluteFill>
  );
};

export const RemotionRoot: React.FC = () => {
  return (
    <>
    <Composition
      id="ChartPreview"
      component={ChartPreview}
      defaultProps={{
        brand: (demoProps as unknown as ShotList).brand,
        chart: { chartKind: "bar", title: "Preview", labels: ["A", "B"], values: [1, 2], unit: "%", source: "demo" },
        component: null,
        durationSeconds: 6,
      } as ChartPreviewProps}
      calculateMetadata={({ props }) => ({ durationInFrames: Math.ceil((props as ChartPreviewProps).durationSeconds * 30) })}
      durationInFrames={180}
      fps={30}
      width={1920}
      height={1080}
    />
    <Composition
      id="MainVideo"
      component={MainVideo}
      // These are only used when you open Remotion Studio with no props file -
      // they give you something to look at while you're building components.
      defaultProps={demoProps as unknown as ShotList}
      calculateMetadata={({ props }) => {
        const list = props as ShotList;
        return {
          durationInFrames: Math.ceil(list.durationSeconds * list.fps),
          fps: list.fps,
          width: list.width,
          height: list.height,
        };
      }}
      // Placeholders; calculateMetadata replaces all four at render time.
      durationInFrames={300}
      fps={30}
      width={1920}
      height={1080}
    />
    </>
  );
};
