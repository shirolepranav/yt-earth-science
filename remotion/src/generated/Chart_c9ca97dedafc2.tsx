import React, { useMemo } from "react";
import { Easing, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import * as THREE from "three";
import {
  ChartStage,
  Label,
  formatValue,
  project,
} from "../components/charts/ChartStage";
import { BODY, DISPLAY } from "../fonts";
import type { ChartProps } from "../types";

/**
 * Two windows through the same curved atmosphere.
 * Water accumulates as illuminated, suspended laminae—not solid columns.
 * Equal vertical distances represent equal increases in both windows.
 */
function atmosphericRibbon(
  center: number,
  width: number,
  thickness: number,
  depth: number,
  curvature: number,
): THREE.BufferGeometry {
  const segments = 48;
  const vertices: number[] = [];
  const indices: number[] = [];

  for (let i = 0; i <= segments; i++) {
    const x = (i / segments - 0.5) * width;
    const surface = -curvature * (x + center) ** 2;

    vertices.push(
      x, surface, -depth / 2,
      x, surface, depth / 2,
      x, surface + thickness, -depth / 2,
      x, surface + thickness, depth / 2,
    );

    if (i < segments) {
      const a = i * 4;
      const b = a + 4;
      indices.push(
        a, b, a + 1, a + 1, b, b + 1,
        a + 2, a + 3, b + 2, a + 3, b + 3, b + 2,
        a, a + 2, b, a + 2, b + 2, b,
        a + 1, b + 1, a + 3, a + 3, b + 1, b + 3,
      );
    }
  }

  indices.push(0, 1, 2, 1, 3, 2);
  const end = segments * 4;
  indices.push(end, end + 2, end + 1, end + 1, end + 2, end + 3);

  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute(
    "position",
    new THREE.Float32BufferAttribute(vertices, 3),
  );
  geometry.setIndex(indices);
  geometry.computeVertexNormals();
  return geometry;
}

export default function Chart(props: ChartProps) {
  const frame = useCurrentFrame();
  const { width, height, durationInFrames } = useVideoConfig();
  const progress = frame / Math.max(1, durationInFrames - 1);

  const numbers = useMemo(
    () =>
      props.values.map((value) => {
        const parsed = Number(String(value).replace(/[^0-9.-]/g, ""));
        return Number.isFinite(parsed) ? parsed : 0;
      }),
    [props.values],
  );

  const maximum = Math.max(...numbers.map(Math.abs), 1e-9);
  const important = numbers.indexOf(Math.max(...numbers));
  const count = Math.max(1, numbers.length);

  const viewHeight = 8.4;
  const viewWidth = viewHeight * width / height;
  const span = viewWidth * 0.79;
  const pitch = span / count;
  const ribbonWidth = pitch * 0.87;
  const baseline = 0.65;
  const fullHeight = 4.8;
  const layerStep = fullHeight / 48;
  const curvature = 0.68 / Math.max((span / 2) ** 2, 0.01);

  const camera = useMemo(
    () => ({
      position: [
        0,
        3.5,
        viewHeight / (2 * Math.tan(THREE.MathUtils.degToRad(17))),
      ] as [number, number, number],
      target: [0, 3.5, 0] as [number, number, number],
      fov: 34,
    }),
    [],
  );

  const windows = useMemo(
    () =>
      numbers.map((value, index) => {
        const x = (index - (count - 1) / 2) * pitch;
        const magnitude = Math.abs(value) / maximum * fullHeight;
        return {
          x,
          value,
          magnitude,
          geometry: atmosphericRibbon(
            x, ribbonWidth, 0.032, 0.78, curvature,
          ),
          capGeometry: atmosphericRibbon(
            x, ribbonWidth, 0.052, 0.9, curvature,
          ),
          layers: Array.from(
            { length: Math.ceil(magnitude / layerStep) },
            (_, layer) => layer * layerStep,
          ),
        };
      }),
    [numbers, count, pitch, maximum, ribbonWidth, curvature],
  );

  const earthGeometry = useMemo(
    () => atmosphericRibbon(0, span * 1.13, 0.34, 1.5, curvature),
    [span, curvature],
  );
  const horizonGeometry = useMemo(
    () => atmosphericRibbon(0, span * 1.13, 0.025, 1.56, curvature),
    [span, curvature],
  );
  const ruleGeometry = useMemo(() => new THREE.BoxGeometry(1, 1, 1), []);

  const riseFor = (index: number): number => {
    const stagger = count > 1 ? index / (count - 1) : 0;
    return interpolate(
      progress,
      [0.075 + stagger * 0.16, 0.43 + stagger * 0.14],
      [0, 1],
      {
        extrapolateLeft: "clamp",
        extrapolateRight: "clamp",
        easing: Easing.inOut(Easing.cubic),
      },
    );
  };

  const secondaryHeight = Math.min(
    ...windows.map((item) => item.magnitude),
  );
  const difference = Math.max(0, fullHeight - secondaryHeight);
  const comparisonReveal = interpolate(
    progress,
    [0.50, 0.59],
    [0, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );
  const accent = props.brand.colors.accent;
  const secondaryColor = "#819BAD";

  return (
    <ChartStage
      brand={props.brand}
      camera={camera}
      title={props.title}
      source={props.source}
      subtitle={props.unit.length > 2 ? `in ${props.unit}` : undefined}
      overlay={
        <>
          {windows.map((item, index) => {
            const position = project(
              camera,
              [item.x, baseline, 0],
              width,
              height,
            );
            const highlighted = index === important;
            const reveal = interpolate(
              riseFor(index),
              [0, 0.16],
              [0, 1],
              { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
            );

            return (
              <Label
                key={index}
                x={position.x}
                y={height * 0.80}
                size={height * 0.033}
                color={props.brand.colors.text}
                opacity={reveal}
              >
                <div
                  style={{
                    width: width * 0.35,
                    padding: `${height * 0.017}px ${width * 0.01}px`,
                    textAlign: "center",
                    background:
                      "radial-gradient(ellipse, rgba(5,12,20,0.94) 0%, rgba(5,12,20,0.7) 42%, rgba(5,12,20,0) 73%)",
                  }}
                >
                  <div
                    style={{
                      fontFamily: DISPLAY,
                      fontSize: height * 0.086,
                      lineHeight: 1.08,
                      fontWeight: 650,
                      letterSpacing: "-0.035em",
                      color: highlighted ? accent : props.brand.colors.text,
                      fontVariantNumeric: "tabular-nums",
                    }}
                  >
                    {formatValue(item.value, props.unit, props.values)}
                  </div>
                  <div
                    style={{
                      marginTop: height * 0.01,
                      fontFamily: BODY,
                      fontSize: height * 0.032,
                      fontWeight: 500,
                      lineHeight: 1.2,
                      whiteSpace: "normal",
                      color: highlighted
                        ? props.brand.colors.text
                        : secondaryColor,
                    }}
                  >
                    {props.labels[index] ?? ""}
                  </div>
                </div>
              </Label>
            );
          })}
        </>
      }
    >
      {/* A continuous planetary limb makes the shared baseline explicit. */}
      <mesh
        geometry={earthGeometry}
        position={[0, baseline - 0.35, 0]}
      >
        <meshStandardMaterial
          color="#101F2A"
          roughness={0.85}
          metalness={0.15}
        />
      </mesh>
      <mesh
        geometry={horizonGeometry}
        position={[0, baseline, 0]}
      >
        <meshStandardMaterial
          color="#67889B"
          emissive="#67889B"
          emissiveIntensity={0.45}
          roughness={0.5}
        />
      </mesh>

      {windows.map((item, index) => {
        const rise = riseFor(index);
        const builtHeight = item.magnitude * rise;
        const highlighted = index === important;
        const color = highlighted ? accent : secondaryColor;

        return (
          <group key={index} position={[item.x, baseline, 0]}>
            {item.layers.map((level, layer) => {
              const exposure = Math.max(
                0,
                Math.min(1, (builtHeight - level) / layerStep),
              );
              if (exposure <= 0) return null;

              const aboveComparison =
                highlighted && level >= secondaryHeight;

              return (
                <mesh
                  key={layer}
                  geometry={item.geometry}
                  position={[0, level, 0]}
                >
                  <meshStandardMaterial
                    color={color}
                    emissive={color}
                    emissiveIntensity={aboveComparison ? 0.8 : 0.32}
                    roughness={0.36}
                    metalness={0.1}
                    transparent
                    opacity={
                      exposure * (aboveComparison ? 0.84 : 0.56)
                    }
                    depthWrite={false}
                    side={THREE.DoubleSide}
                  />
                </mesh>
              );
            })}

            {/* The moving upper boundary settles at the exact data height. */}
            <mesh
              geometry={item.capGeometry}
              position={[0, builtHeight, 0]}
            >
              <meshStandardMaterial
                color={color}
                emissive={color}
                emissiveIntensity={0.85}
                transparent
                opacity={Math.min(1, rise * 8)}
                roughness={0.3}
              />
            </mesh>
          </group>
        );
      })}

      {/* A quiet open bracket isolates the excess, without another statistic. */}
      {count === 2 && difference > 0 && (
        <group position={[0, baseline + secondaryHeight, 0.6]}>
          <mesh
            geometry={ruleGeometry}
            position={[0, difference / 2, 0]}
            scale={[0.016, difference, 0.016]}
          >
            <meshBasicMaterial
              color={accent}
              transparent
              opacity={comparisonReveal * 0.75}
            />
          </mesh>
          {[0, difference].map((offset, index) => (
            <mesh
              key={index}
              geometry={ruleGeometry}
              position={[0, offset, 0]}
              scale={[pitch * 0.055, 0.016, 0.016]}
            >
              <meshBasicMaterial
                color={accent}
                transparent
                opacity={comparisonReveal * 0.85}
              />
            </mesh>
          ))}
        </group>
      )}
    </ChartStage>
  );
}