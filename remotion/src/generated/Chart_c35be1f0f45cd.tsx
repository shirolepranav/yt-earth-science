import React, { useMemo } from "react";
import { useCurrentFrame, useVideoConfig } from "remotion";
import * as THREE from "three";
import {
  ChartStage,
  Label,
  formatValue,
  project,
} from "../components/charts/ChartStage";
import { BODY } from "../fonts";
import type { ChartProps } from "../types";

const clamp = (v: number): number => Math.max(0, Math.min(1, v));
const smooth = (v: number): number => {
  const t = clamp(v);
  return t * t * (3 - 2 * t);
};

type PassageProps = {
  position: [number, number, number];
  radius: number;
  progress: number;
  color: string;
  antipodal: boolean;
  sphere: THREE.SphereGeometry;
  ring: THREE.TorusGeometry;
  dot: THREE.SphereGeometry;
};

/**
 * One passage is one completed circuit, not an arbitrary decorative tick.
 * The wave travels around its globe and leaves a permanent luminous orbit.
 */
function Passage({
  position,
  radius,
  progress,
  color,
  antipodal,
  sphere,
  ring,
  dot,
}: PassageProps) {
  const arc = useMemo(
    () =>
      new THREE.TorusGeometry(
        1.075,
        0.023,
        8,
        100,
        Math.PI * 2 * Math.max(progress, 0.0001),
      ),
    [progress],
  );

  const arrival = smooth(progress / 0.18);
  const angle = progress * Math.PI * 2;
  const latitude = Math.sqrt(1 - 0.45 * 0.45);

  return (
    <group position={position} scale={radius}>
      <mesh geometry={sphere}>
        <meshStandardMaterial
          color="#142637"
          emissive="#102232"
          emissiveIntensity={0.3}
          roughness={0.76}
          metalness={0.2}
          transparent
          opacity={0.2 + arrival * 0.8}
        />
      </mesh>

      {/* A deliberately spare atlas: no textures, invented geography or text. */}
      {[0, Math.PI / 3, (Math.PI * 2) / 3].map((rotation, i) => (
        <mesh
          key={`meridian-${i}`}
          geometry={ring}
          rotation={[0, rotation, 0]}
          scale={1.008}
        >
          <meshBasicMaterial
            color="#7690A4"
            transparent
            opacity={0.08 + arrival * 0.18}
            depthWrite={false}
          />
        </mesh>
      ))}
      {[-0.45, 0, 0.45].map((y, i) => (
        <mesh
          key={`latitude-${i}`}
          geometry={ring}
          position={[0, y, 0]}
          rotation={[Math.PI / 2, 0, 0]}
          scale={y === 0 ? 1.008 : latitude * 1.008}
        >
          <meshBasicMaterial
            color="#7690A4"
            transparent
            opacity={0.08 + arrival * 0.18}
            depthWrite={false}
          />
        </mesh>
      ))}

      <group rotation={[0.58, -0.3, -0.18]}>
        <mesh geometry={ring} scale={1.075}>
          <meshBasicMaterial
            color={color}
            transparent
            opacity={0.15}
            depthWrite={false}
          />
        </mesh>

        <group rotation={[0, 0, antipodal ? Math.PI : 0]}>
          <mesh geometry={arc} visible={progress > 0}>
            <meshBasicMaterial
              color={color}
              transparent
              opacity={0.95}
              toneMapped={false}
            />
          </mesh>
          <mesh
            geometry={dot}
            visible={progress > 0 && progress < 1}
            position={[
              Math.cos(angle) * 1.075,
              Math.sin(angle) * 1.075,
              0,
            ]}
            scale={0.06}
          >
            <meshBasicMaterial color={color} toneMapped={false} />
          </mesh>
        </group>
      </group>
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
  const largest = Math.max(...numbers.map(Math.abs), 1);
  const important = numbers.indexOf(Math.max(...numbers));
  const rowCount = Math.max(numbers.length, 1);

  // A locked, near-orthographic perspective makes both bar lengths comparable.
  // Layout is expressed in screen fractions, leaving the stage's credits clear.
  const distance = 18;
  const fov = 40;
  const viewHeight = 2 * distance * Math.tan((fov * Math.PI) / 360);
  const viewWidth = viewHeight * (width / height);
  const targetY = viewHeight * 0.52;
  const camera = {
    position: [0, targetY, distance] as [number, number, number],
    target: [0, targetY, 0] as [number, number, number],
    fov,
  };

  const world = (x: number, y: number, z = 0): [number, number, number] => [
    (x - 0.5) * viewWidth,
    targetY + (0.5 - y) * viewHeight,
    z,
  ];

  const geometries = useMemo(
    () => ({
      sphere: new THREE.SphereGeometry(1, 32, 20),
      ring: new THREE.TorusGeometry(1, 0.006, 5, 72),
      dot: new THREE.SphereGeometry(1, 10, 8),
      box: new THREE.BoxGeometry(1, 1, 1),
    }),
    [],
  );

  const left = 0.115;
  const totalWidth = viewWidth * 0.77;
  const unitWidth = totalWidth / largest;
  const laneHeight = 0.62 / rowCount;
  const radius = Math.min(
    unitWidth * 0.435,
    viewHeight * laneHeight * 0.365,
  );
  const intro = smooth(time / 0.06);

  const rows = numbers.map((value, index) => {
    const centerY = 0.445 + index * laneHeight;
    const start = 0.065 + index * (0.205 / Math.max(1, rowCount - 1));
    const end = start + 0.285;
    const progress = clamp((time - start) / (end - start));
    const amount = Math.abs(value);
    const length = (amount / largest) * totalWidth;
    const color = index === important ? props.brand.colors.accent : "#8CA9C2";

    // Each whole unit becomes an Earth circuit; fractional units retain
    // proportional bar lengths rather than being rounded to whole passages.
    const cells = Math.min(48, Math.ceil(amount));
    return {
      index,
      value,
      amount,
      centerY,
      start,
      end,
      progress,
      length,
      color,
      cells,
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
          {rows.map((row) => {
            const headerY = row.centerY - laneHeight * 0.47;
            const labelPoint = project(
              camera,
              world(left, headerY),
              width,
              height,
            );
            const valuePoint = project(
              camera,
              world(0.885, headerY),
              width,
              height,
            );

            return (
              <React.Fragment key={row.index}>
                <div
                  style={{
                    position: "absolute",
                    left: labelPoint.x,
                    top: labelPoint.y,
                    transform: "translateY(-50%)",
                    fontFamily: BODY,
                    fontSize: height * 0.034,
                    lineHeight: 1.1,
                    fontWeight: 500,
                    color: props.brand.colors.text,
                    opacity: intro,
                    maxWidth: width * 0.6,
                    textShadow: "0 2px 18px rgba(0,0,0,0.85)",
                  }}
                >
                  {props.labels[row.index] ?? ""}
                </div>
                <Label
                  x={valuePoint.x}
                  y={valuePoint.y}
                  size={height * 0.065}
                  color={row.color}
                  opacity={intro}
                  weight={700}
                >
                  {formatValue(row.value, props.unit, props.values)}
                </Label>
              </React.Fragment>
            );
          })}
        </>
      }
    >
      {rows.map((row) => {
        const origin = world(left, row.centerY);
        const activeLength = row.length * row.progress;
        const baselineY = origin[1] - radius * 1.07;

        return (
          <group key={row.index}>
            {/* The shared measuring rail establishes an identical zero. */}
            <mesh
              geometry={geometries.box}
              position={[
                origin[0] + totalWidth / 2,
                baselineY,
                -radius * 0.3,
              ]}
              scale={[totalWidth, viewHeight * 0.0016, 0.035]}
            >
              <meshBasicMaterial
                color="#526B80"
                transparent
                opacity={0.32 * intro}
              />
            </mesh>

            {/* A continuous rectangular body makes the repeated globes
                read as two segmented bars, not seven unrelated bubbles. */}
            <mesh
              geometry={geometries.box}
              visible={activeLength > 0}
              position={[
                origin[0] + activeLength / 2,
                origin[1],
                -radius * 0.75,
              ]}
              scale={[
                Math.max(activeLength, 0.001),
                radius * 1.84,
                radius * 0.24,
              ]}
            >
              <meshStandardMaterial
                color={row.color}
                emissive={row.color}
                emissiveIntensity={0.18}
                transparent
                opacity={0.14}
                roughness={0.65}
                depthWrite={false}
              />
            </mesh>

            <mesh
              geometry={geometries.box}
              visible={activeLength > 0}
              position={[
                origin[0] + activeLength / 2,
                baselineY,
                0.05,
              ]}
              scale={[
                Math.max(activeLength, 0.001),
                viewHeight * 0.003,
                0.05,
              ]}
            >
              <meshBasicMaterial color={row.color} toneMapped={false} />
            </mesh>

            {Array.from({ length: row.cells }, (_, cell) => {
              const cellAmount = row.amount / Math.max(1, row.cells);
              const cellWidth = unitWidth * cellAmount;
              const passageProgress = clamp(
                row.progress * row.cells - cell,
              );

              return (
                <Passage
                  key={cell}
                  position={[
                    origin[0] + (cell + 0.5) * cellWidth,
                    origin[1],
                    0,
                  ]}
                  radius={Math.min(radius, cellWidth * 0.435)}
                  progress={passageProgress}
                  color={row.color}
                  antipodal={row.index !== important}
                  sphere={geometries.sphere}
                  ring={geometries.ring}
                  dot={geometries.dot}
                />
              );
            })}
          </group>
        );
      })}
    </ChartStage>
  );
}