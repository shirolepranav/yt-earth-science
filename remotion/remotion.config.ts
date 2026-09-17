// Remotion's build settings. See https://remotion.dev/docs/config
import { Config } from "@remotion/cli/config";

// H.264 in an MP4 container is what YouTube wants.
Config.setVideoImageFormat("jpeg");
Config.setCodec("h264");

// CRF is the quality dial: lower means better and bigger. 18 is visually
// lossless for this kind of content (flat colours, charts, text) and still
// produces a sensible file size.
Config.setCrf(18);

// Charts and captions are full of sharp edges, so we render at full quality
// rather than letting the JPEG frames soften the text.
Config.setJpegQuality(95);

Config.setOverwriteOutput(true);
