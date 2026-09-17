import React from "react";
import { AbsoluteFill, OffthreadVideo, interpolate, staticFile, useCurrentFrame, useVideoConfig } from "remotion";

/**
 * Footage: an AI image-to-video clip or a stock clip, with a slow push-in.
 *
 * Hard cuts, no fades - the ColdFusion/Moon rhythm comes from cutting on the
 * narration, and a fade on every two-second shot turns that rhythm to mush.
 *
 * `playbackRate` below 1 stretches a clip that's a little shorter than its
 * shot (a 5s generation on a 6s shot plays at 0.83x, which reads as
 * deliberate slow motion rather than a frozen last frame).
 *
 * OffthreadVideo extracts frames with ffmpeg instead of playing the clip in
 * the browser - faster and far more reliable during a render.
 */
export const StockClip: React.FC<{ src: string; playbackRate?: number }> = ({ src, playbackRate }) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  const zoom = interpolate(frame, [0, durationInFrames], [1.02, 1.08]);

  return (
    <AbsoluteFill style={{ overflow: "hidden" }}>
      <OffthreadVideo
        src={staticFile(src)}
        muted
        playbackRate={playbackRate ?? 1}
        style={{ width: "100%", height: "100%", objectFit: "cover", transform: `scale(${zoom})` }}
      />
    </AbsoluteFill>
  );
};
