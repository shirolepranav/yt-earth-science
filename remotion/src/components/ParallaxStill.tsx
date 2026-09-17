import React, { useMemo } from "react";
import { AbsoluteFill, Img, interpolate, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import { ThreeCanvas } from "@remotion/three";
import { useLoader } from "@react-three/fiber";
import * as THREE from "three";

/**
 * A still AI keyframe that moves like footage: a 2.5D parallax camera drift
 * driven by the image's depth map. Near pixels shift more than far ones, so a
 * flat image reads as a slow dolly past a real scene. Costs nothing per video -
 * it's why only the most important shots need paid image-to-video.
 *
 * Deterministic: motion comes only from the frame number and the shot's seed,
 * never a clock or Math.random(), so parallel render tabs agree.
 *
 * No depth map (the depth call failed) -> a plain slow push-in instead.
 */

const VERTEX = `
varying vec2 vUv;
void main() { vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }
`;

// Sample the depth (bright = near), then offset the colour lookup by it.
const FRAGMENT = `
uniform sampler2D map;
uniform sampler2D depthMap;
uniform vec2 offset;
uniform float zoom;
varying vec2 vUv;
void main() {
  vec2 uv = (vUv - 0.5) / zoom + 0.5;
  float depth = texture2D(depthMap, uv).r;
  gl_FragColor = texture2D(map, uv + offset * (depth - 0.5));
}
`;

// Four drift directions, picked per shot so consecutive stills don't all move the same way.
const DIRECTIONS: [number, number][] = [[1, 0.3], [-1, 0.2], [0.4, -1], [-0.5, 1]];

const Plane: React.FC<{ src: string; depth: string; seed: number }> = ({ src, depth, seed }) => {
  const frame = useCurrentFrame();
  const { width, height, durationInFrames } = useVideoConfig();
  const [map, depthMap] = useLoader(THREE.TextureLoader, [staticFile(src), staticFile(depth)]);

  const uniforms = useMemo(
    () => ({ map: { value: map }, depthMap: { value: depthMap }, offset: { value: new THREE.Vector2() }, zoom: { value: 1 } }),
    [map, depthMap],
  );

  const progress = interpolate(frame, [0, durationInFrames], [-1, 1]);
  const [dx, dy] = DIRECTIONS[seed % DIRECTIONS.length];
  uniforms.offset.value.set(dx * progress * 0.022, dy * progress * 0.012);
  uniforms.zoom.value = interpolate(frame, [0, durationInFrames], [1.07, 1.13]);

  return (
    <mesh>
      <planeGeometry args={[width, height]} />
      <shaderMaterial vertexShader={VERTEX} fragmentShader={FRAGMENT} uniforms={uniforms} />
    </mesh>
  );
};

export const ParallaxStill: React.FC<{ src: string; depth?: string | null; seed: number }> = ({ src, depth, seed }) => {
  const frame = useCurrentFrame();
  const { width, height, durationInFrames } = useVideoConfig();

  if (!depth) {
    const zoom = interpolate(frame, [0, durationInFrames], [1.03, 1.12]);
    return (
      <AbsoluteFill style={{ overflow: "hidden" }}>
        <Img src={staticFile(src)} style={{ width: "100%", height: "100%", objectFit: "cover", transform: `scale(${zoom})` }} />
      </AbsoluteFill>
    );
  }

  return (
    // Orthographic at zoom 1: one world unit is one pixel, so the plane is
    // exactly the frame. `linear` + `flat` pass the image colours through untouched.
    <ThreeCanvas width={width} height={height} orthographic linear flat camera={{ position: [0, 0, 10], zoom: 1 }}>
      <Plane src={src} depth={depth} seed={seed} />
    </ThreeCanvas>
  );
};
