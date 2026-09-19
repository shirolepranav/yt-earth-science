import React, { useMemo } from "react";
import { useCurrentFrame, useVideoConfig } from "remotion";
import * as THREE from "three";
import { BODY } from "../fonts";
import {
  ChartStage,
  Label,
  formatValue,
  project,
} from "../components/charts/ChartStage";
import type { ChartProps } from "../types";

const TAU = Math.PI * 2;
const RADIUS = 2.3;
const MAX_HEIGHT = 4.8;

const clamp = (n: number) => Math.max(0, Math.min(1, n));
const smooth = (n: number) => {
  const t = clamp(n);
  return t * t * (3 - 2 * t);
};

/**
 * A passage is one complete sweep around a cylindrical Earth-like drum.
 * Every completed sweep leaves another equal-height layer behind:
 * the wave does not disappear at the horizon; it comes back.
 */
function Passage({
  x,
  bottom,
  height,
  progress,
  color,
  leading,
}: {
  x: number;
  bottom: number;
  height: number;
  progress: number;
  color: string;
  leading: boolean;
}) {
  const sweep = Math.max(0.0001, progress) * TAU;

  const geometries = useMemo(() => {
    const drum = new THREE.CylinderGeometry(
      RADIUS,
      RADIUS,
      Math.max(0.001, height - 0.025),
      96,
      1,
      false,
      0,
      sweep,
    );

    const points: THREE.Vector3[] = [];
    const steps = Math.max(4, Math.ceil((sweep / TAU) * 128));
    for (let j = 0; j <= steps; j++) {
      const angle = (j / steps) * sweep;
      points.push(
        new THREE.Vector3(
          Math.sin(angle) * (RADIUS + 0.012),
          0,
          Math.cos(angle) * (RADIUS + 0.012),
        ),
      );
    }
    const rim = new THREE.TubeGeometry(
      new THREE.CatmullRomCurve3(points),
      steps,
      0.022,
      6,
      false,
    );
    return { drum, rim };
  }, [height, sweep]);

  const markerGeometry = useMemo(
    () => new THREE.SphereGeometry(0.065, 12, 8),
    [],
  );

  if (progress <= 0) return null;

  return (
    <group position={[x, bottom, 0]}>
      <mesh
        geometry={geometries.drum}
        position={[0, height / 2, 0]}
      >
        <meshStandardMaterial
          color={color}
          emissive={color}
          emissiveIntensity={0.065}
          roughness={0.48}
          metalness={0.32}
        />
      </mesh>

      <mesh geometry={geometries.rim} position={[0, height, 0]}>
        <meshStandardMaterial
          color={color}
          emissive={color}
          emissiveIntensity={1.4}
          roughness={0.35}
          toneMapped={false}
        />
      </mesh>

      <mesh geometry={geometries.rim} position={[0, 0.015, 0]}>
        <meshStandardMaterial
          color={color}
          emissive={color}
          emissiveIntensity={0.35}
          roughness={0.5}
        />
      </mesh>

      {leading && progress < 1 ? (
        <mesh
          geometry={markerGeometry}
          position={[
            Math.sin(sweep) * (RADIUS + 0.025),
            height,
            Math.cos(sweep) * (RADIUS + 0.025),
          ]}
        >
          <meshBasicMaterial color={color} toneMapped={false} />
        </mesh>
      ) : null}
    </group>
  );
}

