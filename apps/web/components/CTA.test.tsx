import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { CTA } from "./CTA";

describe("CTA", () => {
  it("renders without crashing", () => {
    const { container } = render(<CTA />);
    expect(container.firstChild).toBeTruthy();
  });
});
