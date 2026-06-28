import { Badge } from "./ui/Badge";

const STATUS_VARIANT = {
  running: "warning",
  success: "success",
  failed: "error",
} as const;

interface Props {
  status: "running" | "success" | "failed";
}

export function StatusBadge({ status }: Props) {
  return <Badge variant={STATUS_VARIANT[status]}>{status}</Badge>;
}
