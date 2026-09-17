import { useEffect, useState } from "react";
import { cancelRender, continueRender, delayRender } from "remotion";
import { INTER, OSWALD, SOURCE_SERIF } from "./fonts/embedded";

// Three OFL fonts, embedded in the bundle as base64 Latin subsets
// (tools/embed_fonts.py). Loading them over HTTP hung on long renders, so
// there is no network request here at all:
//   DISPLAY - condensed all-caps cards, chart titles, big numbers (ColdFusion style)
//   BODY    - labels and source credits
//   SERIF   - the recreated article/filing pages in evidence shots
export const DISPLAY = "Oswald";
export const BODY = "Inter";
export const SERIF = "Source Serif 4";

// Loading starts as soon as the bundle does (it takes ~20ms)...
const fontsLoaded = Promise.all(
  [
    new FontFace(DISPLAY, `url(${OSWALD})`, { weight: "200 700" }),
    new FontFace(BODY, `url(${INTER})`, { weight: "100 900" }),
    new FontFace(SERIF, `url(${SOURCE_SERIF})`, { weight: "200 900" }),
  ].map((face) => face.load().then((loaded) => document.fonts.add(loaded))),
);

// ...but the render waits for it from inside the composition, not at import time.
// A delayRender() made while the bundle is still evaluating gets its timeout
// dropped from Remotion's window-level table before continueRender() runs, so
// the timer was never cleared and killed every render segment ~2 minutes in
// ("Loading fonts" not cleared after 118000ms, 15 Sep 2026).
export const useFonts = (): void => {
  const [handle] = useState(() => delayRender("Loading fonts"));
  useEffect(() => {
    fontsLoaded.then(() => continueRender(handle)).catch((error) => cancelRender(error));
  }, [handle]);
};
