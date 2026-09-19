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
  extrapolateLeft: "clamp" as const,
  extrapolateRight: "clamp" as const,
};

function graticule(dashed: boolean): THREE.BufferGeometry {
  const positions: number[] = [];

  const append = (
    point: (t: number) => [number, number, number],
    subdivisions: number,
  ) => {
    for (let j = 0; j < subdivisions; j++) {
      if (dashed && j % 6 >= 3) continue;
      positions.push(
        ...point((j / subdivisions) * Math.PI * 2),
        ...point(((j + 1) / subdivisions) * Math.PI * 2),
      );
    }
  };

  for (let latitude = 1; latitude < 16; latitude++) {
    const phi = -Math.PI / 2 + (latitude / 16) * Math.PI;
    append(
      (theta) => [
        Math.cos(phi) * Math.cos(theta),
        Math.sin(phi),
        Math.cos(phi) * Math.sin(theta),
      ],
      144,
    );
  }

  for (let meridian = 0; meridian < 8; meridian++) {
    const angle = (meridian / 8) * Math.PI;
    append(
      (theta) => [
        Math.cos(theta) * Math.cos(angle),
        Math.sin(theta),
        Math.cos(theta) * Math.sin(angle),
      ],
      144,
    );
  }

  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute(
    "position",
    new THREE.Float32BufferAttribute(positions, 3),
  );
  return geometry;
}

