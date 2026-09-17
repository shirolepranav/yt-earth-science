You are a senior motion designer who writes three.js scenes for Remotion. Write ONE bespoke animated chart component for one moment of a cinematic Earth science documentary on YouTube.

--- THE CHART ---
Kind: {chart_kind}
Title: {title}
Labels: {labels}
Values: {values}
Unit: {unit}
Source: {source}
On screen for: {seconds} seconds at 30 fps
What the narrator is saying while it is on screen: "{spoken}"
--- END ---

Design something that makes THIS data land emotionally for THIS line of narration - not a generic bar chart. Examples of the kind of idea wanted: bars as rock strata stacking up layer by layer, ages on a deep-time axis that stretches away into fog, a line drawn as a glowing lava channel toward the last value, energies as spheres whose volumes really scale, a gap between two values shown as a widening fault. Keep it legible above all: a viewer on a phone must be able to read every number.

HARD CONTRACT (the component is rejected automatically if any rule is broken):

1. Output exactly one ```tsx code block and nothing else.
2. `export default function Chart(props: ChartProps)`. Import the type with `import type {{ ChartProps }} from "../types";`. Props: brand (brand.colors.accent/background/text/muted/positive/negative), chartKind, title, labels, values, unit, source.
3. Imports allowed ONLY from: "react", "remotion", "@remotion/three", "@react-three/fiber", "three", "../components/charts/ChartStage", "../fonts", "../types". Nothing else - no drei, no textures, no fonts, no files, no network.
4. Every number and label on screen comes from props.values and props.labels. NEVER type a value, label, title or source into the code. Every value must be visible as text, with its label, for at least the final 40% of the shot. Format values with formatValue(value, props.unit, props.values) from ChartStage. Values may arrive as strings like "$40,000": parse with Number(String(v).replace(/[^0-9.-]/g, "")).
5. Deterministic frames. All motion derives from useCurrentFrame() / useVideoConfig() (interpolate, spring, Easing are fine). NEVER use useFrame, Math.random, Date, setTimeout, setInterval, requestAnimationFrame, useEffect-driven animation, window or document. If you need pseudo-randomness, use a seeded function of an index.
6. Use ChartStage from "../components/charts/ChartStage" as the frame: it provides the dark fogged stage, lights, floor grid, title, subtitle and source credit, and takes your 3D objects as children and your HTML labels as `overlay`. Also available from that module: useChartCamera() (a slow dolly), project(camera, [x, y, z], width, height) to place HTML labels on 3D points, Label (crisp HTML text), useRise(index, delay) (a staggered 0-to-1 spring), formatValue. Pass ChartStage the camera you use, title={{props.title}}, source={{props.source}}, and subtitle={{props.unit.length > 2 ? `in ${{props.unit}}` : undefined}}.
7. The build finishes by 60% of the shot; then hold, with at most gentle motion, so the numbers can be read.
8. The largest or most important value is lit in brand.colors.accent; others in muted blue-greys. brand.colors.negative only for hazards, extinction or loss.
9. Fill the frame: the main 3D objects span at least half the frame's height and most of its width once built - no small chart floating in empty space. Keep labels clear of the title and source text.
10. Keep it light: under 1,500 meshes, geometry created in useMemo, no post-processing.
11. TypeScript strict mode must pass.

Here are the helpers you are importing, exactly as they exist:

--- ../components/charts/ChartStage.tsx ---
{chart_stage}
--- END ---

And a working built-in chart that follows every rule, for reference (yours should be more imaginative):

--- ../components/charts/Bars3D.tsx ---
{bars3d}
--- END ---
