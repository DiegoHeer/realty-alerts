import { render } from "@testing-library/react-native";

import { StatusBadge } from "@/components/StatusBadge";

const STATUS_STYLES = {
  running: { bg: "#fef3c7", text: "#92400e" },
  success: { bg: "#d1fae5", text: "#065f46" },
  failed: { bg: "#fee2e2", text: "#991b1b" },
} as const;

describe("StatusBadge", () => {
  it.each(Object.keys(STATUS_STYLES) as (keyof typeof STATUS_STYLES)[])(
    "renders the literal status text for %s",
    (status) => {
      const { getByText } = render(<StatusBadge status={status} />);
      expect(getByText(status)).toBeTruthy();
    },
  );

  it.each(Object.entries(STATUS_STYLES))(
    "applies the %s color palette",
    (status, palette) => {
      const { toJSON } = render(
        <StatusBadge status={status as keyof typeof STATUS_STYLES} />,
      );
      const tree = toJSON() as { props: { style: object }; children: { props: { style: object } }[] };
      expect(tree.props.style).toMatchObject({ backgroundColor: palette.bg });
      expect(tree.children[0].props.style).toMatchObject({ color: palette.text });
    },
  );
});
