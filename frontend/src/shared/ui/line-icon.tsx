import {
  ArrowBothDirectionVertical1Outlined,
  ArrowRightOutlined,
  Buildings1Outlined,
  ExitOutlined,
  Gear1Outlined,
  Locked2Outlined,
  MenuHamburger1Outlined,
  Shield2CheckOutlined,
  User4Outlined,
  UserMultiple4Outlined,
} from "@lineiconshq/free-icons";
import type { SVGProps } from "react";
import { cn } from "@/shared/lib/utils";

interface LineIconDefinition {
  svg: string;
  viewBox: string;
  hasFill: boolean;
  hasStroke: boolean;
  hasStrokeWidth: boolean;
  defaultFill?: string;
  defaultStroke?: string;
}

const lineIconRegistry = {
  roles: Shield2CheckOutlined,
  members: UserMultiple4Outlined,
  settings: Gear1Outlined,
  tenant: Buildings1Outlined,
  switchTenant: ArrowBothDirectionVertical1Outlined,
  profile: User4Outlined,
  logout: ExitOutlined,
  menu: MenuHamburger1Outlined,
  chevronRight: ArrowRightOutlined,
  permissions: Locked2Outlined,
} satisfies Record<string, LineIconDefinition>;

export type LineIconName = keyof typeof lineIconRegistry;

export interface LineIconProps extends Omit<SVGProps<SVGSVGElement>, "name"> {
  name: LineIconName;
  size?: number | string;
  strokeWidth?: number;
}

function buildIconMarkup(
  icon: LineIconDefinition,
  color: string,
  strokeWidth: number
) {
  let svg = icon.svg;
  if (icon.hasFill) {
    svg = svg.replace(/fill="{color}"/g, `fill="${color}"`);
  }
  if (icon.hasStroke) {
    svg = svg.replace(/stroke="{color}"/g, `stroke="${color}"`);
  }
  if (icon.hasStrokeWidth) {
    svg = svg.replace(
      /stroke-width="{strokeWidth}"/g,
      `stroke-width="${strokeWidth}"`
    );
  }
  return svg;
}

export function LineIcon({
  name,
  size = 24,
  color = "currentColor",
  strokeWidth = 1.65,
  className,
  "aria-hidden": ariaHidden = true,
  ...props
}: LineIconProps) {
  const icon = lineIconRegistry[name];
  const svg = buildIconMarkup(icon, color, strokeWidth);
  const svgProps: SVGProps<SVGSVGElement> = {
    width: size,
    height: size,
    viewBox: icon.viewBox,
    fill: icon.defaultFill ?? "none",
    stroke: icon.defaultStroke ?? "none",
    className: cn("shrink-0", className),
    "aria-hidden": ariaHidden,
    dangerouslySetInnerHTML: { __html: svg },
    ...props,
  };

  if (icon.hasFill && !svg.includes("fill=")) {
    svgProps.fill = color;
  }
  if (icon.hasStroke && !svg.includes("stroke=")) {
    svgProps.stroke = color;
  }
  if (icon.hasStrokeWidth && !svg.includes("stroke-width=")) {
    svgProps.strokeWidth = strokeWidth;
  }

  return <svg {...svgProps} />;
}