export default function Chart(props: ChartProps) {
  const frame = useCurrentFrame();
  const { width, height, durationInFrames } = useVideoConfig();
  const time = frame / Math.max(1, durationInFrames - 1);

  const numbers = props.values.map((value) => {
    const parsed = Number(String(value).replace(/[^0-9.-]/g, ""));
    return Number.isFinite(parsed) ? parsed : 0;
  });
  const maximum = Math.max(0.0001, ...numbers.map(Math.abs));
  const highlight = numbers.indexOf(Math.max(...numbers));
  const total = Math.max(
    0.0001,
    numbers.reduce((sum, value) => sum + Math.abs(value), 0),
  );

  // Freeze the camera before the reading hold. The slight descent lets the
  // stacked circumferences resolve into an unmistakable pair of bars.
  const cameraMove = smooth(time / 0.56);
  const aspect = width / height;
  const viewHeight = Math.max(7.95, 12.2 / aspect);
  const distance = viewHeight / (2 * Math.tan(THREE.MathUtils.degToRad(17)));

  const camera = {
    position: [
      -0.22 * (1 - cameraMove),
      3.8 - cameraMove * 0.2,
      distance,
    ] as [number, number, number],
    target: [0, 3.0, 0] as [number, number, number],
    fov: 34,
  };

  const unitHeight = MAX_HEIGHT / maximum;
  const spacing = 6.0;
  const scale = height / 1080;
  const build = clamp((time - 0.065) / 0.475);
  const labelOpacity = smooth((time - 0.035) / 0.065);

  const baseGeometry = useMemo(
    () => new THREE.CylinderGeometry(RADIUS + 0.13, RADIUS + 0.18, 0.1, 96),
    [],
  );

  const meridianGeometry = useMemo(() => {
    const vertices: number[] = [];
    // Hairline radial engraving on each finished cap: no map or asset needed.
    for (let i = 0; i < 12; i++) {
      const a = (i / 12) * TAU;
      vertices.push(
        Math.sin(a) * 0.2,
        0,
        Math.cos(a) * 0.2,
        Math.sin(a) * (RADIUS - 0.07),
        0,
        Math.cos(a) * (RADIUS - 0.07),
      );
    }
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute(
      "position",
      new THREE.Float32BufferAttribute(vertices, 3),
    );
    return geometry;
  }, []);

  let preceding = 0;
  const bars = numbers.map((value, index) => {
    const magnitude = Math.abs(value);
    const start = preceding;
    preceding += magnitude;

    // A bounded number of layers keeps the scene light if props are replaced.
    // For the supplied passage data, each layer is exactly one passage.
    const count = Math.min(64, Math.max(1, Math.ceil(magnitude)));
    const layers = Array.from({ length: count }, (_, layer) => {
      const from = (layer / count) * magnitude;
      const to = ((layer + 1) / count) * magnitude;
      const extent = to - from;
      return {
        bottom: from * unitHeight,
        height: extent * unitHeight,
        progress: clamp(
          (build * total - start - from) / Math.max(0.0001, extent),
        ),
      };
    });

    const finishTime = 0.065 + ((start + magnitude) / total) * 0.475;
    return {
      value,
      x: (index - (numbers.length - 1) / 2) * spacing,
      height: magnitude * unitHeight,
      color: index === highlight ? props.brand.colors.accent : "#728BA3",
      layers,
      numberOpacity: smooth((time - finishTime) / 0.035),
    };
  });

  return (
    <ChartStage
      brand={props.brand}
      camera={camera}
      title={props.title}
      source={props.source}
      subtitle={props.unit.length > 2 ? `in ${props.unit}` : undefined}
      overlay={
        <>
          {bars.map((bar, index) => {
            const valuePoint = project(
              camera,
              [bar.x, Math.max(0.6, bar.height * 0.48), RADIUS + 0.15],
              width,
              height,
            );
            const labelPoint = project(
              camera,
              [bar.x, -0.33, 0],
              width,
              height,
            );

            return (
              <React.Fragment key={index}>
                <Label
                  x={valuePoint.x}
                  y={valuePoint.y}
                  size={106 * scale}
                  color={
                    index === highlight
                      ? props.brand.colors.accent
                      : props.brand.colors.text
                  }
                  weight={700}
                  opacity={bar.numberOpacity}
                >
                  <span
                    style={{
                      display: "inline-block",
                      minWidth: 125 * scale,
                      textAlign: "center",
                      padding: `${5 * scale}px ${24 * scale}px`,
                      borderRadius: 12 * scale,
                      background: "rgba(5, 10, 17, 0.88)",
                      lineHeight: 1.1,
                      fontVariantNumeric: "tabular-nums",
                    }}
                  >
                    {formatValue(bar.value, props.unit, props.values)}
                  </span>
                </Label>
                <Label
                  x={labelPoint.x}
                  y={labelPoint.y}
                  size={36 * scale}
                  color={props.brand.colors.text}
                  font={BODY}
                  weight={600}
                  opacity={labelOpacity}
                >
                  {props.labels[index] ?? ""}
                </Label>
              </React.Fragment>
            );
          })}
        </>
      }
    >
      {bars.map((bar, index) => (
        <group key={index}>
          <mesh
            geometry={baseGeometry}
            position={[bar.x, 0.01, 0]}
          >
            <meshStandardMaterial
              color="#253344"
              metalness={0.5}
              roughness={0.6}
            />
          </mesh>

          {bar.layers.map((layer, layerIndex) => (
            <Passage
              key={layerIndex}
              x={bar.x}
              bottom={layer.bottom + 0.065}
              height={layer.height}
              progress={layer.progress}
              color={bar.color}
              leading
            />
          ))}

          {bar.layers.map((layer, layerIndex) =>
            layer.progress >= 1 ? (
              <lineSegments
                key={layerIndex}
                geometry={meridianGeometry}
                position={[
                  bar.x,
                  layer.bottom + layer.height + 0.066,
                  0,
                ]}
              >
                <lineBasicMaterial
                  color={bar.color}
                  transparent
                  opacity={0.3}
                />
              </lineSegments>
            ) : null,
          )}
        </group>
      ))}
    </ChartStage>
  );
}