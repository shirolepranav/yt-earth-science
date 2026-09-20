import React, { useMemo } from "react";
import { Easing, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import * as THREE from "three";
import {
  ChartStage,
  formatValue,
  project,
} from "../components/charts/ChartStage";
import type { Camera } from "../components/charts/ChartStage";
import { BODY, DISPLAY } from "../fonts";
import type { ChartProps } from "../types";

const clamp = {
  extrapolateLeft: "clamp",
  extrapolateRight: "clamp",
} as const;

export default function Chart(props: ChartProps) {
  const frame = useCurrentFrame();
  const { width, height, durationInFrames } = useVideoConfig();
  const scale = Math.min(width / 1920, height / 1080);
  const progress = frame / Math.max(1, durationInFrames - 1);

  const values = props.values.map((v) => {
    const parsed = Number(String(v).replace(/[^0-9.-]/g, ""));
    return Number.isFinite(parsed) ? parsed : 0;
  });
  const maximum = Math.max(...values.map(Math.abs), 1e-9);
  const primary = values.indexOf(Math.max(...values));
  const reference = Math.min(...values.filter((v) => v > 0), maximum);

  // Equal curved footprints: the enclosed water volumes scale linearly with
  // the supplied quantities. Horizontal seams repeat the smaller quantity.
  const fullHeight = 5.15;
  const viewHeight = fullHeight / 0.535;
  const aspect = width / height;
  const gap = viewHeight * aspect * 0.07;
  const sheetWidth =
    (viewHeight * aspect * 0.78 - gap * Math.max(0, values.length - 1)) /
    Math.max(1, values.length);
  const depth = 0.82;

  const dolly = interpolate(progress, [0, 0.58], [1.035, 1], {
    ...clamp,
    easing: Easing.out(Easing.cubic),
  });
  const camera: Camera = {
    position: [
      0,
      3.2,
      (viewHeight / (2 * Math.tan(THREE.MathUtils.degToRad(20)))) * dolly,
    ],
    target: [0, 3.2, 0],
    fov: 40,
  };

  const geometry = useMemo(() => {
    const subdivisions = 40;
    const bow = (x: number) =>
      0.34 * Math.pow(x / Math.max(sheetWidth / 2, 0.001), 2);

    const positions: number[] = [];
    const indices: number[] = [];
    const perimeter: number[] = [];
    const silhouette: number[] = [];

    const segment = (
      destination: number[],
      a: [number, number, number],
      b: [number, number, number],
    ) => destination.push(...a, ...b);

    for (let i = 0; i <= subdivisions; i++) {
      const x = -sheetWidth / 2 + (i / subdivisions) * sheetWidth;
      const z = bow(x);
      positions.push(
        x, 0, z - depth / 2,
        x, 0, z + depth / 2,
        x, 1, z - depth / 2,
        x, 1, z + depth / 2,
      );

      if (i < subdivisions) {
        const a = i * 4;
        const b = a + 4;
        indices.push(
          a, b, a + 2, b, b + 2, a + 2,
          a + 1, a + 3, b + 1, b + 1, a + 3, b + 3,
          a + 2, b + 2, a + 3, b + 2, b + 3, a + 3,
          a, a + 1, b, b, a + 1, b + 1,
        );

        const nextX = x + sheetWidth / subdivisions;
        const nextZ = bow(nextX);
        for (const side of [-1, 1]) {
          segment(
            perimeter,
            [x, 0, z + side * depth / 2],
            [nextX, 0, nextZ + side * depth / 2],
          );
          for (const y of [0, 1]) {
            segment(
              silhouette,
              [x, y, z + side * depth / 2],
              [nextX, y, nextZ + side * depth / 2],
            );
          }
        }
      }
    }

    const end = subdivisions * 4;
    indices.push(0, 2, 1, 1, 2, 3);
    indices.push(end, end + 1, end + 2, end + 1, end + 3, end + 2);

    for (const x of [-sheetWidth / 2, sheetWidth / 2]) {
      const z = bow(x);
      segment(perimeter, [x, 0, z - depth / 2], [x, 0, z + depth / 2]);
      for (const y of [0, 1]) {
        segment(
          silhouette,
          [x, y, z - depth / 2],
          [x, y, z + depth / 2],
        );
      }
      for (const side of [-1, 1]) {
        segment(
          silhouette,
          [x, 0, z + side * depth / 2],
          [x, 1, z + side * depth / 2],
        );
      }
    }

    const volume = new THREE.BufferGeometry();
    volume.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
    volume.setIndex(indices);
    volume.computeVertexNormals();

    const makeLines = (points: number[]) => {
      const result = new THREE.BufferGeometry();
      result.setAttribute("position", new THREE.Float32BufferAttribute(points, 3));
      const temporary = new THREE.LineSegments(result);
      temporary.computeLineDistances();
      return result;
    };

    return {
      volume,
      perimeter: makeLines(perimeter),
      silhouette: makeLines(silhouette),
    };
  }, [sheetWidth]);

  const caveat = props.source
    .split(/\s+[—–]\s+/)
    .slice(1)
    .join(" — ");

  const entries = values.map((value, index) => {
    const important = index === primary;
    const x =
      (index - (values.length - 1) / 2) * (sheetWidth + gap);
    const finalHeight = (Math.abs(value) / maximum) * fullHeight;
    const rise = interpolate(
      progress,
      important ? [0.035, 0.48] : [0.06, 0.29],
      [0, 1],
      { ...clamp, easing: Easing.inOut(Easing.cubic) },
    );
    return {
      value,
      index,
      important,
      x,
      finalHeight,
      currentHeight: Math.max(0.001, finalHeight * rise),
      rise,
      color: important ? props.brand.colors.accent : "#8CA9BF",
    };
  });

  const textOpacity = interpolate(progress, [0.08, 0.19], [0, 1], clamp);
  const caveatOpacity = interpolate(progress, [0.43, 0.57], [0, 1], clamp);

  return (
    <ChartStage
      brand={props.brand}
      camera={camera}
      title={props.title}
      source={props.source}
      subtitle={props.unit.length > 2 ? `in ${props.unit}` : undefined}
      overlay={
        <>
          {entries.map((entry) => {
            const anchor = project(
              camera,
              [
                entry.x,
                entry.important
                  ? entry.finalHeight - 0.75
                  : entry.finalHeight + 1.62,
                depth / 2 + 0.45,
              ],
              width,
              height,
            );

            const label = props.labels[entry.index] ?? "";
            const qualificationStart = label.indexOf("(");
            const labelMain =
              qualificationStart < 0 ? label : label.slice(0, qualificationStart);
            const qualification =
              qualificationStart < 0 ? "" : label.slice(qualificationStart);

            return (
              <React.Fragment key={entry.index}>
                <div
                  style={{
                    position: "absolute",
                    left: anchor.x,
                    top: anchor.y,
                    transform: "translateX(-50%)",
                    width: width * 0.34,
                    textAlign: "center",
                    opacity: textOpacity,
                    textShadow: "0 3px 24px rgba(0,0,0,0.95)",
                    pointerEvents: "none",
                  }}
                >
                  <div
                    style={{
                      fontFamily: DISPLAY,
                      fontWeight: 600,
                      fontSize: 102 * scale,
                      lineHeight: 1,
                      letterSpacing: -3 * scale,
                      color: entry.important
                        ? props.brand.colors.accent
                        : props.brand.colors.text,
                      fontVariantNumeric: "tabular-nums",
                    }}
                  >
                    {formatValue(entry.value, props.unit, props.values)}
                  </div>
                  <div
                    style={{
                      marginTop: 15 * scale,
                      fontFamily: BODY,
                      fontSize: 36 * scale,
                      fontWeight: 600,
                      lineHeight: 1.15,
                      color: props.brand.colors.text,
                    }}
                  >
                    {labelMain}
                  </div>
                  {qualification ? (
                    <div
                      style={{
                        fontFamily: BODY,
                        fontSize: 32 * scale,
                        lineHeight: 1.25,
                        marginTop: 5 * scale,
                        color: "#B4C9D9",
                      }}
                    >
                      {qualification}
                    </div>
                  ) : null}
                </div>

                {!entry.important && caveat ? (
                  <div
                    style={{
                      position: "absolute",
                      left: anchor.x,
                      top: height * 0.335,
                      transform: "translateX(-50%)",
                      width: width * 0.29,
                      boxSizing: "border-box",
                      borderLeft: `${3 * scale}px dashed #8CA9BF`,
                      paddingLeft: 22 * scale,
                      color: props.brand.colors.text,
                      fontFamily: BODY,
                      fontSize: 31 * scale,
                      lineHeight: 1.35,
                      opacity: caveatOpacity,
                      textShadow: "0 2px 14px rgba(0,0,0,0.9)",
                    }}
                  >
                    {caveat}
                  </div>
                ) : null}
              </React.Fragment>
            );
          })}
        </>
      }
    >
      {entries.map((entry) => {
        const referenceHeight = (reference / maximum) * fullHeight;
        const divisions = Math.min(
          20,
          Math.max(0, Math.ceil(entry.finalHeight / referenceHeight) - 1),
        );
        const laminae = entry.important ? 66 : 17;

        return (
          <group key={entry.index} position={[entry.x, 0, 0]}>
            {/* A suspended, curved atmospheric reservoir rather than a solid bar. */}
            <mesh
              geometry={geometry.volume}
              scale={[1, entry.currentHeight, 1]}
              renderOrder={1}
            >
              <meshStandardMaterial
                color={entry.color}
                emissive={entry.color}
                emissiveIntensity={entry.important ? 0.3 : 0.08}
                transparent
                opacity={entry.important ? 0.23 : 0.045}
                roughness={0.3}
                metalness={0.15}
                depthWrite={false}
                side={THREE.DoubleSide}
              />
            </mesh>

            {Array.from({ length: laminae }, (_, i) => {
              const fraction = (i + 1) / laminae;
              return (
                <lineSegments
                  key={`lamina-${i}`}
                  geometry={geometry.perimeter}
                  position={[0, fraction * entry.currentHeight, 0]}
                  renderOrder={2}
                >
                  {entry.important ? (
                    <lineBasicMaterial
                      color={entry.color}
                      transparent
                      opacity={0.16 + 0.18 * fraction}
                      depthWrite={false}
                    />
                  ) : (
                    <lineDashedMaterial
                      color={entry.color}
                      transparent
                      opacity={0.38}
                      dashSize={0.11}
                      gapSize={0.095}
                      depthWrite={false}
                    />
                  )}
                </lineSegments>
              );
            })}

            <lineSegments
              geometry={geometry.silhouette}
              scale={[1, entry.currentHeight, 1]}
              renderOrder={3}
            >
              {entry.important ? (
                <lineBasicMaterial
                  color={entry.color}
                  transparent
                  opacity={0.8}
                  depthWrite={false}
                />
              ) : (
                <lineDashedMaterial
                  color={entry.color}
                  dashSize={0.13}
                  gapSize={0.09}
                  transparent
                  opacity={0.9}
                  depthWrite={false}
                />
              )}
            </lineSegments>

            {/* Each strong seam is one smaller-reservoir height:
                almost four repeats are visible, without inventing another label. */}
            {entry.important
              ? Array.from({ length: divisions }, (_, i) => {
                  const y = (i + 1) * referenceHeight;
                  const revealed = Math.min(
                    1,
                    Math.max(0, (entry.currentHeight - y) / 0.18),
                  );
                  return (
                    <lineSegments
                      key={`reference-${i}`}
                      geometry={geometry.perimeter}
                      position={[0, y, 0.015]}
                      renderOrder={4}
                    >
                      <lineBasicMaterial
                        color={props.brand.colors.accent}
                        transparent
                        opacity={revealed * 0.95}
                        depthWrite={false}
                      />
                    </lineSegments>
                  );
                })
              : null}

            <lineSegments
              geometry={geometry.perimeter}
              position={[0, 0.012, 0]}
            >
              <lineBasicMaterial
                color={entry.color}
                transparent
                opacity={0.55}
              />
            </lineSegments>
          </group>
        );
      })}
    </ChartStage>
  );
}