export default function Chart(props: ChartProps) {
  const frame = useCurrentFrame();
  const { width, height, durationInFrames } = useVideoConfig();
  const time = frame / Math.max(1, durationInFrames - 1);
  const scale = height / 1080;
  const viewHeight = 10.8;
  const viewWidth = viewHeight * (width / height);
  const distance = 12;
  const targetY = 4.1;

  // A locked, near-frontal composition makes the volume comparison trustworthy.
  const camera = useMemo<Camera>(
    () => ({
      position: [0, targetY, distance],
      target: [0, targetY, 0],
      fov: THREE.MathUtils.radToDeg(
        2 * Math.atan(viewHeight / (2 * distance)),
      ),
    }),
    [],
  );

  const numbers = props.values.map((value) => {
    const parsed = Number(String(value).replace(/[^0-9.-]/g, ""));
    return Number.isFinite(parsed) ? parsed : 0;
  });
  const maximum = Math.max(...numbers.map(Math.abs), 1e-9);
  const highlight = numbers.findIndex((value) => Math.abs(value) === maximum);

  const geometry = useMemo(() => {
    const atmospherePositions: number[] = [];
    for (let layer = 0; layer < 8; layer++) {
      for (let segment = 0; segment < 100; segment++) {
        const point = (step: number): [number, number, number] => {
          const x = (step / 100 - 0.5) * viewWidth * 1.15;
          return [
            x,
            0.85 + layer * 0.7 - 0.011 * x * x,
            -3.2,
          ];
        };
        atmospherePositions.push(...point(segment), ...point(segment + 1));
      }
    }

    const atmosphere = new THREE.BufferGeometry();
    atmosphere.setAttribute(
      "position",
      new THREE.Float32BufferAttribute(atmospherePositions, 3),
    );

    return {
      sphere: new THREE.SphereGeometry(1, 64, 48),
      continuous: graticule(false),
      dashed: graticule(true),
      atmosphere,
    };
  }, [viewWidth]);

  const reservoirs = numbers.map((value, index) => {
    const important = index === highlight;
    const fraction =
      numbers.length <= 1 ? 0.5 : 0.28 + (index / (numbers.length - 1)) * 0.46;

    const fill = interpolate(
      time,
      important ? [0.025, 0.35] : [0.16, 0.52],
      [0, 1],
      { ...clamp, easing: Easing.inOut(Easing.cubic) },
    );

    // Identical spherical envelopes: V ∝ r³, not r or projected area.
    const finalRadius = viewHeight * 0.27 * Math.cbrt(Math.abs(value) / maximum);
    const radius = finalRadius * Math.cbrt(fill);
    const x = (fraction - 0.5) * viewWidth;
    const y = targetY - viewHeight * 0.055;

    // Account for perspective displacement of an off-axis sphere's silhouette.
    const perspectiveCorrection =
      1 / (1 - (finalRadius * finalRadius) / (distance * distance));
    const labelPoint = project(
      camera,
      [
        x * perspectiveCorrection,
        targetY + (y - targetY) * perspectiveCorrection,
        0,
      ],
      width,
      height,
    );

    const label = props.labels[index] ?? "";
    const qualifier = label.match(/\s*(\([^)]*\))\s*$/);
    const name = qualifier
      ? label.slice(0, qualifier.index).trim()
      : label;

    return {
      value,
      important,
      fill,
      radius,
      finalRadius,
      x,
      y,
      labelPoint,
      name,
      qualifier: qualifier?.[1],
      color: important ? props.brand.colors.accent : "#8DA6BE",
    };
  });

  const labelOpacity = interpolate(time, [0.035, 0.115], [0, 1], clamp);
  const evidenceEmphasis = interpolate(time, [0.42, 0.56], [0, 1], clamp);

  return (
    <ChartStage
      brand={props.brand}
      camera={camera}
      title={props.title}
      source={props.source}
      subtitle={props.unit.length > 2 ? `in ${props.unit}` : undefined}
      overlay={
        <>
          {reservoirs.map((reservoir, index) => {
            const labelY = height * 0.857;
            const projectedBottom = project(
              camera,
              [reservoir.x, reservoir.y - reservoir.finalRadius, 0],
              width,
              height,
            );
            const leaderTop = Math.min(
              labelY - 18 * scale,
              projectedBottom.y + 18 * scale,
            );

            return (
              <React.Fragment key={index}>
                <div
                  style={{
                    position: "absolute",
                    left: reservoir.labelPoint.x,
                    top: reservoir.labelPoint.y,
                    transform: "translate(-50%, -50%)",
                    opacity: labelOpacity,
                    textAlign: "center",
                    color: reservoir.important
                      ? props.brand.colors.text
                      : "#D7E3EF",
                    fontFamily: DISPLAY,
                    fontWeight: 600,
                    fontVariantNumeric: "tabular-nums",
                    fontSize: (reservoir.important ? 122 : 108) * scale,
                    lineHeight: 1,
                    letterSpacing: -3 * scale,
                    whiteSpace: "nowrap",
                    textShadow: "0 3px 25px rgba(0,0,0,0.9)",
                  }}
                >
                  {formatValue(reservoir.value, props.unit, props.values)}
                  <div
                    style={{
                      width: 90 * scale,
                      margin: `${19 * scale}px auto 0`,
                      borderTop: `${2 * scale}px ${
                        reservoir.important ? "solid" : "dashed"
                      } ${reservoir.color}`,
                      opacity: 0.9,
                    }}
                  />
                </div>

                <div
                  style={{
                    position: "absolute",
                    left: reservoir.labelPoint.x,
                    top: leaderTop,
                    height: Math.max(0, labelY - 20 * scale - leaderTop),
                    borderLeft: `${scale}px ${
                      reservoir.important ? "solid" : "dashed"
                    } ${reservoir.color}`,
                    opacity: labelOpacity * 0.45,
                  }}
                />

                <div
                  style={{
                    position: "absolute",
                    left: reservoir.labelPoint.x,
                    top: labelY,
                    transform: "translateX(-50%)",
                    width: width * 0.39,
                    textAlign: "center",
                    opacity: labelOpacity,
                    fontFamily: BODY,
                    color: props.brand.colors.text,
                    textShadow: "0 2px 15px rgba(0,0,0,0.95)",
                  }}
                >
                  <div
                    style={{
                      fontSize: 40 * scale,
                      fontWeight: 600,
                      lineHeight: 1.12,
                    }}
                  >
                    {reservoir.name}
                  </div>
                  {reservoir.qualifier ? (
                    <div
                      style={{
                        display: "inline-block",
                        marginTop: 10 * scale,
                        padding: `${3 * scale}px ${14 * scale}px`,
                        fontSize: 31 * scale,
                        lineHeight: 1.1,
                        color: "#B7CADB",
                        borderBottom: `${2 * scale}px dashed rgba(141,166,190,${
                          0.25 + evidenceEmphasis * 0.65
                        })`,
                        backgroundColor: `rgba(75,101,128,${
                          evidenceEmphasis * 0.16
                        })`,
                      }}
                    >
                      {reservoir.qualifier}
                    </div>
                  ) : null}
                </div>
              </React.Fragment>
            );
          })}
        </>
      }
    >
      {/* Atmospheric laminations, not an axis or an additional data series. */}
      <lineSegments geometry={geometry.atmosphere}>
        <lineBasicMaterial
          color="#61788F"
          transparent
          opacity={0.17}
          depthWrite={false}
        />
      </lineSegments>

      {reservoirs.map((reservoir, index) => {
        const visibleRadius = Math.max(0.00001, reservoir.radius);
        return (
          <group
            key={index}
            position={[reservoir.x, reservoir.y, 0]}
            scale={visibleRadius}
            visible={reservoir.fill > 0}
          >
            {/* Continuous water body versus an explicitly dashed model envelope. */}
            <mesh geometry={geometry.sphere}>
              <meshPhysicalMaterial
                color={reservoir.important ? reservoir.color : "#26394B"}
                emissive={reservoir.color}
                emissiveIntensity={reservoir.important ? 0.23 : 0.09}
                roughness={reservoir.important ? 0.24 : 0.65}
                metalness={reservoir.important ? 0.24 : 0.05}
                clearcoat={reservoir.important ? 1 : 0}
                clearcoatRoughness={0.17}
                transparent={!reservoir.important}
                opacity={reservoir.important ? 1 : 0.16}
                depthWrite
              />
            </mesh>

            <lineSegments
              geometry={
                reservoir.important ? geometry.continuous : geometry.dashed
              }
              scale={1.004}
              renderOrder={2}
            >
              <lineBasicMaterial
                color={reservoir.important ? "#E1F3F5" : reservoir.color}
                transparent
                opacity={reservoir.important ? 0.2 : 0.72}
                depthWrite={false}
              />
            </lineSegments>
          </group>
        );
      })}

      {reservoirs
        .filter((reservoir) => reservoir.important)
        .map((reservoir, index) => (
          <pointLight
            key={index}
            position={[
              reservoir.x - reservoir.finalRadius * 0.7,
              reservoir.y + reservoir.finalRadius * 0.9,
              reservoir.finalRadius + 1.3,
            ]}
            color={props.brand.colors.accent}
            intensity={36}
            distance={10}
            decay={2}
          />
        ))}
    </ChartStage>
  );
}