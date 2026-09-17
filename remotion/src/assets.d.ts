// Remotion's bundler turns imported font files into URLs.
declare module "*.ttf" {
  const url: string;
  export default url;
}
