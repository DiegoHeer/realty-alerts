import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Footer } from "./Footer";

describe("Footer", () => {
  it("renders without crashing", () => {
    const { container } = render(<Footer />);
    expect(container.firstChild).toBeTruthy();
  });
});
