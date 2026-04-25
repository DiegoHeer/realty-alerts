import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Features } from "./Features";

describe("Features", () => {
  it("renders without crashing", () => {
    const { container } = render(<Features />);
    expect(container.firstChild).toBeTruthy();
  });
});
