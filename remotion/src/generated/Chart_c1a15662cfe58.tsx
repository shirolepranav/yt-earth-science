import React, { useMemo } from "react";
import { Easing, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import * as THREE from "three";
import {
  ChartStage,
  Label,
  formatValue,
  project,
} from "../components/charts/ChartStage";
import type { Camera } from "../components/charts/ChartStage";
import type { ChartProps } from "../types";

const RADIUS = 7.5;
const HEIGHT = 5.8;
const LAYERS = 16;
const SEGMENTS = 48;

const profile = (t: number): number =>
  0.12 + 0.88 * Math.pow(1 - t, 1.25);

/** A solid, semicircular rock stratum, with its cut face toward the viewer. */
function makeStratum(index: number): THREE.BufferGeometry {
  const bottom = index / LAYERS;
  const top = (index + 1) / LAYERS;
  const rb = profile(bottom);
  const rt = profile(top);
  const yb = bottom * HEIGHT;
  const yt = top * HEIGHT;
  const vertices: number[] = [];

  const triangle = (
    a: number[],
    b: number[],
    c: number[],
  ): void => {
    vertices.push(...a, ...b, ...c);
  };

  for (let s = 0; s < SEGMENTS; s++) {
    const a = (s / SEGMENTS) * Math.PI;
    const b = ((s + 1) / SEGMENTS) * Math.PI;
    const lowerA = [Math.cos(a) * rb, yb, -Math.sin(a) * rb];
    const lowerB = [Math.cos(b) * rb, yb, -Math.sin(b) * rb];
    const upperA = [Math.cos(a) * rt, yt, -Math.sin(a) * rt];
    const upperB = [Math.cos(b) * rt, yt, -Math.sin(b) * rt];

    triangle(lowerA, upperA, upperB);
    triangle(lowerA, upperB, lowerB);
    triangle([0, yt, 0], upperB, upperA);
    triangle([0, yb, 0], lowerA, lowerB);
  }

  triangle([-rb, yb, 0], [rb, yb, 0], [rt, yt, 0]);
  triangle([-rb, yb, 0], [rt, yt, 0], [-rt, yt, 0]);

  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute(
    "position",
    new THREE.Float32BufferAttribute(vertices, 3),
  );
  geometry.computeVertexNormals();
  return geometry;
}

export default function Chart(props: ChartProps) {
  const frame = useCurrentFrame();
  const { width, height, durationInFrames } = useVideoConfig();
  const { colors } = props.brand;

  const numbers = props.values.map((value) => {
    const parsed = Number(String(value).replace(/[^0-9.-]/g, ""));
    return Number.isFinite(parsed) ? parsed : 0;
  });

  const maximum = Math.max(...numbers.map(Math.abs), 1e-9);
  const important = numbers.indexOf(Math.max(...numbers));
  const originalRadius = RADIUS * (Math.abs(numbers[0] ?? 0) / maximum);
  const finalRadius = RADIUS * (Math.abs(numbers[1] ?? 0) / maximum);

  const reveal = interpolate(
    frame,
    [0, durationInFrames * 0.09],
    [0, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );

  const expansion = interpolate(
    frame,
    [durationInFrames * 0.17, durationInFrames * 0.56],
    [0, 1],
    {
      easing: Easing.inOut(Easing.cubic),
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
    },
  );

  const radius =
    originalRadius + (finalRadius - originalRadius) * expansion;

  const newLabelOpacity = interpolate(
    frame,
    [durationInFrames * 0.2, durationInFrames * 0.3],
    [0, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );

  const distance = Math.max(
    18.3,
    (RADIUS * 2) /
      (0.82 * 2 * Math.tan(THREE.MathUtils.degToRad(17)) * (width / height)),
  );

  const camera: Camera = {
    position: [0, 3.5, distance],
    target: [0, 2.8, 0],
    fov: 34,
  };

  const geology = useMemo(() => {
    const layers = Array.from({ length: LAYERS }, (_, i) =>
      makeStratum(i),
    );

    const seams: number[] = [];
    for (let i = 1; i < LAYERS; i++) {
      const t = i / LAYERS;
      const r = profile(t);
      seams.push(-r, t * HEIGHT, 0.012, r, t * HEIGHT, 0.012);
    }
    const seamGeometry = new THREE.BufferGeometry();
    seamGeometry.setAttribute(
      "position",
      new THREE.Float32BufferAttribute(seams, 3),
    );

    const edgePoints: number[] = [];
    for (const side of [-1, 1]) {
      for (let i = 0; i < SEGMENTS; i++) {
        const a = i / SEGMENTS;
        const b = (i + 1) / SEGMENTS;
        edgePoints.push(
          side * profile(a), a * HEIGHT, 0.018,
          side * profile(b), b * HEIGHT, 0.018,
        );
      }
    }
    edgePoints.push(
      -profile(1), HEIGHT, 0.018,
      profile(1), HEIGHT, 0.018,
    );
    const edgeGeometry = new THREE.BufferGeometry();
    edgeGeometry.setAttribute(
      "position",
      new THREE.Float32BufferAttribute(edgePoints, 3),
    );

    const ghostPoints: number[] = [];
    for (const side of [-1, 1]) {
      for (let i = 0; i < SEGMENTS; i += 2) {
        const a = i / SEGMENTS;
        const b = (i + 1) / SEGMENTS;
        ghostPoints.push(
          side * profile(a), a * HEIGHT, 0.12,
          side * profile(b), b * HEIGHT, 0.12,
        );
      }
    }
    const ghostGeometry = new THREE.BufferGeometry();
    ghostGeometry.setAttribute(
      "position",
      new THREE.Float32BufferAttribute(ghostPoints, 3),
    );

    return { layers, seamGeometry, edgeGeometry, ghostGeometry };
  }, []);

  const oldLeft = project(camera, [-originalRadius, 0.25, 0.2], width, height);
  const oldRight = project(camera, [originalRadius, 0.25, 0.2], width, height);
  const newLeft = project(camera, [-radius, -0.38, 0.2], width, height);
  const newRight = project(camera, [radius, -0.38, 0.2], width, height);
  const leftFoot = project(camera, [-radius, 0, 0.2], width, height);
  const rightFoot = project(camera, [radius, 0, 0.2], width, height);

  const tick = height * 0.012;
  const stroke = Math.max(1.5, height * 0.002);
  const activeColor = important === 1 ? colors.accent : "#8296AE";
  const oldColor = important === 0 ? colors.accent : "#A3B4C9";

  return (
    <ChartStage
      brand={props.brand}
      camera={camera}
      title={props.title}
      source={props.source}
      subtitle={props.unit.length > 2 ? `in ${props.unit}` : undefined}
      overlay={
        <>
          <svg
            width={width}
            height={height}
            viewBox={`0 0 ${width} ${height}`}
            style={{ position: "absolute", inset: 0, overflow: "visible" }}
          >
            <g
              fill="none"
              stroke={oldColor}
              strokeWidth={stroke}
              opacity={reveal}
            >
              <path
                d={[
                  `M ${oldLeft.x} ${oldLeft.y} H ${oldRight.x}`,
                  `M ${oldLeft.x} ${oldLeft.y - tick} V ${oldLeft.y + tick}`,
                  `M ${oldRight.x} ${oldRight.y - tick} V ${oldRight.y + tick}`,
                ].join(" ")}
              />
              <path
                d={`M ${width * 0.2} ${height * 0.435}
                    V ${height * 0.55}
                    L ${oldLeft.x} ${oldLeft.y}`}
                opacity={0.65}
              />
            </g>

            <g
              fill="none"
              stroke={activeColor}
              strokeWidth={stroke}
              opacity={newLabelOpacity}
            >
              <path
                d={[
                  `M ${newLeft.x} ${newLeft.y} H ${newRight.x}`,
                  `M ${newLeft.x} ${newLeft.y - tick} V ${newLeft.y + tick}`,
                  `M ${newRight.x} ${newRight.y - tick} V ${newRight.y + tick}`,
                ].join(" ")}
              />
              <path
                d={`M ${leftFoot.x} ${leftFoot.y}
                    L ${newLeft.x} ${newLeft.y - tick * 1.5}
                    M ${rightFoot.x} ${rightFoot.y}
                    L ${newRight.x} ${newRight.y - tick * 1.5}`}
                opacity={0.4}
              />
              <path
                d={`M ${width * 0.8} ${height * 0.435}
                    L ${width * 0.9} ${height * 0.56}
                    L ${newRight.x} ${newRight.y}`}
                opacity={0.65}
              />
            </g>
          </svg>

          {numbers.map((value, index) => {
            const x = width * (index === 0 ? 0.2 : 0.8);
            const opacity = index === 0 ? reveal : newLabelOpacity;
            const highlighted = index === important;

            return (
              <React.Fragment key={index}>
                <Label
                  x={x}
                  y={height * 0.327}
                  size={height * 0.032}
                  color={highlighted ? colors.text : "#B5C1D0"}
                  opacity={opacity}
                  weight={500}
                >
                  {props.labels[index] ?? ""}
                </Label>
                <Label
                  x={x}
                  y={height * 0.388}
                  size={height * (highlighted ? 0.069 : 0.059)}
                  color={highlighted ? colors.accent : colors.text}
                  opacity={opacity}
                  weight={650}
                >
                  {formatValue(value, props.unit, props.values)}
                </Label>
              </React.Fragment>
            );
          })}
        </>
      }
    >
      {/* Width carries the measurement; the constant-height cutaway is sculptural. */}
      <group scale={[Math.max(radius, 0.001), 1, Math.max(radius * 0.4, 0.001)]}>
        {geology.layers.map((geometry, index) => (
          <mesh key={index} geometry={geometry}>
            <meshStandardMaterial
              color={index % 4 === 0 ? "#405064" : index % 2 === 0 ? "#293847" : "#334253"}
              roughness={0.94}
              metalness={0.06}
              emissive={activeColor}
              emissiveIntensity={(0.025 + expansion * 0.075) * (0.5 + index / LAYERS)}
              transparent
              opacity={reveal}
              side={THREE.DoubleSide}
            />
          </mesh>
        ))}

        <lineSegments geometry={geology.seamGeometry}>
          <lineBasicMaterial
            color={activeColor}
            transparent
            opacity={reveal * (0.12 + expansion * 0.24)}
          />
        </lineSegments>

        <lineSegments geometry={geology.edgeGeometry}>
          <lineBasicMaterial
            color={activeColor}
            transparent
            opacity={reveal * (0.35 + expansion * 0.65)}
          />
        </lineSegments>
      </group>

      {/* The original boundary stays etched into the exposed face as it widens. */}
      <group scale={[Math.max(originalRadius, 0.001), 1, 1]}>
        <lineSegments geometry={geology.ghostGeometry} renderOrder={5}>
          <lineBasicMaterial
            color={oldColor}
            transparent
            opacity={reveal * 0.9}
            depthTest={false}
            depthWrite={false}
          />
        </lineSegments>
      </group>

      <pointLight
        position={[radius * 0.65, 2.8, 3.5]}
        color={activeColor}
        intensity={expansion * 30}
        distance={16}
        decay={2}
      />
    </ChartStage>
  );
}