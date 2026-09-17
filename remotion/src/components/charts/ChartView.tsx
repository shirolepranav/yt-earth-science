import React from "react";
import { charts as generated } from "../../generated";
import type { ChartData, ChartProps, Brand } from "../../types";
import { Bars3D } from "./Bars3D";
import { BigNumber } from "./BigNumber";
import { Line3D } from "./Line3D";

/** The built-in three.js chart for a chart kind - the fallback for every chart. */
export const BuiltinChart: React.FC<ChartProps> = (props) => {
  if (props.chartKind === "line") return <Line3D {...props} />;
  if (props.chartKind === "bignumber")
    return <BigNumber brand={props.brand} value={String(props.values[0] ?? "")} label={props.title} source={props.source} />;
  return <Bars3D {...props} />;
};

/** The GPT-6 Astra component written for this chart if one was accepted, else the built-in. */
export const ChartView: React.FC<{ brand: Brand; chart: ChartData; component?: string | null }> = ({ brand, chart, component }) => {
  const Generated = component ? generated[component] : undefined;
  return Generated ? <Generated brand={brand} {...chart} /> : <BuiltinChart brand={brand} {...chart} />;
};
