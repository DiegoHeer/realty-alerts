import { Surface, type SurfaceProps } from "./Surface";

export function Card({ shadow = "sm", radius = "150", padding = "200", ...rest }: SurfaceProps) {
  return <Surface shadow={shadow} radius={radius} padding={padding} {...rest} />;
}
