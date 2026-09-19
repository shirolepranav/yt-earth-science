import React, { useMemo } from "react";
import { Easing, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import * as THREE from "three";
import {
  ChartStage,
  formatValue,
  project,
} from "../components/charts/ChartStage";
import type { ChartProps } from "../types";

const clamp = {
  extrapolateLeft: "clamp" as const,
  extrapolateRight: "clamp" as const,
};

/**
 * A curved atmospheric lamina, with actual front, back, and edge surfaces.
 * The curvature is identical for both estimates; only atmospheric depth changes.
 */
function makeLamina(width: number, thickness: number, depth: number) {
  const positions: number[] = [];
  const segments = 48;

  const vertex = (x: number, top: boolean, front: boolean) => {
    const curve = -0.42 * Math.pow((x / width) * 2, 2);
    return [
      x,
      curve + (top ? thickness / 2 : -thickness / 2),
      front ? depth / 2 : -depth / 2,
    ];
  };

  const quad = (a: number[], b: number[], c: number[], d: number[]) => {
    positions.push(...a, ...b, ...c, ...a, ...c, ...d);
  };

  for (let i = 0; i < segments; i++) {
    const x0 = width * (i / segments - 0.5);
    const x1 = width * ((i + 1) / segments - 0.5);
    const a = vertex(x0, false, true);
    const b = vertex(x1, false, true);
    const c = vertex(x1, true, true);
    const d = vertex(x0, true, true);
    const e = vertex(x0, false, false);
    const f = vertex(x1, false, false);
    const g = vertex(x1, true, false);
    const h = vertex(x0, true, false);

    quad(a, b, c, d);
    quad(f, e, h, g);
    quad(d, c, g, h);
    quad(e, f, b, a);
    if (i === 0) quad(e, a, d, h);
    if (i === segments - 1) quad(b, f, g, c);
  }

  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute(
    "position",
    new THREE.Float32BufferAttribute(positions, 3),
  );
  geometry.computeVertexNormals();
  return geometry;
}

export default function Chart(props: ChartProps) {
  const frame = useCurrentFrame();
  const { width, height, durationInFrames } = useVideoConfig();

  const numbers = useMemo(
    () =>
      props.values.map((value) => {
        const parsed = Number(String(value).replace(/[^0-9.-]/g, ""));
        return Number.isFinite(parsed) ? parsed : 0;
      }),
    [props.values],
  );

  const count = Math.max(numbers.length, 1);
  const maximum = Math.max(...numbers.map(Math.abs), 1e-9);
  const highlighted = numbers.indexOf(Math.max(...numbers));
  const smallestHeight =
    numbers.length > 0
      ? (Math.min(...numbers.map(Math.abs)) / maximum) * 5.6
      : 0;

  const visibleHeight = 11.2;
  const visibleWidth = visibleHeight * (width / height);
  const sceneWidth = visibleWidth * 0.84;
  const gap = visibleWidth * 0.045;
  const panelWidth = (sceneWidth - gap * (count - 1)) / count;
  const baseY = 1.02;
  const layers = 32;
  const screenScale = height / 1080;

  // A locked, near-frontal camera makes the two atmospheric depths comparable.
  const camera = useMemo(
    () => ({
      position: [
        0,
        4,
        visibleHeight / (2 * Math.tan(THREE.MathUtils.degToRad(18))),
      ] as [number, number, number],
      target: [0, 4, 0] as [number, number, number],
      fov: 36,
    }),
    [],
  );

  const geometries = useMemo(
    () =>
      numbers.map((value) => {
        const fullHeight = (Math.abs(value) / maximum) * 5.6;
        return {
          layer: makeLamina(
            panelWidth,
            Math.max(0.012, (fullHeight / layers) * 0.64),
            0.78,
          ),
          crest: makeLamina(panelWidth, 0.046, 0.84),
          ground: makeLamina(panelWidth + 0.1, 0.46, 1.05),
          horizon: makeLamina(panelWidth + 0.1, 0.023, 1.07),
        };
      }),
    [numbers, maximum, panelWidth],
  );

  const columns = numbers.map((value, index) => {
    const start = durationInFrames * (index === highlighted ? 0.045 : 0.19);
    const end = durationInFrames * (index === highlighted ? 0.40 : 0.535);
    const rise = interpolate(frame, [start, end], [0, 1], {
      ...clamp,
      easing: Easing.inOut(Easing.cubic),
    });
    const fullHeight = (Math.abs(value) / maximum) * 5.6;
    const x = (index - (count - 1) / 2) * (panelWidth + gap);
    const opacity = interpolate(
      frame,
      [start, start + durationInFrames * 0.045],
      [0, 1],
      clamp,
    );
    return { value, index, x, rise, fullHeight, opacity };
  });

  const comparisonOpacity = interpolate(
    frame,
    [durationInFrames * 0.535, durationInFrames * 0.585],
    [0, 0.85],
    clamp,
  );

  const highColumn = columns[highlighted];
  const lowColumn = columns.reduce<(typeof columns)[number] | undefined>(
    (lowest, column) =>
      !lowest || column.fullHeight < lowest.fullHeight ? column : lowest,
    undefined,
  );

  const bracket =
    highColumn && lowColumn && highColumn.index !== lowColumn.index
      ? (() => {
          const middleX = (highColumn.x + lowColumn.x) / 2;
          const top = project(
            camera,
            [middleX, baseY + highColumn.fullHeight, 0.5],
            width,
            height,
          );
          const bottom = project(
            camera,
            [middleX, baseY + lowColumn.fullHeight, 0.5],
            width,
            height,
          );
          return { top, bottom };
        })()
      : undefined;

  return (
    <ChartStage
      brand={props.brand}
      camera={camera}
      title={props.title}
      source={props.source}
      subtitle={props.unit.length > 2 ? `in ${props.unit}` : undefined}
      overlay={
        <>
          {/* An unnumbered caliper makes the extra atmospheric depth tangible. */}
          {bracket ? (
            <svg
              width={width}
              height={height}
              style={{
                position: "absolute",
                inset: 0,
                overflow: "visible",
                pointerEvents: "none",
                opacity: comparisonOpacity,
              }}
            >
              <path
                d={[
                  `M ${bracket.top.x - 12 * screenScale} ${bracket.top.y}`,
                  `H ${bracket.top.x + 12 * screenScale}`,
                  `M ${bracket.top.x} ${bracket.top.y}`,
                  `V ${bracket.bottom.y}`,
                  `M ${bracket.bottom.x - 12 * screenScale} ${bracket.bottom.y}`,
                  `H ${bracket.bottom.x + 12 * screenScale}`,
                ].join(" ")}
                fill="none"
                stroke={props.brand.colors.accent}
                strokeWidth={2 * screenScale}
              />
            </svg>
          ) : null}

          {columns.map((column) => {
            const anchor = project(
              camera,
              [column.x, baseY, 0.7],
              width,
              height,
            );
            const panelPixels = (panelWidth / visibleWidth) * width;
            const isHighlight = column.index === highlighted;
            return (
              <div
                key={column.index}
                style={{
                  position: "absolute",
                  left: anchor.x,
                  top: height * 0.704,
                  width: panelPixels * 0.96,
                  transform: "translateX(-50%)",
                  padding: `${18 * screenScale}px ${10 * screenScale}px`,
                  textAlign: "center",
                  opacity: column.opacity,
                  background:
                    "radial-gradient(ellipse at center, rgba(5,12,19,0.96) 0%, rgba(5,12,19,0.72) 44%, rgba(5,12,19,0) 73%)",
                  fontFamily: "Arial, Helvetica, sans-serif",
                  textShadow: "0 3px 20px rgba(0,0,0,0.9)",
                }}
              >
                <div
                  style={{
                    color: isHighlight
                      ? props.brand.colors.accent
                      : props.brand.colors.text,
                    fontSize: 96 * screenScale,
                    fontWeight: 700,
                    lineHeight: 1.02,
                    letterSpacing: -3 * screenScale,
                    fontVariantNumeric: "tabular-nums",
                  }}
                >
                  {formatValue(column.value, props.unit, props.values)}
                </div>
                <div
                  style={{
                    color: props.brand.colors.text,
                    fontSize: 35 * screenScale,
                    fontWeight: 500,
                    lineHeight: 1.2,
                    marginTop: 10 * screenScale,
                  }}
                >
                  {props.labels[column.index] ?? ""}
                </div>
              </div>
            );
          })}
        </>
      }
    >
      {columns.map((column) => {
        const geometry = geometries[column.index];
        const isHighlight = column.index === highlighted;
        const color = isHighlight ? props.brand.colors.accent : "#7894AB";

        return (
          <group key={column.index} position={[column.x, 0, 0]}>
            {/* Matching curved Earth sections establish a shared baseline. */}
            <mesh geometry={geometry.ground} position={[0, baseY - 0.26, 0]}>
              <meshStandardMaterial
                color="#182B38"
                roughness={0.91}
                metalness={0.12}
              />
            </mesh>
            <mesh
              geometry={geometry.horizon}
              position={[0, baseY - 0.02, 0]}
            >
              <meshStandardMaterial
                color="#8AA8BA"
                emissive="#6D8BA0"
                emissiveIntensity={0.34}
                roughness={0.5}
              />
            </mesh>

            {/* Water-bearing atmospheric strata unfold, rather than a solid bar. */}
            {Array.from({ length: layers }, (_, layer) => {
              const fraction = (layer + 0.5) / layers;
              const altitude = fraction * column.fullHeight;
              const extraWater =
                isHighlight && altitude > smallestHeight + 0.02;
              const reveal = interpolate(
                column.rise,
                [fraction * 0.62, Math.min(1, fraction * 0.62 + 0.3)],
                [0, 1],
                clamp,
              );

              return (
                <mesh
                  key={layer}
                  geometry={geometry.layer}
                  position={[
                    0,
                    baseY + altitude * column.rise,
                    0,
                  ]}
                  visible={reveal > 0.001}
                >
                  <meshStandardMaterial
                    color={color}
                    emissive={color}
                    emissiveIntensity={extraWater ? 0.75 : 0.22}
                    roughness={0.38}
                    metalness={0.2}
                    transparent
                    opacity={
                      reveal *
                      (extraWater ? 0.87 : isHighlight ? 0.48 : 0.52)
                    }
                    depthWrite={false}
                    side={THREE.DoubleSide}
                  />
                </mesh>
              );
            })}

            <mesh
              geometry={geometry.crest}
              position={[0, baseY + column.fullHeight * column.rise, 0]}
              visible={column.rise > 0.005}
            >
              <meshStandardMaterial
                color={color}
                emissive={color}
                emissiveIntensity={isHighlight ? 1.2 : 0.5}
                roughness={0.24}
                metalness={0.18}
                transparent
                opacity={column.opacity}
              />
            </mesh>
          </group>
        );
      })}
    </ChartStage>
  );
}