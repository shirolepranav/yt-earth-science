import React from "react";
import { useVideoConfig } from "remotion";
import { BODY } from "../../fonts";
import type { Brand } from "../../types";
import { ChartStage, Label, formatValue, project, useChartCamera, useRise } from "./ChartStage";

const HEIGHT = 3.6; // tallest bar, in world units
const BAR = ({ x, h, w, color, emissive }: { x: number; h: number; w: number; color: string; emissive: string }) => (
  <mesh position={[x, h / 2, 0]}>
    <boxGeometry args={[w, h, w * 0.8]} />
    <meshStandardMaterial color={color} emissive={emissive} emissiveIntensity={0.35} roughness={0.55} metalness={0.1} />
  </mesh>
);

/**
 * Bars that rise one after another while the camera dollies in, values counting
 * up with them. The largest bar is lit in the accent colour - the eye goes
 * straight to the number the narration is about. Used for "bar" and, with two
 * values, "comparison".
 */
export const Bars3D: React.FC<{ brand: Brand; title: string; labels: string[]; values: (number | string)[]; unit: string; source: string }> = ({
  brand, title, labels, values, unit, source,
}) => {
  const { width, height } = useVideoConfig();
  const camera = useChartCamera();
  const nums = values.map((v) => Number(String(v).replace(/[^0-9.-]/g, "")) || 0);
  const max = Math.max(...nums.map(Math.abs), 1e-9);
  const spacing = Math.min(2.2, 9.5 / nums.length);
  const highlight = nums.indexOf(Math.max(...nums));
  const rises = nums.map((_, i) => useRise(i)); // eslint-disable-line react-hooks/rules-of-hooks
  const labelSize = nums.length > 6 ? 30 : 40;

  const bars = nums.map((value, i) => {
    const x = (i - (nums.length - 1) / 2) * spacing;
    return { x, h: Math.max(0.001, (Math.abs(value) / max) * HEIGHT * rises[i]), value };
  });

  return (
    <ChartStage
      brand={brand}
      camera={camera}
      title={title}
      subtitle={unit.length > 2 ? `in ${unit}` : undefined}
      source={source}
      overlay={bars.map((bar, i) => {
        const top = project(camera, [bar.x, bar.h + 0.45, 0], width, height);
        const base = project(camera, [bar.x, -0.5, 0.9], width, height);
        return (
          <React.Fragment key={i}>
            <Label x={top.x} y={top.y} size={i === highlight ? labelSize + 14 : labelSize} color={i === highlight ? brand.colors.accent : brand.colors.text} opacity={Math.min(1, rises[i] * 3)}>
              {formatValue(bar.value * rises[i], unit, values)}
            </Label>
            <Label x={base.x} y={base.y} size={nums.length > 6 ? 20 : 26} color={brand.colors.muted} font={BODY} weight={500}>
              {labels[i] ?? ""}
            </Label>
          </React.Fragment>
        );
      })}
    >
      {bars.map((bar, i) => (
        <BAR key={i} x={bar.x} h={bar.h} w={spacing * 0.6}
          color={i === highlight ? brand.colors.accent : "#3B4757"}
          emissive={i === highlight ? brand.colors.accent : "#000000"} />
      ))}
    </ChartStage>
  );
};
