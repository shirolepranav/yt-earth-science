import React, { useMemo } from "react";
import { Easing, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import * as THREE from "three";
import {
  ChartStage,
  Label,
  formatValue,
  project,
} from "../components/charts/ChartStage";
import type { ChartProps } from "../types";

const STRATA = 26;
const HEIGHT = 5.7;
const DEPTH = 0.95;

const clamp = (n: number) => Math.max(0, Math.min(1, n));
const seed = (index: number) => {
  const n = Math.sin(index * 127.1 + 311.7) * 43758.5453;
  return n - Math.floor(n);
};

export default function Chart(props: ChartProps) {
  const frame = useCurrentFrame();
  const { width, height, durationInFrames } = useVideoConfig();
  const time = frame / Math.max(1, durationInFrames - 1);

  const camera = useMemo(
    () => ({
      position: [0, 3.4, 14] as [number, number, number],
      target: [0, 2.9, 0] as [number, number, number],
      fov: 40,
    }),
    [],
  );

  const numbers = props.values.map((value) => {
    const parsed = Number(String(value).replace(/[^0-9.-]/g, ""));
    return Number.isFinite(parsed) ? parsed : 0;
  });
  const maximum = Math.max(...numbers.map(Math.abs), 1e-9);
  const important = numbers.indexOf(Math.max(...numbers));
  const count = Math.max(1, numbers.length);

  const visibleWidth = 2 * Math.tan((camera.fov * Math.PI) / 360) * 14 * (width / height);
  const totalWidth = visibleWidth * 0.78;
  const gap = totalWidth * 0.052;
  const wallWidth = (totalWidth - gap * (count - 1)) / count;
  const layerHeight = HEIGHT / STRATA;

  // Each stratum is a chipped, extruded rock shelf, not a smooth chart bar.
  // Its top remains level: the final cap is an exact index-height datum.
  const geometry = useMemo(() => {
    const strata = Array.from({ length: STRATA }, (_, index) => {
      const left = seed(index * 7 + 1) * 0.018;
      const right = seed(index * 7 + 2) * 0.018;
      const chip = 0.006 + seed(index * 7 + 3) * 0.012;
      const shape = new THREE.Shape();

      shape.moveTo(-0.5 + left + chip, 0);
      shape.lineTo(0.5 - right - chip, 0);
      shape.lineTo(0.5 - right, 0.19);
      shape.lineTo(0.5 - right - chip * 0.3, 0.72);
      shape.lineTo(0.5 - right - chip, 1);
      shape.lineTo(-0.5 + left + chip, 1);
      shape.lineTo(-0.5 + left, 0.77);
      shape.lineTo(-0.5 + left + chip * 0.4, 0.24);
      shape.closePath();

      const result = new THREE.ExtrudeGeometry(shape, {
        depth: DEPTH,
        bevelEnabled: false,
        steps: 1,
        curveSegments: 1,
      });
      result.translate(0, 0, -DEPTH / 2);
      return result;
    });

    return { strata, box: new THREE.BoxGeometry(1, 1, 1) };
  }, []);

  const rockColors = useMemo(
    () =>
      Array.from({ length: STRATA }, (_, index) => {
        const color = new THREE.Color("#354858");
        color.multiplyScalar(0.68 + seed(index + 80) * 0.65);
        return color;
      }),
    [],
  );

  const columns = numbers.map((value, index) => {
    const stagger = count > 1 ? (index / (count - 1)) * 0.18 : 0;
    const progress = interpolate(
      time,
      [0.035 + stagger, 0.35 + stagger],
      [0, 1],
      {
        easing: Easing.inOut(Easing.cubic),
        extrapolateLeft: "clamp",
        extrapolateRight: "clamp",
      },
    );

    const targetHeight = (Math.abs(value) / maximum) * HEIGHT;
    return {
      value,
      index,
      x: -totalWidth / 2 + wallWidth / 2 + index * (wallWidth + gap),
      targetHeight,
      currentHeight: targetHeight * progress,
      progress,
      color: index === important ? props.brand.colors.accent : "#93AFC4",
    };
  });

  const comparisonOpacity = interpolate(time, [0.50, 0.57], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const overlay = (
    <>
      {columns.map((column) => {
        const position = project(
          camera,
          [column.x, 1.42, DEPTH / 2 + 0.08],
          width,
          height,
        );
        const opacity = interpolate(
          time,
          [0.075 + column.index * 0.10, 0.15 + column.index * 0.10],
          [0, 1],
          { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
        );
        const label = props.labels[column.index] ?? "";
        const labelSize = Math.min(
          height * 0.035,
          (width * 0.35) / Math.max(1, label.length * 0.56),
        );
        const cardWidth = (wallWidth / visibleWidth) * width * 0.9;

        return (
          <React.Fragment key={column.index}>
            <div
              style={{
                position: "absolute",
                left: position.x,
                top: position.y,
                width: cardWidth,
                height: height * 0.19,
                transform: "translate(-50%, -50%)",
                background:
                  "radial-gradient(ellipse, rgba(5,10,15,0.82) 0%, rgba(5,10,15,0.35) 55%, transparent 74%)",
                opacity,
                pointerEvents: "none",
              }}
            />
            <Label
              x={position.x}
              y={position.y - height * 0.031}
              size={height * 0.084}
              color={
                column.index === important
                  ? props.brand.colors.accent
                  : props.brand.colors.text
              }
              weight={650}
              opacity={opacity}
            >
              {formatValue(column.value, props.unit, props.values)}
            </Label>
            <Label
              x={position.x}
              y={position.y + height * 0.043}
              size={labelSize}
              color={props.brand.colors.text}
              weight={500}
              opacity={opacity}
            >
              {label}
            </Label>
          </React.Fragment>
        );
      })}
    </>
  );

  return (
    <ChartStage
      brand={props.brand}
      camera={camera}
      title={props.title}
      source={props.source}
      subtitle={props.unit.length > 2 ? `in ${props.unit}` : undefined}
      overlay={overlay}
    >
      {columns.map((column) => (
        <group key={column.index} position={[column.x, 0, 0]}>
          {geometry.strata.map((stratum, index) => {
            const bottom = index * layerHeight;
            const available = Math.min(
              layerHeight,
              column.targetHeight - bottom,
              column.currentHeight - bottom,
            );
            if (available <= 0.001) return null;

            const thickness = Math.max(0.001, available - 0.009);
            const isUpperRock = bottom > column.targetHeight * 0.78;

            return (
              <group key={index}>
                <mesh
                  geometry={stratum}
                  position={[0, bottom, 0]}
                  scale={[wallWidth, thickness, 1]}
                >
                  <meshStandardMaterial
                    color={rockColors[index]}
                    roughness={0.94}
                    metalness={0.06}
                    emissive={
                      column.index === important && isUpperRock
                        ? props.brand.colors.accent
                        : "#142737"
                    }
                    emissiveIntensity={isUpperRock ? 0.13 : 0.045}
                  />
                </mesh>

                <mesh
                  geometry={geometry.box}
                  position={[
                    0,
                    bottom + thickness - 0.006,
                    DEPTH / 2 + 0.004,
                  ]}
                  scale={[
                    wallWidth * (0.94 + seed(index + 200) * 0.025),
                    0.012,
                    0.009,
                  ]}
                >
                  <meshBasicMaterial
                    color={column.color}
                    transparent
                    opacity={0.10 + seed(index + 300) * 0.19}
                    depthWrite={false}
                  />
                </mesh>
              </group>
            );
          })}

          {/* A hot depositional front climbs the exposed geological section. */}
          {column.currentHeight > 0.01 ? (
            <>
              <mesh
                geometry={geometry.box}
                position={[0, column.currentHeight + 0.005, 0]}
                scale={[wallWidth * 0.962, 0.034, DEPTH * 1.02]}
              >
                <meshStandardMaterial
                  color={column.color}
                  emissive={column.color}
                  emissiveIntensity={0.9}
                  roughness={0.4}
                  metalness={0.15}
                />
              </mesh>
              <mesh
                geometry={geometry.box}
                position={[0, column.currentHeight - 0.021, DEPTH / 2 + 0.018]}
                scale={[wallWidth * 0.962, 0.075, 0.018]}
              >
                <meshBasicMaterial
                  color={column.color}
                  transparent
                  opacity={0.15}
                  depthWrite={false}
                />
              </mesh>
            </>
          ) : null}

          {column.index === important ? (
            <pointLight
              position={[0, column.currentHeight + 0.8, 1.3]}
              color={props.brand.colors.accent}
              intensity={14 * clamp(column.progress * 2)}
              distance={6}
            />
          ) : null}
        </group>
      ))}

      {/* The unexaggerated height difference is traced across the central rift. */}
      {columns.slice(0, -1).map((left, index) => {
        const right = columns[index + 1];
        if (!right) return null;

        const leftEdge = left.x + wallWidth * 0.481;
        const rightEdge = right.x - wallWidth * 0.481;
        const center = (leftEdge + rightEdge) / 2;
        const difference = Math.abs(right.targetHeight - left.targetHeight);

        return (
          <group key={index}>
            {[left, right].map((column, side) => {
              const edge = side === 0 ? leftEdge : rightEdge;
              return (
                <mesh
                  key={side}
                  geometry={geometry.box}
                  position={[(edge + center) / 2, column.targetHeight, DEPTH / 2]}
                  scale={[Math.abs(center - edge), 0.018, 0.018]}
                >
                  <meshBasicMaterial
                    color={column.color}
                    transparent
                    opacity={comparisonOpacity * 0.85}
                    depthWrite={false}
                  />
                </mesh>
              );
            })}
            <mesh
              geometry={geometry.box}
              position={[
                center,
                (left.targetHeight + right.targetHeight) / 2,
                DEPTH / 2,
              ]}
              scale={[0.018, Math.max(0.018, difference), 0.018]}
            >
              <meshBasicMaterial
                color={props.brand.colors.accent}
                transparent
                opacity={comparisonOpacity}
                depthWrite={false}
              />
            </mesh>
          </group>
        );
      })}
    </ChartStage>
  );
}