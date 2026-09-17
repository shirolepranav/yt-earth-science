// The shape of the shot list that pipeline/shotlist.py produces.
// Keeping it in one file means the Python side and the React side can't
// silently drift apart - if you change one, TypeScript complains here.

type Timed = { start: number; end: number };

export type ChartKind = "bar" | "comparison" | "line" | "bignumber";

// What every chart component receives - the built-in ones and the ones GPT-6
// Astra writes per video. Numbers always arrive as data, never as code.
export type ChartData = {
  chartKind: ChartKind;
  title: string;
  labels: string[];
  values: (number | string)[];
  unit: string;
  source: string;
};
export type ChartProps = ChartData & { brand: Brand };

export type Shot = Timed &
  (
    // AI image-to-video or stock footage. playbackRate < 1 stretches a clip
    // that's slightly shorter than its shot.
    | { type: "clip"; src: string; playbackRate?: number }
    // AI keyframe with an optional depth map for the parallax camera move.
    | { type: "still"; src: string; depth?: string | null; seed: number }
    // `component` names a GPT-6 Astra component staged into src/generated/;
    // without one (or if it's missing) the built-in chart renders instead.
    | ({ type: "chart"; component?: string | null } & ChartData)
    | { type: "number"; value: string; label: string; source: string }
    // A recreated source page with one sentence highlighted - the receipts.
    | {
        type: "evidence";
        variant: "article" | "filing";
        publisher: string;
        headline: string;
        before: string;
        quote: string;
        after: string;
      }
    // ColdFusion-style question or fact card over a darkened AI plate.
    | { type: "card"; variant: "question" | "fact"; text: string; src: string }
  );

export type Brand = {
  colors: {
    accent: string;
    background: string;
    text: string;
    muted: string;
    positive: string;
    negative: string;
  };
  fonts: { heading: string; body: string };
};

export type ChartPreviewProps = {
  brand: Brand;
  chart: ChartData;
  component: string | null;
  durationSeconds: number;
};

export type ShotList = {
  title: string;
  durationSeconds: number;
  fps: number;
  width: number;
  height: number;
  brand: Brand;
  audioFile: string;
  shots: Shot[];
  letterbox?: boolean;
};
