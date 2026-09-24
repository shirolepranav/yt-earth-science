import React from "react";
import { AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig, Easing } from "remotion";
import { ThreeCanvas } from "@remotion/three";
import { useThree } from "@react-three/fiber";
import * as THREE from "three";
import { BODY, DISPLAY } from "../../fonts";
import type { Brand } from "../../types";

/**
 * Everything the three.js charts share: a dark fogged stage with a faint floor
 * grid, a slow near-frontal camera move, and crisp HTML text on top.
 *
 * WHY THE TEXT IS HTML, NOT 3D
 * Numbers are the one thing on this channel that must be legible on a phone.
 * Labels are positioned by projecting 3D points through a camera identical to
 * the one inside the canvas, then drawn as ordinary DOM text in the brand
 * fonts - sharp at any size, no font-to-geometry pipeline, no async loaders.
 *
 * DETERMINISM
 * All motion comes from useCurrentFrame(), never react-three-fiber's useFrame()
 * (a real clock) or Math.random() - parallel render tabs must draw identical frames.
 */

export type Camera = { position: [number, number, number]; target: [number, number, number]; fov: number };

/** A slow dolly in from slightly left and above - never more than ~15 degrees off-axis. */
export const useChartCamera = (): Camera => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  const t = interpolate(frame, [0, durationInFrames], [0, 1], { easing: Easing.out(Easing.cubic) });
  return {
    position: [interpolate(t, [0, 1], [-2.6, 0.9]), interpolate(t, [0, 1], [3.4, 2.7]), interpolate(t, [0, 1], [13.5, 11.2])],
    target: [0, 2.5, 0],
    fov: 40,
  };
};

/** Where a 3D point lands on screen, in pixels, for the given camera. */
export const project = (camera: Camera, point: [number, number, number], width: number, height: number) => {
  const cam = new THREE.PerspectiveCamera(camera.fov, width / height, 0.1, 200);
  cam.position.set(...camera.position);
  cam.lookAt(...camera.target);
  cam.updateMatrixWorld();
  const v = new THREE.Vector3(...point).project(cam);
  return { x: ((v.x + 1) / 2) * width, y: ((1 - v.y) / 2) * height };
};

/** 0 -> 1 rise for element `index`, staggered, starting after `delay` frames. */
export const useRise = (index: number, delay = 10) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  return spring({ frame: frame - delay - index * 4, fps, config: { damping: 200 }, durationInFrames: Math.round(fps * 1.6) });
};

const decimalsOf = (values: (number | string)[]) =>
  Math.max(0, ...values.map((v) => (String(v).split(".")[1] ?? "").replace(/\D/g, "").length));

/** "7.2%", "$40,000", "52 basis points" - unit placed the way people read it. */
export const formatValue = (value: number, unit: string, values: (number | string)[]) => {
  const n = value.toLocaleString("en-US", { minimumFractionDigits: decimalsOf(values), maximumFractionDigits: decimalsOf(values) });
  if (unit === "$" || /^\$|dollar/i.test(unit)) return `$${n}`;
  if (unit.startsWith("%") || /^percent/i.test(unit)) return `${n}%`;  // "% change, inflation-adjusted" -> 21%
  if (unit.length <= 2) return `${n}${unit}`;
  return n; // long units ("basis points") go in the subtitle instead
};

const CameraRig: React.FC<{ camera: Camera }> = ({ camera }) => {
  const three = useThree();
  const cam = three.camera as THREE.PerspectiveCamera;
  cam.fov = camera.fov;
  cam.position.set(...camera.position);
  cam.lookAt(...camera.target);
  cam.updateProjectionMatrix();
  return null;
};

export const Label: React.FC<{ x: number; y: number; size: number; color: string; font?: string; weight?: number; opacity?: number; children: React.ReactNode }> = ({
  x, y, size, color, font = DISPLAY, weight = 600, opacity = 1, children,
}) => (
  <div
    style={{
      position: "absolute", left: x, top: y, transform: "translate(-50%, -50%)", whiteSpace: "nowrap",
      fontFamily: font, fontWeight: weight, fontSize: size, color, opacity, textShadow: "0 2px 18px rgba(0,0,0,0.8)",
    }}
  >
    {children}
  </div>
);

export const ChartStage: React.FC<{
  brand: Brand;
  camera: Camera;
  title?: string;
  subtitle?: string;
  source?: string;
  overlay?: React.ReactNode;
  children?: React.ReactNode;
}> = ({ brand, camera, title, subtitle, source, overlay, children }) => {
  const frame = useCurrentFrame();
  const { width, height } = useVideoConfig();
  const intro = interpolate(frame, [0, 12], [0, 1], { extrapolateRight: "clamp" });

  return (
    <AbsoluteFill style={{ backgroundColor: brand.colors.background }}>
      <ThreeCanvas width={width} height={height} camera={{ position: camera.position, fov: camera.fov }}>
        <CameraRig camera={camera} />
        <color attach="background" args={[brand.colors.background]} />
        <fog attach="fog" args={[brand.colors.background, 12, 30]} />
        <ambientLight intensity={0.45} />
        <directionalLight position={[-5, 9, 7]} intensity={0.9} />
        <pointLight position={[0, 5, 4]} intensity={18} distance={16} color={brand.colors.accent} />
        <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -0.01, 0]}>
          <planeGeometry args={[60, 60]} />
          <meshStandardMaterial color="#0A0D12" roughness={0.95} />
        </mesh>
        <gridHelper args={[60, 60, "#1E2733", "#141A22"]} />
        {children}
      </ThreeCanvas>

      <AbsoluteFill>{overlay}</AbsoluteFill>

      {title ? (
        <div style={{ position: "absolute", left: 120, top: 90, right: 120, opacity: intro }}>
          <div style={{ fontFamily: DISPLAY, fontWeight: 600, fontSize: 64, color: brand.colors.text, textTransform: "uppercase", letterSpacing: 1, lineHeight: 1.05 }}>
            {title}
          </div>
          {subtitle ? (
            <div style={{ fontFamily: BODY, fontSize: 28, color: brand.colors.muted, marginTop: 12 }}>{subtitle}</div>
          ) : null}
        </div>
      ) : null}

      {/* `source` is drawn by MainVideo's SourceLine, above the vignette. */}
    </AbsoluteFill>
  );
};
