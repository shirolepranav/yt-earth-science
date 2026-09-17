import React, { useMemo } from "react";
import { Easing, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import * as THREE from "three";
import { BODY } from "../../fonts";
import type { Brand } from "../../types";
import { ChartStage, Label, formatValue, project, useChartCamera } from "./ChartStage";

const SEGMENTS = 240;
const RADIAL = 12;

/**
 * A glowing tube that draws itself along the data while the camera follows,
 * with the running value riding on its head. The drawn fraction is a draw
 * range over the tube's index buffer - no geometry is rebuilt per frame.
 */
export const Line3D: React.FC<{ brand: Brand; title: string; labels: string[]; values: (number | string)[]; unit: string; source: string }> = ({
  brand, title, labels, values, unit, source,
}) => {
  const frame = useCurrentFrame();
  const { width, height, fps } = useVideoConfig();
  const camera = useChartCamera();
  const nums = values.map((v) => Number(String(v).replace(/[^0-9.-]/g, "")) || 0);
  const lo = Math.min(...nums);
  const span = Math.max(...nums) - lo || 1;

  const points = useMemo(
    () => nums.map((v, i) => new THREE.Vector3((i / Math.max(1, nums.length - 1) - 0.5) * 10, 0.4 + ((v - lo) / span) * 3.8, 0)),
    [values.join("|")], // eslint-disable-line react-hooks/exhaustive-deps
  );
  const curve = useMemo(() => new THREE.CatmullRomCurve3(points, false, "centripetal"), [points]);
  const geometry = useMemo(() => new THREE.TubeGeometry(curve, SEGMENTS, 0.07, RADIAL, false), [curve]);

  const progress = interpolate(frame, [10, 10 + fps * 2.6], [0, 1], {
    extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.inOut(Easing.cubic),
  });
  geometry.setDrawRange(0, Math.floor((geometry.index?.count ?? 0) * progress / 6) * 6);

  const head = curve.getPointAt(Math.max(0.0001, progress));
  const exact = progress * (nums.length - 1);
  const k = Math.min(nums.length - 2, Math.floor(exact));
  const running = nums.length > 1 ? nums[k] + (nums[k + 1] - nums[k]) * (exact - k) : nums[0];
  const headPx = project(camera, [head.x, head.y + 0.55, 0], width, height);
  const showAll = labels.length <= 8;

  return (
    <ChartStage
      brand={brand}
      camera={camera}
      title={title}
      subtitle={unit.length > 2 ? `in ${unit}` : undefined}
      source={source}
      overlay={
        <>
          <Label x={headPx.x} y={headPx.y} size={46} color={brand.colors.accent} opacity={Math.min(1, progress * 4)}>
            {formatValue(running, unit, values)}
          </Label>
          {points.map((p, i) => {
            if (!showAll && i !== 0 && i !== points.length - 1) return null;
            const at = project(camera, [p.x, -0.5, 0.9], width, height);
            const visible = progress >= i / Math.max(1, points.length - 1) - 0.001;
            return (
              <Label key={i} x={at.x} y={at.y} size={24} color={brand.colors.muted} font={BODY} weight={500} opacity={visible ? 1 : 0.25}>
                {labels[i] ?? ""}
              </Label>
            );
          })}
        </>
      }
    >
      <mesh geometry={geometry}>
        <meshStandardMaterial color={brand.colors.accent} emissive={brand.colors.accent} emissiveIntensity={0.8} />
      </mesh>
      <mesh position={head}>
        <sphereGeometry args={[0.16, 24, 24]} />
        <meshStandardMaterial color="#FFFFFF" emissive={brand.colors.accent} emissiveIntensity={2} />
      </mesh>
      <pointLight position={[head.x, head.y + 0.4, 0.6]} intensity={10} distance={5} color={brand.colors.accent} />
    </ChartStage>
  );
};
