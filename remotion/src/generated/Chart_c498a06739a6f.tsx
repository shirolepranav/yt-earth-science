import React, { useMemo } from "react";
import { Easing, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import * as THREE from "three";
import {
  ChartStage,
  Label,
  formatValue,
  project,
} from "../components/charts/ChartStage";
import { BODY } from "../fonts";
import type { ChartProps } from "../types";

const LAYERS = 24;
const ROCK_HEIGHT = 5.65;

const clamp = (n: number) => Math.max(0, Math.min(1, n));
const seeded = (n: number) => {
  const x = Math.sin(n * 127.1 + 311.7) * 43758.5453;
  return x - Math.floor(x);
};

/**
 * A horizontal slice of fractured volcanic rock.
 * The upper and lower faces are planar: the silhouette preserves the data,
 * while the chipped perimeter supplies the geological character.
 */
function makeStratum(index: number): THREE.BufferGeometry {
  const points: Array<[number, number]> = [
    [-0.5, -0.44],
    [-0.29, -0.5],
    [0.22, -0.48],
    [0.48, -0.39],
    [0.5, 0.28],
    [0.44, 0.47],
    [0.19, 0.51],
    [-0.08, 0.47],
    [-0.34, 0.51],
    [-0.5, 0.35],
  ];

  const perimeter = points.map(([x, z], j): [number, number] => [
    x + (seeded(index * 31 + j) - 0.5) * 0.025,
    z + (seeded(index * 47 + j + 90) - 0.5) * 0.065,
  ]);

  const vertices: number[] = [];
  const triangle = (
    a: [number, number, number],
    b: [number, number, number],
    c: [number, number, number],
  ) => vertices.push(...a, ...b, ...c);

  perimeter.forEach(([x, z], j) => {
    const [nx, nz] = perimeter[(j + 1) % perimeter.length];
    triangle([0, 1, 0], [nx, 1, nz], [x, 1, z]);
    triangle([0, 0, 0], [x, 0, z], [nx, 0, nz]);
    triangle([x, 0, z], [x, 1, z], [nx, 1, nz]);
    triangle([x, 0, z], [nx, 1, nz], [nx, 0, nz]);
  });

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
  const time = frame / Math.max(1, durationInFrames - 1);
  const screenScale = height / 1080;

  const numbers = props.values.map((value) => {
    const parsed = Number(String(value).replace(/[^0-9.-]/g, ""));
    return Number.isFinite(parsed) ? parsed : 0;
  });
  const maximum = Math.max(...numbers.map(Math.abs), 1e-9);
  const highlight = numbers.indexOf(Math.max(...numbers));
  const count = Math.max(1, numbers.length);

  // A very shallow dolly settles before the reading hold.
  const dolly = interpolate(time, [0, 0.56], [0, 1], {
    easing: Easing.inOut(Easing.cubic),
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const camera: {
    position: [number, number, number];
    target: [number, number, number];
    fov: number;
  } = {
    position: [0.22 - dolly * 0.12, 4.25, 13.8 - dolly * 0.4],
    target: [0, 2.8, 0],
    fov: 40,
  };

  const geometry = useMemo(
    () => ({
      strata: Array.from({ length: LAYERS }, (_, i) => makeStratum(i)),
      cap: makeStratum(101),
      box: new THREE.BoxGeometry(1, 1, 1),
    }),
    [],
  );

  const stoneColors = useMemo(
    () =>
      Array.from({ length: LAYERS }, (_, i) =>
        new THREE.Color("#263442").lerp(
          new THREE.Color("#657787"),
          0.13 + seeded(i + 71) * 0.37,
        ),
      ),
    [],
  );

  // Broad, adjacent sections from one imagined caldera wall.
  // Heights share a zero baseline; the small difference is not exaggerated.
  const aspect = width / height;
  const totalWidth = Math.min(13.25, aspect * 7.55);
  const gap = totalWidth * 0.065;
  const slabWidth = (totalWidth - gap * (count - 1)) / count;
  const depth = 1.65;

  const sections = numbers.map((value, index) => {
    const start = count === 1 ? 0.035 : 0.035 + (index / (count - 1)) * 0.215;
    const end = start + 0.295;
    return {
      value,
      x: (index - (count - 1) / 2) * (slabWidth + gap),
      height: (Math.abs(value) / maximum) * ROCK_HEIGHT,
      build: clamp((time - start) / (end - start)),
      labelOpacity: interpolate(time, [start + 0.055, start + 0.125], [0, 1], {
        extrapolateLeft: "clamp",
        extrapolateRight: "clamp",
      }),
      color: index === highlight ? props.brand.colors.accent : "#9DB1C4",
    };
  });

  const connectionOpacity = interpolate(time, [0.545, 0.585], [0, 0.85], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <ChartStage
      brand={props.brand}
      camera={camera}
      title={props.title}
      subtitle={props.unit.length > 2 ? `in ${props.unit}` : undefined}
      source={props.source}
      overlay={
        <>
          {sections.map((section, index) => {
            const anchor = project(
              camera,
              [section.x, 1.5, depth * 0.56],
              width,
              height,
            );
            const panelWidth = Math.min(
              width / count - 30 * screenScale,
              610 * screenScale,
            );

            return (
              <React.Fragment key={index}>
                <div
                  style={{
                    position: "absolute",
                    left: anchor.x,
                    top: anchor.y,
                    transform: "translate(-50%, -50%)",
                    width: panelWidth,
                    height: 218 * screenScale,
                    opacity: section.labelOpacity,
                    background:
                      "linear-gradient(180deg, rgba(5,9,14,0), rgba(5,9,14,0.87) 35%, rgba(5,9,14,0.88) 75%, rgba(5,9,14,0))",
                    pointerEvents: "none",
                  }}
                />
                <Label
                  x={anchor.x}
                  y={anchor.y - 28 * screenScale}
                  size={108 * screenScale}
                  color={
                    index === highlight
                      ? props.brand.colors.accent
                      : props.brand.colors.text
                  }
                  weight={600}
                  opacity={section.labelOpacity}
                >
                  {formatValue(section.value, props.unit, props.values)}
                </Label>
                <Label
                  x={anchor.x}
                  y={anchor.y + 57 * screenScale}
                  size={44 * screenScale}
                  color={props.brand.colors.text}
                  font={BODY}
                  weight={500}
                  opacity={section.labelOpacity}
                >
                  {props.labels[index] ?? ""}
                </Label>
              </React.Fragment>
            );
          })}
        </>
      }
    >
      {sections.map((section, index) => {
        const layerHeight = section.height / LAYERS;
        const capReveal = clamp((section.build - 0.9) / 0.1);

        return (
          <group key={index} position={[section.x, 0, 0]}>
            {geometry.strata.map((stratum, layer) => {
              // Successive beds resolve upward, like a geological exposure
              // being uncovered. No oscillation or motion remains in the hold.
              const progress = clamp(
                (section.build - (layer / LAYERS) * 0.76) / 0.24,
              );
              const reveal = 1 - Math.pow(1 - progress, 3);
              const thickness = layerHeight * 0.965 * reveal;
              const y = layer * layerHeight;
              const seam = layer % 4 === 3;
              const tint =
                index === highlight && seam
                  ? props.brand.colors.accent
                  : "#647D92";

              return (
                <group key={layer} visible={reveal > 0}>
                  <mesh
                    geometry={stratum}
                    position={[0, y, 0]}
                    scale={[slabWidth, Math.max(0.0001, thickness), depth]}
                  >
                    <meshStandardMaterial
                      color={stoneColors[layer]}
                      roughness={0.96}
                      metalness={0.04}
                      flatShading
                    />
                  </mesh>
                  {seam ? (
                    <mesh
                      geometry={stratum}
                      position={[0, y + thickness, 0]}
                      scale={[
                        slabWidth,
                        Math.max(0.0001, layerHeight * 0.027 * reveal),
                        depth,
                      ]}
                    >
                      <meshStandardMaterial
                        color={tint}
                        emissive={tint}
                        emissiveIntensity={index === highlight ? 0.42 : 0.16}
                        roughness={0.8}
                      />
                    </mesh>
                  ) : null}
                </group>
              );
            })}

            <mesh
              geometry={geometry.cap}
              visible={capReveal > 0}
              position={[0, Math.max(0, section.height - 0.055), 0]}
              scale={[slabWidth, 0.055 * Math.max(0.001, capReveal), depth]}
            >
              <meshStandardMaterial
                color={section.color}
                emissive={section.color}
                emissiveIntensity={index === highlight ? 0.85 : 0.22}
                roughness={0.5}
                metalness={0.15}
              />
            </mesh>
          </group>
        );
      })}

      {/* A restrained stepped datum joins the two summit elevations.
          The narrow illuminated riser is the actual difference in height. */}
      {sections.slice(0, -1).map((left, index) => {
        const right = sections[index + 1];
        const xLeft = left.x + slabWidth * 0.45;
        const xRight = right.x - slabWidth * 0.45;
        const difference = Math.abs(right.height - left.height);
        const color =
          index === highlight || index + 1 === highlight
            ? props.brand.colors.accent
            : "#9DB1C4";

        return (
          <group key={index} visible={connectionOpacity > 0}>
            <mesh
              geometry={geometry.box}
              position={[(xLeft + xRight) / 2, left.height, depth * 0.56]}
              scale={[xRight - xLeft, 0.018, 0.018]}
            >
              <meshBasicMaterial
                color={color}
                transparent
                opacity={connectionOpacity}
              />
            </mesh>
            <mesh
              geometry={geometry.box}
              position={[
                xRight,
                (left.height + right.height) / 2,
                depth * 0.56,
              ]}
              scale={[0.026, Math.max(0.018, difference), 0.026]}
            >
              <meshBasicMaterial
                color={color}
                transparent
                opacity={connectionOpacity}
              />
            </mesh>
          </group>
        );
      })}
    </ChartStage>
  );
}